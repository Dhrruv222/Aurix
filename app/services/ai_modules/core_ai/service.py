"""
core_ai/service.py
──────────────────
Central fraud detection and transaction risk scoring engine.

Phase 2: Multi-signal rule-based scoring system.

Five independent signal analysers each return a typed SignalResult dict:
    {"score": float, "reason": str}

Signals are aggregated into a single risk_score (0–100).  The decision
thresholds are:
    BLOCK  — risk_score >= 80
    REVIEW — risk_score >= 50
    APPROVE — below 50

ML toggle: set USE_ML_MODEL=true in .env to route through compute_fraud_score_ml().
"""

from datetime import datetime
from typing import TypedDict

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.schemas import FraudScoreRequest, FraudScoreResponse
from app.services.velocity_tracker import velocity_tracker
from app.services.ai_modules.core_ai.ml_scorer import get_ml_scorer
from app.services.ai_modules.core_ai.xgb_scorer import get_xgb_scorer 


logger = get_logger(__name__)

# ─── Reference Data ────────────────────────────────────────────────────────────

_KNOWN_CURRENCIES: frozenset[str] = frozenset({"EUR", "USD", "GBP", "CHF", "SGD"})

# OFAC / FATF high-risk jurisdictions (static stub — replace with live API)
_HIGH_RISK_LOCATIONS: frozenset[str] = frozenset({"KP", "IR", "SY", "CU", "SD", "MM"})
_MEDIUM_RISK_LOCATIONS: frozenset[str] = frozenset({"NG", "PK", "VN", "UA", "KZ", "YE", "LY"})

# aligned MVP decision bands:
# 0–30  -> allow
# 31–60 -> allow + log
# 61–80 -> step-up verification
# >80   -> freeze temporarily

# Since the current API supports only APPROVE / REVIEW / BLOCK:
# - APPROVE covers 0–30
# - REVIEW covers 31–80
# - BLOCK covers >80
_BLOCK_THRESHOLD: float = 81.0
_REVIEW_THRESHOLD: float = 31.0

# ─── Signal Result Type ────────────────────────────────────────────────────────

class SignalResult(TypedDict):
    score: float    # contribution to overall risk_score (0–100 scale)
    reason: str     # human-readable explanation; empty string if no risk found


# ─── Signal 1: Amount ─────────────────────────────────────────────────────────

def analyze_amount_risk(amount: float, currency: str) -> SignalResult:
    """
    Evaluate transaction amount against configurable thresholds.

    - >= 5,000  -> medium risk
    - >= 20,000 -> high risk

    Score contributions:
      > HIGH_RISK_AMOUNT  → 40 pts 
      > MEDIUM_RISK_AMOUNT → 25 pts
      otherwise            →  0 pts

    TODO (ML): replace fixed bands with a continuous model trained on
    historical transaction distributions per currency / user segment.
    """
    if amount >= settings.HIGH_RISK_AMOUNT:
        return {
            "score": 40.0,
            "reason": (
                f"High-value transfer: {amount:.2f} {currency} exceeds "
                f"the high-risk threshold ({settings.HIGH_RISK_AMOUNT:.2f})."
            ),
        }

    if amount >= settings.MEDIUM_RISK_AMOUNT:
        return {
            "score": 25.0,
            "reason": (
                f"Medium-risk transfer: {amount:.2f} {currency} exceeds "
                f"the medium-risk threshold ({settings.MEDIUM_RISK_AMOUNT:.2f})."
            ),
        }
    return {"score": 0.0, "reason": ""}


# ─── Signal 2: Currency ───────────────────────────────────────────────────────

def analyze_currency_risk(currency: str) -> SignalResult:
    """
    Flag transactions in currencies outside the known/accepted set.

    Score contribution: 10 pts for unknown currency.

    TODO (ML): weight by per-currency fraud rate derived from historical data.
    """
    if currency.upper() not in _KNOWN_CURRENCIES:
        return {
            "score": 10.0,
            "reason": f"Unusual or unsupported currency: {currency}.",
        }
    return {"score": 0.0, "reason": ""}


# ─── Signal 3: Location ───────────────────────────────────────────────────────

def analyze_location_risk(location: str | None) -> SignalResult:
    """
    Evaluate geographic risk based on country code.

    Score contributions:
      Missing location      → 12 pts
      High-risk jurisdiction → 30 pts
      Medium-risk jurisdiction → 15 pts
      otherwise              →  0 pts

    TODO (ML): integrate real-time geo-IP enrichment, OFAC/EU sanctions
    API, and a per-country risk model trained on transaction fraud rates.
    """
    if location is None:
        return {
            "score": 12.0,
            "reason": "Location unknown — geographic risk cannot be assessed.",
        }

    loc = location.upper()
    if loc in _HIGH_RISK_LOCATIONS:
        return {
            "score": 30.0,
            "reason": f"Transaction originates from high-risk jurisdiction: {loc}.",
        }
    if loc in _MEDIUM_RISK_LOCATIONS:
        return {
            "score": 15.0,
            "reason": f"Transaction originates from medium-risk jurisdiction: {loc}.",
        }
    return {"score": 0.0, "reason": ""}


# ─── Signal 4: Device ─────────────────────────────────────────────────────────

def analyze_device_risk(device_id: str | None) -> SignalResult:
    """
    Evaluate device-level risk signals.

    Score contributions:
      Missing device_id → 10 pts  (anonymous / no fingerprint)
      otherwise          →  0 pts  (known device, assume clean)

    TODO (ML): query device reputation store (Sardine / Seon / custom),
    check velocity (transactions per device in last 24 h), and apply a
    device-trust score derived from historical behaviour.
    """
    if device_id is None:
        return {
            "score": 10.0,
            "reason": "No device ID — transaction is from an anonymous session.",
        }
    return {"score": 0.0, "reason": ""}


# ─── Signal 5: Velocity ───────────────────────────────────────────────────────

def analyze_velocity_risk(user_id: str, amount: float, timestamp: datetime) -> SignalResult:
    """
    -aligned MVP velocity rules.
    Clean separation:
    - 1-minute burst detection
    - 1-hour velocity detection
    - 24-hour elevated frequency

    Important:
    The current transaction is included in the evaluation window so that:
    - the 5th transfer in 1 minute triggers the 1-minute rule
    - the 6th transfer in 1 hour triggers the 1-hour rule
    """
    v = velocity_tracker.get_signals(user_id, timestamp)

    # Include the current transaction in this evaluation
    current_large = 1 if amount >= settings.MEDIUM_RISK_AMOUNT else 0

    count_1m = v["count_1m"] + 1
    count_1h = v["count_1h"] + 1
    count_24h = v["count_24h"] + 1

    amount_1h = v["amount_1h"] + amount
    amount_24h = v["amount_24h"] + amount

    large_count_1m = v["large_count_1m"] + current_large
    large_count_1h = v["large_count_1h"] + current_large
    large_count_24h = v["large_count_24h"] + current_large

    # Rule thresholds
    high_count_1m = count_1m >= 5          # 5 transfers in 1 minute
    high_count_1h = count_1h >= 6          # 6 transfers in 1 hour
    high_count_24h = count_24h >= 20

    repeated_large_1m = large_count_1m >= 2
    repeated_large_1h = large_count_1h >= 2
    repeated_large_24h = large_count_24h >= 3

    high_amount_1h = amount_1h >= 50_000.0
    high_amount_24h = amount_24h >= 200_000.0

    score = 0.0
    reason_parts: list[str] = []

    # ── 1-minute burst rules ──────────────────────────────────────────────────
    if high_count_1m:
        score += 35.0
        reason_parts.append(
            f"High velocity: {count_1m} transfers in the last minute."
        )

    if repeated_large_1m:
        score += 20.0
        reason_parts.append(
            f"Repeated large transfers: {large_count_1m} transfers "
            f">= {settings.MEDIUM_RISK_AMOUNT:.0f} in the last minute."
        )

    # ── 1-hour rules (only when 1-minute burst is NOT active) ────────────────
    if high_count_1h and not high_count_1m:
        score += 10.0
        reason_parts.append(
            f"High velocity: {count_1h} transactions in the last hour."
        )

    if repeated_large_1h and not repeated_large_1m:
        score += 15.0
        reason_parts.append(
            f"Repeated large transfers: {large_count_1h} transfers "
            f">= {settings.MEDIUM_RISK_AMOUNT:.0f} in the last hour."
        )

    # ── 24-hour rules (only when shorter windows are not active) ─────────────
    if high_count_24h and not high_count_1h and not high_count_1m:
        score += 8.0
        reason_parts.append(
            f"Elevated frequency: {count_24h} transactions in the last 24 hours."
        )

    if repeated_large_24h and not repeated_large_1h and not repeated_large_1m:
        score += 10.0
        reason_parts.append(
            f"Repeated large transfers: {large_count_24h} transfers "
            f">= {settings.MEDIUM_RISK_AMOUNT:.0f} in the last 24 hours."
        )

    # ── Amount-based velocity ─────────────────────────────────────────────────
    if high_amount_1h:
        score += 10.0
        reason_parts.append(
            f"High amount velocity: {amount_1h:.2f} in the last hour."
        )

    if high_amount_24h and not high_amount_1h:
        score += 8.0
        reason_parts.append(
            f"Elevated daily volume: {amount_24h:.2f} in the last 24 hours."
        )

    return {
        "score": min(score, 45.0),
        "reason": " ".join(reason_parts) if reason_parts else "",
    }

# ─── Aggregator ───────────────────────────────────────────────────────────────

def _aggregate_signals(signals: dict[str, SignalResult]) -> tuple[float, list[str]]:
    """
    Sum all signal scores and collect non-empty reasons.

    Returns:
        risk_score: clamped to [0, 100]
        reasons: list of active risk factor descriptions
    """
    total = sum(s["score"] for s in signals.values())
    reasons = [s["reason"] for s in signals.values() if s["reason"]]
    risk_score = round(min(max(total, 0.0), 100.0), 2)
    return risk_score, reasons


def _derive_decision(risk_score: float) -> str:
    if risk_score >= _BLOCK_THRESHOLD:
        return "BLOCK"
    if risk_score >= _REVIEW_THRESHOLD:
        return "REVIEW"
    return "APPROVE"


# ─── Core Rule-Based Scorer ────────────────────────────────────────────────────

def compute_fraud_score( data: FraudScoreRequest, request_id: str | None = None,) -> FraudScoreResponse:
    """
    Multi-signal rule-based fraud scorer (Phase 2).

    Five signals are evaluated independently then aggregated:
      1. Amount      — transaction size vs configurable thresholds
      2. Currency    — known vs unusual currency
      3. Location    — country-level jurisdiction risk
      4. Device      — device identity / fingerprint presence
      5. Velocity    — transaction frequency (stub — Phase 3)

    Decision thresholds:
      APPROVE  — risk_score <  50
      REVIEW   — risk_score >= 50
      BLOCK    — risk_score >= 80

    Routes through compute_fraud_score_ml() when settings.USE_ML_MODEL is True.
    """
    if settings.USE_ML_MODEL:
        return compute_fraud_score_ml(data, request_id=request_id)

    # ── Run all signal analysers ───────────────────────────────────────────────
    signals: dict[str, SignalResult] = {
        "amount":   analyze_amount_risk(data.amount, data.currency),
        "currency": analyze_currency_risk(data.currency),
        "location": analyze_location_risk(data.location),
        "device":   analyze_device_risk(data.device_id),
        "velocity": analyze_velocity_risk(data.user_id, data.amount, data.timestamp),

    }

    # ── Per-signal logging ────────────────────────────────────────────────────
    logger.info(
        f"[CORE_AI] SIGNALS | request_id={request_id} user_id={data.user_id} "
        f"amount_score={signals['amount']['score']} "
        f"currency_score={signals['currency']['score']} "
        f"location_score={signals['location']['score']} "
        f"device_score={signals['device']['score']} "
        f"velocity_score={signals['velocity']['score']}"
    )

    # ── Aggregate ─────────────────────────────────────────────────────────────
    risk_score, reasons = _aggregate_signals(signals)
    decision = _derive_decision(risk_score)

    if not reasons:
        reasons.append(
            f"Amount {data.amount:.2f} {data.currency} — "
            "no risk signals detected across all checks."
        )

    logger.info(
        f"[CORE_AI] RESULT | request_id={request_id} user_id={data.user_id} "
        f"module=core_ai decision_type=fraud_score "
        f"risk_score={risk_score} decision={decision} active_signals={len(reasons)}"
    )

    # Record velocity for non-blocked transactions so future checks reflect this tx
    if decision != "BLOCK":
        velocity_tracker.record(data.user_id, data.amount, data.timestamp)

    return FraudScoreResponse(
        risk_score=risk_score,
        decision=decision,
        reasons=reasons,
    )


# XGBoost Scorer Hook (Phase 3)
def _run_xgboost_shadow( data: FraudScoreRequest, count_1h: int, request_id: str | None = None,) -> None:
    """
    Run XGBoost in shadow mode for future evaluation only.

    This does NOT affect the live fraud decision.
    It only logs the XGBoost output when USE_XGBOOST_SHADOW=True.
    """
    if not settings.USE_XGBOOST_SHADOW:
        return

    try:
        xgb_result = get_xgb_scorer().score(
            amount=data.amount,
            currency=data.currency,
            location=data.location,
            timestamp=data.timestamp,
            device_id=data.device_id,
            count_1h=count_1h,
        )

        logger.info(
            f"[CORE_AI] XGB_SHADOW | request_id={request_id} user_id={data.user_id} "
            f"xgb_score={xgb_result['ml_score']} "
            f"predicted_label={xgb_result['predicted_label']} "
            f"model_version={xgb_result['model_version']} "
            f"probabilities={xgb_result['probabilities']}"
        )
    except Exception:
        logger.exception(
            f"[CORE_AI] XGB_SHADOW_ERROR | request_id={request_id} user_id={data.user_id}"
        )

# ─── ML Hook ──────────────────────────────────────────────────────────────────

def compute_fraud_score_ml(data: FraudScoreRequest, request_id: str | None = None,) -> FraudScoreResponse:
    """
    ML-powered fraud scorer — activated when settings.USE_ML_MODEL=True.

    Ensemble design:
      - Isolation Forest anomaly score  (60% weight)
      - Rule-based signal aggregate     (40% weight)

    The rule-based signals still run in full so that their reasons are included
    in the response for transparency / audit. The ML score provides the
    multi-variate anomaly component that rules cannot capture alone.

    Velocity signals are read before scoring and the transaction is recorded
    after a non-BLOCK decision (same behaviour as the rule-based path).
    """
    # ── 1. Velocity signals ───────────────────────────────────────────────────
    v = velocity_tracker.get_signals(data.user_id, data.timestamp)

    # ── XGBoost shadow mode for future use only, no impact on live decision
    _run_xgboost_shadow(
        data=data,
        count_1h=v["count_1h"],
        request_id=request_id,
    )


    # ── 2. ML anomaly score ───────────────────────────────────────────────────
    ml_result = get_ml_scorer().score(
        amount=data.amount,
        currency=data.currency,
        location=data.location,
        timestamp=data.timestamp,
        device_id=data.device_id,
        count_1h=v["count_1h"],
    )

    # ── 3. Rule-based signals (for overlay reasons + 40% weight) ──────────────
    rule_signals: dict[str, SignalResult] = {
        "amount":   analyze_amount_risk(data.amount, data.currency),
        "currency": analyze_currency_risk(data.currency),
        "location": analyze_location_risk(data.location),
        "device":   analyze_device_risk(data.device_id),
        "velocity": analyze_velocity_risk(data.user_id, data.amount, data.timestamp), 
    }
    rule_score, rule_reasons = _aggregate_signals(rule_signals)

    # ── 4. Ensemble blend ─────────────────────────────────────────────────────
    blended_score = round(
        ml_result["anomaly_score"] * 0.60 + rule_score * 0.40,
        2,
    )
    blended_score = max(0.0, min(100.0, blended_score))

    # Reasons
    # ── 5. Build reasons ──────────────────────────────────────────────────────

    # Reasons
    reasons: list[str] = []
    sigs = ml_result["signals"]

    if ml_result["is_anomaly"]:
        reasons.append(
            f"ML anomaly detector flagged this transaction "
            f"(score: {ml_result['anomaly_score']:.1f}/100, "
            f"model: {ml_result['model_version']})."
        )

    if sigs["is_night"]:
        reasons.append("Transaction during off-hours (night time).")
    if sigs["currency_risk"] > 0:
        reasons.append(f"Currency {data.currency} is outside the trusted set.")
    if sigs["location_risk"] >= 0.7:
        reasons.append(f"Elevated location risk: {data.location or 'unknown'}.")
    if not sigs["has_device"]:
        reasons.append("No device fingerprint — anonymous session.")

    reasons.extend(rule_reasons)

    if not reasons:
        reasons.append("No significant risk signals detected.")
        
    decision = _derive_decision(blended_score)

    logger.info(
        f"[CORE_AI] ML_RESULT | request_id={request_id} user_id={data.user_id} "
        f"ml_score={ml_result['anomaly_score']} rule_score={rule_score} "
        f"blended={blended_score} decision={decision}"
    )

    if decision != "BLOCK":
        velocity_tracker.record(data.user_id, data.amount, data.timestamp)

    return FraudScoreResponse(
        risk_score=blended_score,
        decision=decision,
        reasons=reasons,
    )

    # ── 6. Decision ───────────────────────────────────────────────────────────
    decision = _derive_decision(blended_score)

    logger.info(
        f"[CORE_AI] ML_RESULT | request_id={request_id} user_id={data.user_id} "
        f"ml_score={ml_result['anomaly_score']} rule_score={rule_score} "
        f"blended={blended_score} decision={decision}"
    )

    # ── 7. Record velocity for non-blocked transactions ───────────────────────
    if decision != "BLOCK":
        velocity_tracker.record(data.user_id, data.amount, data.timestamp)

    return FraudScoreResponse(
        risk_score=blended_score,
        decision=decision,
        reasons=reasons,
    )