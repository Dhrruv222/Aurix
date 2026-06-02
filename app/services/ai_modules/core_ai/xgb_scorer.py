"""
xgb_scorer.py
─────────────
Future-ready XGBoost fraud scorer for Aurix.

Purpose:
- provide a supervised fraud scoring module for future phases
- keep it separate from the active MVP fraud path
- support later shadow mode or active use through config

Current status:
- safe to add now
- not activated by default
- designed to be called from service.py later when needed
"""

import logging
import math
import threading
from datetime import datetime
from typing import Optional

import numpy as np
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

MODEL_VERSION = "xgboost_v1"

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

def _build_features(
    amount: float,
    currency: str,
    location: Optional[str],
    hour: int,
    weekday: int,
    has_device: bool,
    count_1h: int,
) -> np.ndarray:
    return np.array(
        [
            math.log1p(amount),                     # [0] log_amount
            math.sin(2 * math.pi * hour / 24),     # [1] hour_sin
            math.cos(2 * math.pi * hour / 24),     # [2] hour_cos
            float(weekday >= 5),                   # [3] is_weekend
            float(hour < 6 or hour >= 22),         # [4] is_night
            _currency_risk(currency),              # [5] currency_risk
            _location_risk(location),              # [6] location_risk
            float(has_device),                     # [7] has_device
            min(amount / 1_000.0, 20.0),           # [8] amount_k
            min(float(count_1h) / 10.0, 5.0),      # [9] velocity_1h
        ],
        dtype=np.float64,
    )


# ─── Synthetic Label Logic ────────────────────────────────────────────────────

_LABELS = ["APPROVE", "REVIEW", "BLOCK"]
_LABEL_TO_INT = {"APPROVE": 0, "REVIEW": 1, "BLOCK": 2}
_INT_TO_LABEL = {0: "APPROVE", 1: "REVIEW", 2: "BLOCK"}


def _assign_label(
    amount: float,
    currency_risk_value: float,
    location_risk_value: float,
    has_device: bool,
    is_night: bool,
    count_1h: int,
) -> str:
    score = 0

    if amount >= 20_000:
        score += 4
    elif amount >= 5_000:
        score += 2

    if currency_risk_value >= 0.7:
        score += 1

    if location_risk_value >= 1.0:
        score += 3
    elif location_risk_value >= 0.35:
        score += 1

    if not has_device:
        score += 1

    if is_night:
        score += 1

    if count_1h >= 5:
        score += 3
    elif count_1h >= 3:
        score += 1

    if score > 80:
        return "BLOCK"
    if score >= 3:
        return "REVIEW"
    return "APPROVE"


# ─── Synthetic Training Data ──────────────────────────────────────────────────

def _synthetic_training_data(n: int = 5_000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
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
            amount = rng.uniform(5_000, 25_000)

        hour = int(rng.choice(24, p=hour_weights))
        weekday = int(rng.integers(0, 7))

        currency_risk_value = float(rng.choice([0.0, 0.7], p=[0.95, 0.05]))
        location_risk_value = float(rng.choice([0.0, 0.35, 1.0], p=[0.82, 0.12, 0.06]))
        has_device = bool(rng.choice([True, False], p=[0.90, 0.10]))
        count_1h = int(rng.integers(0, 6))

        currency = "EUR" if currency_risk_value == 0.0 else "XTS"
        if location_risk_value == 1.0:
            location = "IR"
        elif location_risk_value == 0.35:
            location = "NG"
        else:
            location = "DE"

        X_rows.append(
            _build_features(
                amount=amount,
                currency=currency,
                location=location,
                hour=hour,
                weekday=weekday,
                has_device=has_device,
                count_1h=count_1h,
            )
        )

        label = _assign_label(
            amount=amount,
            currency_risk_value=currency_risk_value,
            location_risk_value=location_risk_value,
            has_device=has_device,
            is_night=(hour < 6 or hour >= 22),
            count_1h=count_1h,
        )
        y_rows.append(_LABEL_TO_INT[label])

    return np.vstack(X_rows), np.array(y_rows, dtype=np.int64)


# ─── Scorer Class ─────────────────────────────────────────────────────────────

class XGBoostFraudScorer:
    def __init__(self) -> None:
        logger.info(
            f"[XGB-SCORER] Training XGBoost "
            f"(n_samples=5000, version={MODEL_VERSION})..."
        )

        X, y = _synthetic_training_data(n=5_000)

        self._model = XGBClassifier(
            n_estimators=250,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="multi:softprob",
            num_class=3,
            random_state=42,
            eval_metric="mlogloss",
        )
        self._model.fit(X, y)

        logger.info(f"[XGB-SCORER] Ready. version={MODEL_VERSION}")

    def score(
        self,
        amount: float,
        currency: str,
        location: Optional[str],
        timestamp: datetime,
        device_id: Optional[str],
        count_1h: int = 0,
    ) -> dict:
        features = _build_features(
            amount=amount,
            currency=currency,
            location=location,
            hour=timestamp.hour,
            weekday=timestamp.weekday(),
            has_device=device_id is not None,
            count_1h=count_1h,
        )

        X = features.reshape(1, -1)
        probs = self._model.predict_proba(X)[0]
        pred_idx = int(np.argmax(probs))
        predicted_label = _INT_TO_LABEL[pred_idx]

        approve_prob = float(probs[0])
        review_prob = float(probs[1])
        block_prob = float(probs[2])

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

_scorer: Optional[XGBoostFraudScorer] = None
_scorer_lock = threading.Lock()


def get_xgb_scorer() -> XGBoostFraudScorer:
    global _scorer
    if _scorer is None:
        with _scorer_lock:
            if _scorer is None:
                _scorer = XGBoostFraudScorer()
    return _scorer


def warmup_xgb() -> None:
    get_xgb_scorer() 

    

