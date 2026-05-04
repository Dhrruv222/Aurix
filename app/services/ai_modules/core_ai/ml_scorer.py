"""
ml_scorer.py
─────────────
Isolation Forest ML fraud scorer.

Phase 2 ML implementation wired into compute_fraud_score_ml().

Design:
  - Trains an Isolation Forest on 5,000 synthetic normal transactions at startup.
  - Feature vector: log-amount, cyclical hour encoding, weekend/night flags,
    currency risk, location risk, device presence, velocity count (10 features).
  - Lazy-initialised: model is built on first call, then cached.
  - Thread-safe lazy init via double-checked locking.
  - Inference is microseconds per call (sklearn IF predict is O(estimators * depth)).

In production, replace _synthetic_training_data() with real historical
transaction data and retrain periodically (e.g. via an MLflow pipeline).
"""

import logging
import math
import threading
from datetime import datetime
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MODEL_VERSION = "isolation_forest_v1"

# ─── Risk Lookup Tables ───────────────────────────────────────────────────────

_TRUSTED_CURRENCIES = frozenset(
    {"EUR", "USD", "GBP", "CHF", "SGD", "JPY", "AUD", "CAD", "SEK", "NOK", "DKK"}
)

_HIGH_RISK_LOCATIONS = frozenset(
    {"KP", "IR", "SY", "CU", "SD", "MM", "RU", "AF", "YE", "LY", "VE"}
)

_LOW_RISK_LOCATIONS = frozenset(
    {
        "DE", "FR", "GB", "NL", "CH", "US", "CA", "AU", "JP",
        "SE", "NO", "DK", "AT", "FI", "BE", "IE", "NZ", "SG",
        "PT", "ES", "IT", "LU", "EE", "LT", "LV",
    }
)


def _currency_risk(currency: str) -> float:
    return 0.0 if currency.upper() in _TRUSTED_CURRENCIES else 0.7


def _location_risk(location: Optional[str]) -> float:
    if location is None:
        return 0.75
    loc = location.upper()
    if loc in _HIGH_RISK_LOCATIONS:
        return 1.0
    if loc in _LOW_RISK_LOCATIONS:
        return 0.0
    return 0.35


# ─── Feature Engineering ──────────────────────────────────────────────────────

_N_FEATURES = 10


def _build_features(
    amount: float,
    currency: str,
    location: Optional[str],
    hour: int,
    weekday: int,
    has_device: bool,
    count_1h: int,
) -> np.ndarray:
    """
    Construct a 10-dimensional feature vector from transaction properties.

    Features:
      [0] log1p(amount)           — log-scaled amount (reduces skew)
      [1] sin(2π*hour/24)         — hour of day, cyclical encoding (sin component)
      [2] cos(2π*hour/24)         — hour of day, cyclical encoding (cos component)
      [3] is_weekend (0/1)
      [4] is_night (0/1)          — hour < 6 or >= 22
      [5] currency_risk (0–1)
      [6] location_risk (0–1)
      [7] has_device (0/1)
      [8] amount_k (capped at 20) — amount in thousands
      [9] velocity_1h (capped)    — normalised transaction count in last hour
    """
    return np.array(
        [
            math.log1p(amount),
            math.sin(2 * math.pi * hour / 24),
            math.cos(2 * math.pi * hour / 24),
            float(weekday >= 5),
            float(hour < 6 or hour >= 22),
            _currency_risk(currency),
            _location_risk(location),
            float(has_device),
            min(amount / 1_000.0, 20.0),
            min(float(count_1h) / 10.0, 5.0),
        ],
        dtype=np.float64,
    )


# ─── Synthetic Training Data ──────────────────────────────────────────────────

def _synthetic_training_data(n: int = 5_000, seed: int = 42) -> np.ndarray:
    """
    Generate n synthetic normal transaction feature vectors for training.

    Statistical parameters reflect real-world fintech transaction distributions:
      - Amounts: 55% small (5–300), 30% medium (300–1500), 15% large (1500–5000)
      - Hours: business-hours skewed
      - Currencies: 96% trusted
      - Locations: 82% low-risk
      - Device presence: 90%
      - Velocity: 0–3 in last hour (normal burst)
    """
    rng = np.random.default_rng(seed)

    amounts = np.concatenate(
        [
            rng.uniform(5, 300, int(n * 0.55)),
            rng.uniform(300, 1_500, int(n * 0.30)),
            rng.uniform(1_500, 5_000, int(n * 0.15)),
        ]
    )[:n]

    # Business-hours distribution
    hour_weights = np.array(
        [
            0.15, 0.10, 0.08, 0.08, 0.10, 0.12,  # 0–5: night
            0.60, 1.20, 1.80,                      # 6–8: morning
            2.80, 3.20, 3.20, 3.20, 3.00, 2.80,   # 9–14: core hours
            2.80, 2.50, 2.20, 2.00, 1.60,          # 15–19: afternoon
            1.20, 0.80, 0.45, 0.25,                # 20–23: evening
        ]
    )
    hour_weights /= hour_weights.sum()
    hours = rng.choice(24, size=n, p=hour_weights)

    weekdays = rng.integers(0, 7, size=n)
    currency_risks = rng.choice([0.0, 0.7], size=n, p=[0.96, 0.04])
    location_risks = rng.choice(
        [0.0, 0.35, 0.75, 1.0], size=n, p=[0.82, 0.10, 0.05, 0.03]
    )
    has_device = rng.choice([1.0, 0.0], size=n, p=[0.90, 0.10])
    count_1h = rng.integers(0, 4, size=n).astype(float)

    return np.column_stack(
        [
            np.log1p(amounts),
            np.sin(2 * np.pi * hours / 24),
            np.cos(2 * np.pi * hours / 24),
            (weekdays >= 5).astype(float),
            ((hours < 6) | (hours >= 22)).astype(float),
            currency_risks,
            location_risks,
            has_device,
            np.minimum(amounts / 1_000.0, 20.0),
            np.minimum(count_1h / 10.0, 5.0),
        ]
    )


# ─── Scorer Class ─────────────────────────────────────────────────────────────

class IsolationFraudScorer:
    """
    Isolation Forest anomaly detector for transaction fraud scoring.

    contamination=0.04: model expects ~4% of real traffic to be anomalous.
    n_estimators=200: more trees → stabler anomaly scores at the cost of
    slightly higher memory. Still <10 MB for 200 trees on 10 features.
    """

    def __init__(self) -> None:
        logger.info(
            f"[ML-SCORER] Training Isolation Forest "
            f"(n_samples=5000, n_estimators=200, version={MODEL_VERSION})..."
        )
        X = _synthetic_training_data(n=5_000)
        self._scaler = StandardScaler().fit(X)
        X_scaled = self._scaler.transform(X)
        self._model = IsolationForest(
            n_estimators=200,
            contamination=0.04,
            random_state=42,
            n_jobs=-1,
        )
        self._model.fit(X_scaled)
        logger.info(f"[ML-SCORER] Ready. version={MODEL_VERSION}")

    def score(
        self,
        amount: float,
        currency: str,
        location: Optional[str],
        timestamp: datetime,
        device_id: Optional[str],
        count_1h: int = 0,
    ) -> dict:
        """
        Score a single transaction.

        Returns:
            anomaly_score  — float 0–100 (higher = more suspicious)
            is_anomaly     — bool (True when IF predicts outlier)
            model_version  — str
            signals        — dict of per-feature interpretable values
        """
        features = _build_features(
            amount=amount,
            currency=currency,
            location=location,
            hour=timestamp.hour,
            weekday=timestamp.weekday(),
            has_device=device_id is not None,
            count_1h=count_1h,
        )
        X = self._scaler.transform(features.reshape(1, -1))
        raw = float(self._model.decision_function(X)[0])
        is_anomaly = bool(self._model.predict(X)[0] == -1)

        # decision_function: higher (more positive) = more normal.
        # Calibrated mapping to 0–100 anomaly score:
        #   raw ≈  0.10 → score ≈   0   (typical normal transaction)
        #   raw ≈  0.00 → score ≈  20   (slightly unusual)
        #   raw ≈ -0.20 → score ≈  60   (suspect)
        #   raw ≈ -0.40 → score ≈ 100   (strongly anomalous)
        anomaly_score = max(0.0, min(100.0, (0.10 - raw) * 200.0))

        return {
            "anomaly_score": round(anomaly_score, 2),
            "is_anomaly": is_anomaly,
            "model_version": MODEL_VERSION,
            "signals": {
                "log_amount": round(float(features[0]), 3),
                "is_night": bool(features[4] > 0.5),
                "currency_risk": round(float(features[5]), 2),
                "location_risk": round(float(features[6]), 2),
                "has_device": bool(features[7] > 0.5),
                "velocity_1h": int(count_1h),
            },
        }


# ─── Lazy singleton ───────────────────────────────────────────────────────────

_scorer: Optional[IsolationFraudScorer] = None
_scorer_lock = threading.Lock()


def get_ml_scorer() -> IsolationFraudScorer:
    """Return the module-level scorer, initialising it on the first call."""
    global _scorer
    if _scorer is None:
        with _scorer_lock:
            if _scorer is None:  # double-checked locking
                _scorer = IsolationFraudScorer()
    return _scorer


def warmup() -> None:
    """Pre-warm the scorer (call during app lifespan startup)."""
    get_ml_scorer()
