"""
app/api/v1/ai/personalization.py
────────────────────────────────────
POST /v1/ai/user-insights  — spending analysis + insights
POST /v1/ai/goal-optimize  — financial goal planning engine
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.schemas import (
    UserInsightsRequest,
    UserInsightsResponse,
    GoalOptimizationRequest,
    GoalOptimizationResponse,
)
from app.services.ai_modules.personalization_ai.service import (
    generate_user_insights,
    analyze_spending_patterns,
    optimize_financial_goal,
)

router = APIRouter()
logger = get_logger(__name__)

_MODULE = "personalization_ai"


@router.post(
    "/user-insights",
    response_model=UserInsightsResponse,
    summary="Personalised Financial Insights + Spending Analysis",
    tags=["Personalization AI"],
)
async def user_insights(payload: UserInsightsRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} module={_MODULE} "
        f"tx_history_count={len(payload.transaction_history)}"
    )

    user_data = {
        "savings_rate": payload.savings_rate,
        "investment_allocation_pct": payload.investment_allocation_pct,
        "gold_value_usd": payload.gold_value_usd,
        "top_spending_category": payload.top_spending_category,
        "monthly_income": payload.monthly_income,
    }

    tx_history = [tx.model_dump() for tx in payload.transaction_history]

    try:
        insights_result, spending_result = await asyncio.gather(
            asyncio.to_thread(generate_user_insights, payload.user_id, user_data),
            asyncio.to_thread(analyze_spending_patterns, payload.user_id, tx_history),
        )
    except asyncio.TimeoutError:
        logger.error(
            f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id} user_id={payload.user_id}"
        )
        raise HTTPException(status_code=504, detail="User insights generation timed out.")
    except Exception:
        logger.exception(
            f"[{_MODULE.upper()}] ERROR | request_id={request_id} user_id={payload.user_id}"
        )
        raise HTTPException(status_code=500, detail="Internal error during user insights generation.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} user_id={payload.user_id} "
        f"module={_MODULE} decision_type=user_insights "
        f"insights={len(insights_result['insights'])} "
        f"trend={spending_result['trend']}"
    )

    return UserInsightsResponse(
        status="success",
        data={
            "insights": insights_result["insights"],
            "recommendations": insights_result["recommendations"],
            "behavior_summary": insights_result["behavior_summary"],
            "spending_analysis": spending_result,
        },
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "module": _MODULE,
            "transactions_analysed": len(payload.transaction_history),
        },
    )


@router.post(
    "/goal-optimize",
    response_model=GoalOptimizationResponse,
    summary="Financial Goal Optimization Engine",
    tags=["Personalization AI"],
)
async def goal_optimize(payload: GoalOptimizationRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] GOAL-OPTIMIZE REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} target={payload.target_amount} "
        f"horizon={payload.time_horizon_months}mo profile={payload.risk_profile}"
    )

    goal_data = {
        "target_amount": payload.target_amount,
        "current_savings": payload.current_savings,
        "monthly_income": payload.monthly_income,
        "monthly_expenses": payload.monthly_expenses,
        "risk_profile": payload.risk_profile,
        "time_horizon_months": payload.time_horizon_months,
    }

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(optimize_financial_goal, payload.user_id, goal_data),
            timeout=settings.SCORING_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error(
            f"[{_MODULE.upper()}] GOAL-OPTIMIZE TIMEOUT | request_id={request_id} "
            f"user_id={payload.user_id}"
        )
        raise HTTPException(status_code=504, detail="Goal optimization timed out.")
    except Exception:
        logger.exception(
            f"[{_MODULE.upper()}] GOAL-OPTIMIZE ERROR | request_id={request_id} "
            f"user_id={payload.user_id}"
        )
        raise HTTPException(status_code=500, detail="Internal error during goal optimization.")

    logger.info(
        f"[{_MODULE.upper()}] GOAL-OPTIMIZE RESULT | request_id={request_id} "
        f"user_id={payload.user_id} module={_MODULE} decision_type=goal_optimization "
        f"required_monthly={result['required_monthly_savings']} "
        f"achievable={result['is_achievable']}"
    )

    return GoalOptimizationResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "module": _MODULE,
            "risk_profile": payload.risk_profile,
            "time_horizon_months": payload.time_horizon_months,
        },
    )
