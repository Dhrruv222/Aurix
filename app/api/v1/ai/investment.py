"""
app/api/v1/ai/investment.py
────────────────────────────
POST /v1/ai/optimize-portfolio   — portfolio optimization with insights
POST /v1/ai/rebalance-portfolio  — smart drift-based rebalancing plan
POST /v1/ai/score-project        — crowdfunding / startup project scoring

Enhanced portfolio optimization with optimization insights via investment_ai service.
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.schemas import (
    OptimizePortfolioRequest,
    OptimizePortfolioResponse,
    PortfolioRequest,
    RebalanceRequest,
    RebalanceResponse,
    CrowdfundingScoreRequest,
    CrowdfundingScoreResponse,
)
from app.services.ai_modules.investment_ai.service import (
    compute_recommendation,
    compute_rebalancing_plan,
    score_crowdfunding_project,
    RISK_PROFILES,
    normalize_allocation,
)

router = APIRouter()
logger = get_logger(__name__)

_MODULE = "investment_ai"

_ASSETS = ("gold", "stocks", "crypto")


def _generate_optimization_insights(
    current: dict,
    recommended: dict,
    risk_profile: str,
    horizon_months: int | None,
    target_return_pct: float | None,
) -> list[str]:
    """
    Derive human-readable optimization insights by comparing current vs
    recommended allocation.

    TODO (ML): Replace with Markowitz mean-variance optimizer or RL-based
    rebalancing engine that incorporates live price data and covariance matrix.
    """
    insights: list[str] = []
    target = RISK_PROFILES.get(risk_profile, {})

    for asset in _ASSETS:
        current_pct = current.get(asset, 0.0)
        recommended_pct = recommended.get(asset, 0.0)
        target_pct = target.get(asset, 0.0)
        delta = round(recommended_pct - current_pct, 2)

        if abs(delta) >= 3.0:
            direction = "Increase" if delta > 0 else "Decrease"
            insights.append(
                f"{direction} {asset} by {abs(delta):.1f}% "
                f"(current {current_pct:.1f}% → recommended {recommended_pct:.1f}%, "
                f"target {target_pct:.1f}%)."
            )

    if horizon_months and horizon_months >= 24:
        insights.append(
            f"Long investment horizon ({horizon_months} months) — "
            "consider holding through short-term volatility."
        )

    if target_return_pct and target_return_pct > 15.0 and risk_profile in ("low", "medium"):
        insights.append(
            f"Target return {target_return_pct:.1f}% may require a higher risk profile than '{risk_profile}'."
        )

    if not insights:
        insights.append("Portfolio is closely aligned with the target profile — minimal rebalancing needed.")

    return insights


@router.post(
    "/optimize-portfolio",
    response_model=OptimizePortfolioResponse,
    summary="AI Portfolio Optimization with Insights",
    tags=["Investment AI"],
)
async def optimize_portfolio(payload: OptimizePortfolioRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} module={_MODULE} "
        f"risk_profile={payload.risk_profile} portfolio={payload.portfolio}"
    )

    # Build a PortfolioRequest-compatible object for the existing service
    portfolio_req = PortfolioRequest(
        user_id=payload.user_id,
        portfolio=payload.portfolio,
        risk_profile=payload.risk_profile,
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(compute_recommendation, portfolio_req),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(
            f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id} user_id={payload.user_id}"
        )
        raise HTTPException(status_code=504, detail="Portfolio optimization timed out.")
    except Exception:
        logger.exception(
            f"[{_MODULE.upper()}] ERROR | request_id={request_id} user_id={payload.user_id}"
        )
        raise HTTPException(status_code=500, detail="Internal error during portfolio optimization.")

    current_normalized = normalize_allocation(payload.portfolio)
    insights = _generate_optimization_insights(
        current=current_normalized,
        recommended=result.recommended_allocation,
        risk_profile=payload.risk_profile,
        horizon_months=payload.investment_horizon_months,
        target_return_pct=payload.target_return_pct,
    )

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} user_id={payload.user_id} "
        f"module={_MODULE} decision_type=portfolio_optimization "
        f"allocation={result.recommended_allocation}"
    )

    return OptimizePortfolioResponse(
        status="success",
        data={
            "recommended_allocation": result.recommended_allocation,
            "notes": result.notes,
            "optimization_insights": insights,
        },
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "risk_profile": payload.risk_profile,
            "module": _MODULE,
            "investment_horizon_months": payload.investment_horizon_months,
            "target_return_pct": payload.target_return_pct,
        },
    )


# ─── Rebalancing Endpoint ─────────────────────────────────────────────────────

@router.post(
    "/rebalance-portfolio",
    response_model=RebalanceResponse,
    summary="Smart Portfolio Rebalancing Plan",
    tags=["Investment AI"],
)
async def rebalance_portfolio(payload: RebalanceRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} action=rebalance "
        f"risk_profile={payload.risk_profile}"
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                compute_rebalancing_plan,
                payload.user_id,
                payload.portfolio_values_usd,
                payload.risk_profile,
            ),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id}")
        raise HTTPException(status_code=504, detail="Rebalancing computation timed out.")
    except Exception:
        logger.exception(f"[{_MODULE.upper()}] ERROR | request_id={request_id}")
        raise HTTPException(status_code=500, detail="Internal error during rebalancing.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} "
        f"user_id={payload.user_id} rebalance_needed={result['rebalance_needed']} "
        f"trades={len(result['trades'])}"
    )

    return RebalanceResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "risk_profile": payload.risk_profile,
            "module": _MODULE,
        },
    )


# ─── Crowdfunding Scoring Endpoint ────────────────────────────────────────────

@router.post(
    "/score-project",
    response_model=CrowdfundingScoreResponse,
    summary="Crowdfunding / Startup Project Scoring",
    tags=["Investment AI"],
)
async def score_project(payload: CrowdfundingScoreRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    project_data = payload.model_dump(exclude={"user_id"})

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} action=score_project "
        f"sector={payload.sector}"
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                score_crowdfunding_project,
                payload.user_id,
                project_data,
            ),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id}")
        raise HTTPException(status_code=504, detail="Project scoring timed out.")
    except Exception:
        logger.exception(f"[{_MODULE.upper()}] ERROR | request_id={request_id}")
        raise HTTPException(status_code=500, detail="Internal error during project scoring.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} "
        f"user_id={payload.user_id} grade={result['grade']} "
        f"score={result['composite_score']} recommendation={result['recommendation']}"
    )

    return CrowdfundingScoreResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "module": _MODULE,
        },
    )
