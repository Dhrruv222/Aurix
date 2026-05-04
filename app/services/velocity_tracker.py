"""
velocity_tracker.py
────────────────────
Thread-safe in-memory per-user sliding-window transaction velocity tracker.

Used by core_ai (fraud scoring) and risk_ai for real-time velocity signals
without a Redis dependency in the current phase.

Window sizes: 1 hour, 24 hours.
Velocity records are only written for APPROVE and REVIEW decisions — blocked
transactions are not counted so they cannot be used to inflate velocity.
"""

import threading
from collections import defaultdict, deque
from datetime import datetime, timezone

# ─── Window sizes ─────────────────────────────────────────────────────────────
_WINDOW_1H_SECS: int = 3_600
_WINDOW_24H_SECS: int = 86_400

# ─── Alert thresholds ─────────────────────────────────────────────────────────
_HIGH_COUNT_1H: int = 5          # more than 5 transactions in 1 hour
_HIGH_COUNT_24H: int = 20        # more than 20 transactions in 24 hours
_HIGH_AMOUNT_1H: float = 50_000.0    # more than 50k in 1 hour
_HIGH_AMOUNT_24H: float = 200_000.0  # more than 200k in 24 hours


def _to_unix(dt: datetime) -> float:
    """Convert datetime to a UTC unix timestamp, handling tz-naive inputs."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).timestamp()
    return dt.timestamp()


class VelocityTracker:
    """
    Per-user velocity tracker using a deque per user.
    Stores (unix_timestamp, amount) entries for recent transactions.

    Thread-safe: all mutations are protected by a single lock.
    Memory is bounded: entries older than 24 h are pruned on every read.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, deque] = defaultdict(deque)

    def record(self, user_id: str, amount: float, ts: datetime) -> None:
        """
        Record a completed transaction for velocity tracking.
        Should only be called for APPROVE / REVIEW decisions.
        """
        unix_ts = _to_unix(ts)
        with self._lock:
            self._store[user_id].append((unix_ts, amount))

    def get_signals(self, user_id: str, as_of: datetime) -> dict:
        """
        Return velocity signals for user_id as of the given timestamp.

        Returns a dict with:
            count_1h / count_24h      — transaction counts in each window
            amount_1h / amount_24h    — summed transaction amounts in each window
            high_count_1h / _24h      — bool flags when counts exceed thresholds
            high_amount_1h / _24h     — bool flags when amounts exceed thresholds
        """
        now = _to_unix(as_of)
        cutoff_1h = now - _WINDOW_1H_SECS
        cutoff_24h = now - _WINDOW_24H_SECS

        with self._lock:
            dq = self._store[user_id]
            # Prune entries older than 24h to bound memory
            while dq and dq[0][0] < cutoff_24h:
                dq.popleft()
            entries_24h = list(dq)

        entries_1h = [(t, a) for t, a in entries_24h if t >= cutoff_1h]

        count_1h = len(entries_1h)
        count_24h = len(entries_24h)
        amount_1h = sum(a for _, a in entries_1h)
        amount_24h = sum(a for _, a in entries_24h)

        return {
            "count_1h": count_1h,
            "count_24h": count_24h,
            "amount_1h": round(amount_1h, 2),
            "amount_24h": round(amount_24h, 2),
            "high_count_1h": count_1h >= _HIGH_COUNT_1H,
            "high_count_24h": count_24h >= _HIGH_COUNT_24H,
            "high_amount_1h": amount_1h >= _HIGH_AMOUNT_1H,
            "high_amount_24h": amount_24h >= _HIGH_AMOUNT_24H,
        }


# ─── Module-level singleton ───────────────────────────────────────────────────
velocity_tracker = VelocityTracker()
