"""
risk_ai/recommendation_engine.py
────────────────────────────────
User-level risk score and recommendation engine for Aurix.

This module is separate from the transaction anomaly / AML / compliance logic
in risk_ai/service.py.

Design goals:
- accept payload features directly (no runtime CSV dependency)
- load a pre-trained Random Forest model from disk
- predict user risk level
- generate explanation and recommendation outputs
- support a combined assessment response for API use
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────

# Assumes the following files will be copied into the AI backend repo:
# data/risk_engine/risk_model.joblib
# data/risk_engine/metrics.json
BASE_DIR = Path(__file__).resolve().parents[4]
RISK_ENGINE_DIR = BASE_DIR / "data" / "risk_engine"
MODEL_PATH = RISK_ENGINE_DIR / "risk_model.joblib"
METRICS_PATH = RISK_ENGINE_DIR / "metrics.json"


# ─── Model / Metadata Loaders ────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_risk_model():
    logger.info(f"[RISK_AI] Loading user risk model from {MODEL_PATH}")
    return joblib.load(MODEL_PATH)


@lru_cache(maxsize=1)
def load_risk_metrics() -> dict[str, Any]:
    logger.info(f"[RISK_AI] Loading user risk metrics from {METRICS_PATH}")
    with open(METRICS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_feature_columns() -> list[str]:
    metrics = load_risk_metrics()
    feature_columns = metrics.get("feature_columns", [])
    if not feature_columns:
        raise ValueError("feature_columns not found in metrics.json")
    return feature_columns


# ─── Feature Preparation ──────────────────────────────────────────────────────

def build_feature_vector(payload: dict[str, Any]):
    """
    Convert a payload dict into a model-ready one-row DataFrame
    using the feature order saved in metrics.json.
    """

    feature_columns = get_feature_columns()

    try:
        row = {col: payload[col] for col in feature_columns}
    except KeyError as exc:
        missing = str(exc).strip("'")
        raise ValueError(f"Missing required feature: {missing}") from exc

    return pd.DataFrame([row], columns=feature_columns)


# ─── Explanation Layer ────────────────────────────────────────────────────────

def build_explanation(payload: dict[str, Any]) -> tuple[str, list[str]]:
    factors: list[str] = []

    if payload["transaction_frequency_weekly"] >= 10:
        factors.append("Very high transaction frequency")
    elif payload["transaction_frequency_weekly"] >= 5:
        factors.append("Above-normal transaction frequency")

    if payload["avg_transaction_amount"] >= 1500:
        factors.append("Large average transaction size")
    elif payload["avg_transaction_amount"] >= 700:
        factors.append("Moderately large transaction size")

    if payload["max_transaction_amount"] >= 7000:
        factors.append("Extremely large single transaction")
    elif payload["max_transaction_amount"] >= 3000:
        factors.append("Large single transaction detected")

    if int(payload["sudden_behavior_change"]) == 1:
        factors.append("Sudden behavioral change detected")

    if int(payload["recent_large_transaction"]) == 1:
        factors.append("Recent large transaction flag raised")

    if int(payload["failed_login_attempts"]) >= 4:
        factors.append("Elevated failed login attempts")

    if int(payload["kyc_review_flag"]) == 1:
        factors.append("KYC review flag present")

    if not factors:
        factors.append("User behavior is stable across key activity indicators")

    explanation = "; ".join(factors) + "."
    return explanation, factors


# ─── Recommendation Layer ─────────────────────────────────────────────────────

def generate_user_recommendation(payload: dict[str, Any], risk_level: str) -> dict[str, str]:
    actions: list[str] = []
    reasons: list[str] = []

    if payload["transaction_frequency_weekly"] >= 8:
        actions.append("Reduce transaction frequency")
        reasons.append("Transaction activity is significantly above the normal user baseline")

    if payload["avg_transaction_amount"] >= 1000 or payload["max_transaction_amount"] >= 5000:
        actions.append("Consider smaller purchases")
        reasons.append("Transaction sizes are large and may require closer monitoring")

    if int(payload["sudden_behavior_change"]) == 1:
        actions.append("Review recent account activity")
        reasons.append("A sudden behavior change may indicate risky or abnormal usage")

    if int(payload["failed_login_attempts"]) >= 4:
        actions.append("Strengthen account security checks")
        reasons.append("Multiple failed login attempts can indicate account access risk")

    if risk_level == "Low risk" and not actions:
        actions = ["User behavior is stable"]
        reasons = ["Current behavior is consistent with a low-risk customer profile"]

    if risk_level == "Medium risk" and not actions:
        actions = ["Monitor transaction behavior"]
        reasons = ["The activity pattern is not critical but should be watched for escalation"]

    if risk_level == "High risk" and not actions:
        actions = ["Escalate for manual review"]
        reasons = ["High-risk users should be reviewed by compliance or operations teams"]

    result = {
        "suggested_action": " | ".join(dict.fromkeys(actions)),
        "recommendation_reason": " | ".join(dict.fromkeys(reasons)),
    }

    logger.info(
        f"[RISK_AI] generate_user_recommendation | user_id={payload.get('user_id')} "
        f"risk_level={risk_level} actions={len(actions)}"
    )

    return result


# ─── Risk Scoring ─────────────────────────────────────────────────────────────

def predict_user_risk(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Predict user level risk using the pre trained Random Forest model.
    """
    model = load_risk_model()
    X = build_feature_vector(payload)

    probabilities = model.predict_proba(X)[0]
    predicted_label = model.predict(X)[0]
    confidence = float(max(probabilities))

    explanation, factors = build_explanation(payload)

    logger.info(
        f"[RISK_AI] predict_user_risk | user_id={payload.get('user_id')} "
        f"risk_level={predicted_label} confidence={confidence:.4f} "
        f"factors={len(factors)}"
    )

    return {
        "user_id": payload["user_id"],
        "risk_level": predicted_label,
        "confidence": round(confidence, 4),
        "explanation": explanation,
        "contributing_factors": factors,
    }


def assess_user_risk_and_recommend(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Combined risk score + recommendation response builder.
    """
    risk_result = predict_user_risk(payload)
    recommendation = generate_user_recommendation(payload, risk_result["risk_level"])

    logger.info(
        f"[RISK_AI] assess_user_risk_and_recommend | user_id={payload.get('user_id')} "
        f"risk_level={risk_result['risk_level']}"
    )

    return {
        "risk_score": risk_result,
        "recommendation": {
            "user_id": payload["user_id"],
            "risk_level": risk_result["risk_level"],
            **recommendation,
        },
    }


def generate_batch_risk_summary(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Build a simple batch summary across multiple user payloads.
    """
    results = [predict_user_risk(payload) for payload in payloads]

    low_count = sum(1 for r in results if r["risk_level"] == "Low risk")
    medium_count = sum(1 for r in results if r["risk_level"] == "Medium risk")
    high_count = sum(1 for r in results if r["risk_level"] == "High risk")

    logger.info(
        f"[RISK_AI] generate_batch_risk_summary | total_users={len(results)} "
        f"low={low_count} medium={medium_count} high={high_count}"
    )

    return {
        "total_users": len(results),
        "low_risk_count": low_count,
        "medium_risk_count": medium_count,
        "high_risk_count": high_count,
        "results": results, 
    }
