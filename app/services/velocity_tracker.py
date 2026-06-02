"""
velocity_tracker.py
────────────────────
Thread-safe in-memory per-user sliding-window transaction velocity tracker.

Used by core_ai (fraud scoring) and risk_ai for real-time velocity signals
without a Redis dependency in the current phase.

Window sizes:
- 1 minute
- 1 hour
- 24 hours

Velocity records are only written for APPROVE and REVIEW decisions — blocked
transactions are not counted so they cannot be used to inflate velocity.
"""

import threading
from collections import defaultdict, deque
from datetime import datetime, timezone

from app.core.config import settings

# ─── Window sizes ─────────────────────────────────────────────────────────────
_WINDOW_1M_SECS: int = 60
_WINDOW_1H_SECS: int = 3_600
_WINDOW_24H_SECS: int = 86_400

# ─── Alert thresholds ─────────────────────────────────────────────────────────
_HIGH_COUNT_1M: int = 5
_HIGH_COUNT_1H: int = 5
_HIGH_COUNT_24H: int = 20
_HIGH_AMOUNT_1H: float = 50_000.0
_HIGH_AMOUNT_24H: float = 200_000.0


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
        """
        now = _to_unix(as_of)
        cutoff_1m = now - _WINDOW_1M_SECS
        cutoff_1h = now - _WINDOW_1H_SECS
        cutoff_24h = now - _WINDOW_24H_SECS

        with self._lock:
            dq = self._store[user_id]

            # Prune entries older than 24h to bound memory
            while dq and dq[0][0] < cutoff_24h:
                dq.popleft()

            entries_24h = list(dq)

        entries_1h = [(t, a) for t, a in entries_24h if t >= cutoff_1h]
        entries_1m = [(t, a) for t, a in entries_24h if t >= cutoff_1m]

        count_1m = len(entries_1m)
        count_1h = len(entries_1h)
        count_24h = len(entries_24h)

        amount_1m = sum(a for _, a in entries_1m)
        amount_1h = sum(a for _, a in entries_1h)
        amount_24h = sum(a for _, a in entries_24h)

        large_count_1m = sum(1 for _, a in entries_1m if a >= settings.MEDIUM_RISK_AMOUNT)
        large_count_1h = sum(1 for _, a in entries_1h if a >= settings.MEDIUM_RISK_AMOUNT)
        large_count_24h = sum(1 for _, a in entries_24h if a >= settings.MEDIUM_RISK_AMOUNT)

        return {
            "count_1m": count_1m,
            "count_1h": count_1h,
            "count_24h": count_24h,
            "amount_1m": round(amount_1m, 2),
            "amount_1h": round(amount_1h, 2),
            "amount_24h": round(amount_24h, 2),
            "large_count_1m": large_count_1m,
            "large_count_1h": large_count_1h,
            "large_count_24h": large_count_24h,
            "high_count_1m": count_1m >= _HIGH_COUNT_1M,
            "high_count_1h": count_1h >= _HIGH_COUNT_1H,
            "high_count_24h": count_24h >= _HIGH_COUNT_24H,
            "high_amount_1h": amount_1h >= _HIGH_AMOUNT_1H,
            "high_amount_24h": amount_24h >= _HIGH_AMOUNT_24H,
            "repeated_large_1m": large_count_1m >= 2,
            "repeated_large_1h": large_count_1h >= 2,
            "repeated_large_24h": large_count_24h >= 3,
        }


# ─── Module-level singleton ───────────────────────────────────────────────────
velocity_tracker = VelocityTracker()