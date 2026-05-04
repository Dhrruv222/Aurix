"""
app/api/v1/ai/forecast.py
──────────────────────────
POST /v1/ai/forecast-price       — single asset forecast
POST /v1/ai/forecast-price/batch — multi-asset forecast
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.schemas import (
    PriceForecastRequest,
    PriceForecastResponse,
    BatchForecastRequest,
    BatchForecastResponse,
)
from app.services.ai_modules.market_ai.service import forecast_price, batch_forecast

router = APIRouter()
logger = get_logger(__name__)

_MODULE = "market_ai"


@router.post(
    "/forecast-price",
    response_model=PriceForecastResponse,
    summary="AI Price Forecast — Single Asset",
    tags=["Market AI"],
)
async def price_forecast(payload: PriceForecastRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"asset={payload.asset} horizon={payload.horizon_days}d "
        f"price_override={payload.current_price}"
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                forecast_price,
                payload.asset,
                payload.horizon_days,
                payload.current_price,
            ),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id}")
        raise HTTPException(status_code=504, detail="Price forecasting timed out.")
    except Exception:
        logger.exception(f"[{_MODULE.upper()}] ERROR | request_id={request_id}")
        raise HTTPException(status_code=500, detail="Internal error during price forecasting.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} "
        f"module={_MODULE} decision_type=price_forecast "
        f"asset={result['asset']} forecast={result['forecast_price']} trend={result['trend']}"
    )

    return PriceForecastResponse(
        status="success",
        data=result,
        metadata={"request_id": request_id, "module": _MODULE},
    )


@router.post(
    "/forecast-price/batch",
    response_model=BatchForecastResponse,
    summary="AI Price Forecast — Multiple Assets",
    tags=["Market AI"],
)
async def price_forecast_batch(payload: BatchForecastRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] BATCH REQUEST | request_id={request_id} "
        f"assets={payload.assets} horizon={payload.horizon_days}d"
    )

    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(batch_forecast, payload.assets, payload.horizon_days),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[{_MODULE.upper()}] BATCH TIMEOUT | request_id={request_id}")
        raise HTTPException(status_code=504, detail="Batch forecast timed out.")
    except Exception:
        logger.exception(f"[{_MODULE.upper()}] BATCH ERROR | request_id={request_id}")
        raise HTTPException(status_code=500, detail="Internal error during batch forecast.")

    logger.info(
        f"[{_MODULE.upper()}] BATCH RESULT | request_id={request_id} "
        f"assets_forecasted={len(results)}"
    )

    return BatchForecastResponse(
        status="success",
        data={"forecasts": results, "count": len(results)},
        metadata={"request_id": request_id, "module": _MODULE},
    )
