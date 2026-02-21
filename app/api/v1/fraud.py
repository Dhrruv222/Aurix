import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.schemas import FraudScoreRequest, FraudScoreResponse
from app.db.database import get_db
from app.models.logs import FraudLog
from app.core.config import settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)
HIGH_RISK_COUNTRIES = frozenset({"NG", "KP", "IR", "SY"})


# ─── Scoring Logic ────────────────────────────────────────────────────────────

def compute_fraud_score(data: FraudScoreRequest) -> FraudScoreResponse:
    """
    MVP rule-based fraud scoring.
    Phase 2 will replace this with an ML model (Random Forest / XGBoost).
    """
    risk_score = 0.0
    reasons = []

    # Rule 1: High transaction amount
    if data.amount >= settings.HIGH_RISK_AMOUNT:
        risk_score += 60
        reasons.append(f"Very high transaction amount: {data.amount} {data.currency}")
    elif data.amount >= settings.MEDIUM_RISK_AMOUNT:
        risk_score += 30
        reasons.append(f"High transaction amount: {data.amount} {data.currency}")

    # Rule 2: High-risk location (placeholder list — expand in Phase 2)
    if data.location and data.location.upper() in HIGH_RISK_COUNTRIES:
        risk_score += 40
        reasons.append(f"Transaction from high-risk country: {data.location}")

    # Rule 3: Missing device ID (suspicious)
    if not data.device_id or data.device_id.strip() == "":
        risk_score += 20
        reasons.append("No device ID provided")

    # Cap at 100
    risk_score = min(risk_score, 100.0)

    if not reasons:
        reasons.append("No risk signals detected (MVP rules)")

    # Decision thresholds
    if risk_score >= 70:
        decision = "BLOCK"
    elif risk_score >= 30:
        decision = "REVIEW"
    else:
        decision = "APPROVE"

    return FraudScoreResponse(
        risk_score=risk_score,
        decision=decision,
        reasons=reasons,
    )


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/fraud-score", response_model=FraudScoreResponse, summary="Evaluate Transaction Risk")
async def fraud_score(request: FraudScoreRequest, db: Session = Depends(get_db)):
    logger.info(
        f"[FRAUD-SCORE] REQUEST | user_id={request.user_id} "
        f"amount={request.amount} {request.currency} "
        f"location={request.location} device={request.device_id or 'N/A'}"
    )

    try:
        # Timeout protection — scoring must complete within configured limit
        result = await asyncio.wait_for(
            asyncio.to_thread(compute_fraud_score, request),
            timeout=settings.SCORING_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error(f"[FRAUD-SCORE] TIMEOUT | user_id={request.user_id}")
        raise HTTPException(status_code=504, detail="Fraud scoring timed out. Please retry.")
    except Exception:
        logger.exception(f"[FRAUD-SCORE] ERROR | user_id={request.user_id}")
        raise HTTPException(status_code=500, detail="Internal error during fraud scoring.")

    logger.info(
        f"[FRAUD-SCORE] RESPONSE | user_id={request.user_id} "
        f"risk_score={result.risk_score} decision={result.decision}"
    )

    # ── Persist to DB ──────────────────────────────────────────────────────────
    try:
        log_entry = FraudLog(
            user_id=request.user_id,
            amount=request.amount,
            currency=request.currency,
            device_id=request.device_id,
            location=request.location,
            risk_score = result.risk_score,
            decision=result.decision,
            reasons=result.reasons,
            timestamp=request.timestamp.isoformat(),
        )
        db.add(log_entry)
        db.commit()
        logger.info(f"[FRAUD-SCORE] DB LOG SAVED | user_id={request.user_id} id={log_entry.id}")
    except Exception as e:
        db.rollback()
        # Don't fail the request if DB logging fails — just warn
        logger.warning(f"[FRAUD-SCORE] DB LOG FAILED | {str(e)}")

    return result
