import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.schemas.schemas import FraudScoreRequest, FraudScoreResponse
from app.db.database import get_db
from app.models.logs import FraudLog
from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai_modules.core_ai.service import compute_fraud_score

router = APIRouter()
logger = get_logger(__name__)


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/fraud-score", response_model=FraudScoreResponse, summary="Evaluate Transaction Risk")
async def fraud_score(payload: FraudScoreRequest, request: Request, db: Session = Depends(get_db)):
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        f"[FRAUD-SCORE] REQUEST | request_id={request_id} user_id={payload.user_id} "
        f"amount={payload.amount} {payload.currency} "
        f"location={payload.location} device={payload.device_id or 'N/A'}"
    )

    try:
        # Timeout protection — scoring must complete within configured limit
        result = await asyncio.wait_for(
            asyncio.to_thread(compute_fraud_score, payload, request_id),
            timeout=settings.SCORING_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error(f"[FRAUD-SCORE] TIMEOUT | request_id={request_id} user_id={payload.user_id}")
        raise HTTPException(status_code=504, detail="Fraud scoring timed out. Please retry.")
    except Exception:
        logger.exception(f"[FRAUD-SCORE] ERROR | request_id={request_id} user_id={payload.user_id}")
        raise HTTPException(status_code=500, detail="Internal error during fraud scoring.")

    logger.info(
        f"[FRAUD-SCORE] RESPONSE | request_id={request_id} user_id={payload.user_id} "
        f"risk_score={result.risk_score} decision={result.decision}"
    )

    # ── Persist to DB ──────────────────────────────────────────────────────────
    try:
        log_entry = FraudLog(
            request_id=request_id,
            user_id=payload.user_id,
            amount=payload.amount,
            currency=payload.currency,
            device_id=payload.device_id,
            location=payload.location,
            risk_score=result.risk_score,
            decision=result.decision,
            reasons=result.reasons,
            timestamp=payload.timestamp,
        )
        db.add(log_entry)
        db.commit()
        logger.info(
            f"[FRAUD-SCORE] DB LOG SAVED | request_id={request_id} "
            f"user_id={payload.user_id} id={log_entry.id} decision={result.decision}"
        )
    except Exception as e:
        db.rollback()
        # Don't fail the request if DB logging fails — just warn
        logger.warning(
            f"[FRAUD-SCORE] DB LOG FAILED | request_id={request_id} "
            f"user_id={payload.user_id} error={str(e)}"
        )

    return result
