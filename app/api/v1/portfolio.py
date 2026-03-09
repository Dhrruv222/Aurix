import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.schemas import PortfolioRequest, PortfolioResponse
from app.db.database import get_db
from app.models.logs import PortfolioLog
from app.core.config import settings
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ─── Recommendation Logic ─────────────────────────────────────────────────────

RISK_PROFILES = {
    "low":        {"gold": 70, "stocks": 20, "crypto": 10},
    "medium":     {"gold": 55, "stocks": 30, "crypto": 15},
    "high":       {"gold": 30, "stocks": 40, "crypto": 30},
    "aggressive": {"gold": 20, "stocks": 35, "crypto": 45},
}

PROFILE_NOTES = {
    "low":        "Conservative profile → heavy gold allocation for stability.",
    "medium":     "Medium risk profile → balanced allocation across assets.",
    "high":       "High risk profile → increased equity and crypto exposure.",
    "aggressive": "Aggressive profile → maximum growth, higher volatility expected.",
}


def _normalize_allocation(portfolio: dict[str, float]) -> dict[str, float]:
    assets = ("gold", "stocks", "crypto")
    current = {asset: float(portfolio.get(asset, 0.0) or 0.0) for asset in assets}
    total = sum(max(value, 0.0) for value in current.values())
    if total <= 0:
        return {"gold": 33.34, "stocks": 33.33, "crypto": 33.33}

    normalized = {
        asset: round((max(current[asset], 0.0) / total) * 100.0, 2)
        for asset in assets
    }
    drift = round(100.0 - sum(normalized.values()), 2)
    normalized["stocks"] = round(normalized["stocks"] + drift, 2)
    return normalized


def _blend_allocation(current: dict[str, float], target: dict[str, float]) -> dict[str, float]:
    blended = {
        asset: round((target[asset] * 0.7) + (current[asset] * 0.3), 2)
        for asset in ("gold", "stocks", "crypto")
    }
    drift = round(100.0 - sum(blended.values()), 2)
    blended["stocks"] = round(blended["stocks"] + drift, 2)
    return blended


def compute_recommendation(data: PortfolioRequest) -> PortfolioResponse:
    profile = data.risk_profile.lower()

    if profile not in RISK_PROFILES:
        raise ValueError(f"Unknown risk_profile: '{profile}'. Valid: {list(RISK_PROFILES.keys())}")

    current = _normalize_allocation(data.portfolio)
    target = RISK_PROFILES[profile].copy()
    allocation = _blend_allocation(current, target)
    notes = [
        PROFILE_NOTES[profile],
        "Recommendation blends target profile weights (70%) with current allocation (30%).",
    ]

    return PortfolioResponse(
        recommended_allocation=allocation,
        notes=notes,
    )


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
