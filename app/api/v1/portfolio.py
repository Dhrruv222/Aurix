import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.schemas import PortfolioRequest, PortfolioResponse
from app.db.database import get_db
from app.models.logs import PortfolioLog
from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai_modules.investment_ai.service import compute_recommendation

router = APIRouter()
logger = get_logger(__name__)


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/recommend-portfolio", response_model=PortfolioResponse, summary="AI Portfolio Recommendation")
async def recommend_portfolio(request: PortfolioRequest, db: Session = Depends(get_db)):
    logger.info(
        f"[PORTFOLIO] REQUEST | user_id={request.user_id} "
        f"risk_profile={request.risk_profile} portfolio={request.portfolio}"
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(compute_recommendation, request),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[PORTFOLIO] TIMEOUT | user_id={request.user_id}")
        raise HTTPException(status_code=504, detail="Portfolio recommendation timed out.")
    except Exception:
        logger.exception(f"[PORTFOLIO] ERROR | user_id={request.user_id}")
        raise HTTPException(status_code=500, detail="Internal error during portfolio recommendation.")

    logger.info(
        f"[PORTFOLIO] RESPONSE | user_id={request.user_id} "
        f"allocation={result.recommended_allocation}"
    )

    # ── Persist to DB ──────────────────────────────────────────────────────────
    try:
        log_entry = PortfolioLog(
            user_id=request.user_id,
            input_portfolio=request.portfolio,
            risk_profile=request.risk_profile,
            recommended_allocation=result.recommended_allocation,
            notes=result.notes,
        )
        db.add(log_entry)
        db.commit()
        logger.info(f"[PORTFOLIO] DB LOG SAVED | user_id={request.user_id} id={log_entry.id}")
    except Exception as e:
        db.rollback()
        logger.warning(f"[PORTFOLIO] DB LOG FAILED | {str(e)}")

    return result
