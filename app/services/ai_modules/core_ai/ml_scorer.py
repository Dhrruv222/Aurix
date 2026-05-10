"""
ml_scorer.py
────────────
Random Forest ML fraud scorer.

This replaces the Isolation Forest anomaly detector with a supervised
RandomForestClassifier trained on synthetic labelled transactions.

Design:
  - Trains on 5,000 synthetic labelled transactions at startup.
  - Labels: APPROVE / REVIEW / BLOCK
  - Feature vector: log-amount, cyclical hour encoding, weekend/night flags,
    currency risk, location risk, device presence, amount_k, velocity_1h
  - Lazy-initialised and thread-safe via double-checked locking.
  - Returns an ML risk score (0–100), predicted label, model version,
    class probabilities, and interpretable signals.

In production, replace _synthetic_training_data() with real historical
labelled transactions and persist the trained model artifact.
"""

import logging
import math
import threading
from datetime import datetime
from typing import Optional

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler

logger = logging.getLogger(__name__)

MODEL_VERSION = "random_forest_v1"

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
      [0] log1p(amount)
      [1] sin(2π*hour/24)
      [2] cos(2π*hour/24)
      [3] is_weekend (0/1)
      [4] is_night (0/1)
      [5] currency_risk (0–1)
      [6] location_risk (0–1)
      [7] has_device (0/1)
      [8] amount_k (capped at 20)
      [9] velocity_1h (capped)
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


# ─── Synthetic Label Logic ────────────────────────────────────────────────────

def _assign_label(
    amount: float,
    currency_risk: float,
    location_risk: float,
    has_device: bool,
    is_night: bool,
    count_1h: int,
) -> str:
    """
    Assign synthetic fraud labels for supervised training.

    APPROVE: low-risk baseline
    REVIEW:  moderate suspiciousness
    BLOCK:   strong suspiciousness
    """
    score = 0

    if amount >= 10_000:
        score += 4
    elif amount >= 5_000:
        score += 2
    elif amount >= 1_000:
        score += 1

    if currency_risk >= 0.7:
        score += 1

    if location_risk >= 1.0:
        score += 3
    elif location_risk >= 0.35:
        score += 1
    elif location_risk >= 0.75:
        score += 2

    if not has_device:
        score += 1

    if is_night:
        score += 1

    if count_1h >= 5:
        score += 3
    elif count_1h >= 3:
        score += 1

    if score >= 7:
        return "BLOCK"
    if score >= 3:
        return "REVIEW"
    return "APPROVE"


# ─── Synthetic Training Data ──────────────────────────────────────────────────

def _synthetic_training_data(n: int = 5_000, seed: int = 42):
    """
    Generate synthetic labelled transaction data for supervised training.
    """
    rng = np.random.default_rng(seed)

    X_rows = []
    y_rows = []

    hour_weights = np.array(
        [
            0.15, 0.10, 0.08, 0.08, 0.10, 0.12,
            0.60, 1.20, 1.80,
            2.80, 3.20, 3.20, 3.20, 3.00, 2.80,
            2.80, 2.50, 2.20, 2.00, 1.60,
            1.20, 0.80, 0.45, 0.25,
        ]
    )
    hour_weights /= hour_weights.sum()

    for _ in range(n):
        amount_bucket = rng.choice([0, 1, 2, 3], p=[0.45, 0.30, 0.18, 0.07])
        if amount_bucket == 0:
            amount = rng.uniform(5, 300)
        elif amount_bucket == 1:
            amount = rng.uniform(300, 1_500)
        elif amount_bucket == 2:
            amount = rng.uniform(1_500, 5_000)
        else:
            amount = rng.uniform(5_000, 15_000)

        hour = int(rng.choice(24, p=hour_weights))
        weekday = int(rng.integers(0, 7))

        currency_risk = float(rng.choice([0.0, 0.7], p=[0.95, 0.05]))
        location_risk = float(rng.choice([0.0, 0.35, 0.75, 1.0], p=[0.80, 0.10, 0.05, 0.05]))
        has_device = bool(rng.choice([True, False], p=[0.90, 0.10]))
        count_1h = int(rng.integers(0, 6))

        # Build category values from risks
        currency = "EUR" if currency_risk == 0.0 else "XTS"
        if location_risk == 1.0:
            location = "IR"
        elif location_risk == 0.75:
            location = None
        elif location_risk == 0.35:
            location = "NG"
        else:
            location = "DE"

        features = _build_features(
            amount=amount,
            currency=currency,
            location=location,
            hour=hour,
            weekday=weekday,
            has_device=has_device,
            count_1h=count_1h,
        )

        label = _assign_label(
            amount=amount,
            currency_risk=currency_risk,
            location_risk=location_risk,
            has_device=has_device,
            is_night=(hour < 6 or hour >= 22),
            count_1h=count_1h,
        )

        X_rows.append(features)
        y_rows.append(label)

    return np.vstack(X_rows), np.array(y_rows)


# ─── Scorer Class ─────────────────────────────────────────────────────────────

class RandomForestFraudScorer:
    """
    Random Forest classifier for transaction fraud scoring.
    """

    def __init__(self) -> None:
        logger.info(
            f"[ML-SCORER] Training Random Forest "
            f"(n_samples=5000, n_estimators=200, version={MODEL_VERSION})..."
        )

        X, y = _synthetic_training_data(n=5_000)

        self._scaler = StandardScaler().fit(X)
        X_scaled = self._scaler.transform(X)

        self._label_encoder = LabelEncoder()
        y_encoded = self._label_encoder.fit_transform(y)

        self._model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            random_state=42,
            class_weight="balanced",
            n_jobs=-1,
        )
        self._model.fit(X_scaled, y_encoded)

        logger.info(
            f"[ML-SCORER] Ready. version={MODEL_VERSION} "
            f"classes={list(self._label_encoder.classes_)}"
        )

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
            ml_score        — float 0–100 (higher = more suspicious)
            predicted_label — APPROVE / REVIEW / BLOCK
            model_version   — str
            probabilities   — class probability map
            signals         — interpretable feature values
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

        pred_encoded = self._model.predict(X)[0]
        predicted_label = str(self._label_encoder.inverse_transform([pred_encoded])[0])

        probabilities = self._model.predict_proba(X)[0]
        class_names = self._label_encoder.classes_

        prob_map = {
            str(class_name): float(probabilities[idx])
            for idx, class_name in enumerate(class_names)
        }

        approve_prob = prob_map.get("APPROVE", 0.0)
        review_prob = prob_map.get("REVIEW", 0.0)
        block_prob = prob_map.get("BLOCK", 0.0)

        # Weighted risk score from class probabilities
        ml_score = max(0.0, min(100.0, review_prob * 60.0 + block_prob * 100.0))

        return {
            "ml_score": round(ml_score, 2),
            "predicted_label": predicted_label,
            "model_version": MODEL_VERSION,
            "probabilities": {
                "APPROVE": round(approve_prob, 4),
                "REVIEW": round(review_prob, 4),
                "BLOCK": round(block_prob, 4),
            },
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

_scorer: Optional[RandomForestFraudScorer] = None
_scorer_lock = threading.Lock()


def get_ml_scorer() -> RandomForestFraudScorer:
    """Return the module-level scorer, initialising it on the first call."""
    global _scorer
    if _scorer is None:
        with _scorer_lock:
            if _scorer is None:
                _scorer = RandomForestFraudScorer()
    return _scorer


def warmup() -> None:
    """Pre-warm the scorer (call during app lifespan startup)."""
    get_ml_scorer()


    