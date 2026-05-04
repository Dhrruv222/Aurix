"""
app/api/v1/ai/orchestration.py
───────────────────────────────
POST /v1/ai/route-broker       — smart broker routing (best execution)
POST /v1/ai/optimize-fees      — fee comparison and savings estimate
POST /v1/ai/sync-portfolio     — cross-platform portfolio sync + concentration analysis
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.schemas import (
    BrokerRoutingRequest,
    BrokerRoutingResponse,
    FeeOptimizationRequest,
    FeeOptimizationResponse,
    PortfolioSyncRequest,
    PortfolioSyncResponse,
)
from app.services.ai_modules.orchestration_ai.service import (
    route_broker,
    optimize_fees,
    sync_portfolio_intelligence,
)

router = APIRouter()
logger = get_logger(__name__)

_MODULE = "orchestration_ai"


# ─── Smart Broker Routing ────────────────────────────────────────────────────

@router.post(
    "/route-broker",
    response_model=BrokerRoutingResponse,
    summary="Smart Broker Routing — Best Execution",
    tags=["Orchestration AI"],
)
async def route_broker_endpoint(payload: BrokerRoutingRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} asset={payload.asset_type} "
        f"order_usd={payload.order_size_usd} priority={payload.priority}"
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                route_broker,
                payload.user_id,
                payload.asset_type,
                payload.order_size_usd,
                payload.priority,
                payload.required_kyc_tier,
                payload.user_region,
            ),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id}")
        raise HTTPException(status_code=504, detail="Broker routing timed out.")
    except Exception:
        logger.exception(f"[{_MODULE.upper()}] ERROR | request_id={request_id}")
        raise HTTPException(status_code=500, detail="Internal error during broker routing.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} "
        f"user_id={payload.user_id} recommended={result['recommended_broker']}"
    )

    return BrokerRoutingResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "module": _MODULE,
        },
    )


# ─── Fee Optimization ────────────────────────────────────────────────────────

@router.post(
    "/optimize-fees",
    response_model=FeeOptimizationResponse,
    summary="Fee Optimization — Broker Cost Comparison",
    tags=["Orchestration AI"],
)
async def optimize_fees_endpoint(payload: FeeOptimizationRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} current_broker={payload.current_broker} "
        f"trades={len(payload.planned_trades)}"
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                optimize_fees,
                payload.user_id,
                payload.planned_trades,
                payload.current_broker,
            ),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id}")
        raise HTTPException(status_code=504, detail="Fee optimization timed out.")
    except Exception:
        logger.exception(f"[{_MODULE.upper()}] ERROR | request_id={request_id}")
        raise HTTPException(status_code=500, detail="Internal error during fee optimization.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} "
        f"user_id={payload.user_id} "
        f"savings_usd={result['estimated_savings_usd']} "
        f"savings_pct={result['savings_pct']}"
    )

    return FeeOptimizationResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "module": _MODULE,
        },
    )


# ─── Cross-Platform Portfolio Sync ───────────────────────────────────────────

@router.post(
    "/sync-portfolio",
    response_model=PortfolioSyncResponse,
    summary="Cross-Platform Portfolio Sync & Concentration Analysis",
    tags=["Orchestration AI"],
)
async def sync_portfolio(payload: PortfolioSyncRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"user_id={payload.user_id} "
        f"brokers={list(payload.portfolios_by_broker.keys())}"
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                sync_portfolio_intelligence,
                payload.user_id,
                payload.portfolios_by_broker,
            ),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id}")
        raise HTTPException(status_code=504, detail="Portfolio sync timed out.")
    except Exception:
        logger.exception(f"[{_MODULE.upper()}] ERROR | request_id={request_id}")
        raise HTTPException(status_code=500, detail="Internal error during portfolio sync.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} "
        f"user_id={payload.user_id} total_usd={result['total_value_usd']} "
        f"diversification={result['diversification_score']}"
    )

    return PortfolioSyncResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "user_id": payload.user_id,
            "module": _MODULE,
        },
    )
