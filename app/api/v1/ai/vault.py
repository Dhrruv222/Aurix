"""
app/api/v1/ai/vault.py
───────────────────────
POST /v1/ai/vault-forecast        — inventory depletion forecast
POST /v1/ai/redemption-forecast   — demand prediction for physical redemptions
POST /v1/ai/supply-chain-check    — shipment anomaly detection
"""

import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.schemas import (
    VaultForecastRequest,
    VaultForecastResponse,
    RedemptionForecastRequest,
    RedemptionForecastResponse,
    SupplyChainCheckRequest,
    SupplyChainCheckResponse,
)
from app.services.ai_modules.vault_ai.service import (
    forecast_inventory,
    predict_redemption_demand,
    detect_supply_chain_anomaly,
)

router = APIRouter()
logger = get_logger(__name__)

_MODULE = "vault_ai"


# ─── Vault Inventory Forecast ─────────────────────────────────────────────────

@router.post(
    "/vault-forecast",
    response_model=VaultForecastResponse,
    summary="Vault Inventory Depletion Forecast",
    tags=["Vault AI"],
)
async def vault_forecast(payload: VaultForecastRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"vault_id={payload.vault_id} "
        f"stock={payload.current_stock_kg}kg horizon={payload.horizon_days}d"
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                forecast_inventory,
                payload.vault_id,
                payload.current_stock_kg,
                payload.recent_daily_outflows,
                payload.horizon_days,
                payload.seasonality_factor,
            ),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id}")
        raise HTTPException(status_code=504, detail="Vault forecast timed out.")
    except Exception:
        logger.exception(f"[{_MODULE.upper()}] ERROR | request_id={request_id}")
        raise HTTPException(status_code=500, detail="Internal error during vault forecast.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} "
        f"vault_id={payload.vault_id} status={result['stock_status']} "
        f"reorder={result['reorder_recommended']}"
    )

    return VaultForecastResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "vault_id": payload.vault_id,
            "module": _MODULE,
        },
    )


# ─── Redemption Demand Forecast ───────────────────────────────────────────────

@router.post(
    "/redemption-forecast",
    response_model=RedemptionForecastResponse,
    summary="Physical Redemption Demand Prediction",
    tags=["Vault AI"],
)
async def redemption_forecast(payload: RedemptionForecastRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"asset={payload.asset} horizon={payload.horizon_days}d "
        f"price_trend={payload.price_trend}"
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                predict_redemption_demand,
                payload.asset,
                payload.recent_daily_requests,
                payload.horizon_days,
                payload.price_trend,
            ),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id}")
        raise HTTPException(status_code=504, detail="Redemption forecast timed out.")
    except Exception:
        logger.exception(f"[{_MODULE.upper()}] ERROR | request_id={request_id}")
        raise HTTPException(status_code=500, detail="Internal error during redemption forecast.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} "
        f"asset={payload.asset} forecast={result['trend_adjusted_forecast']} "
        f"confidence={result['confidence']}"
    )

    return RedemptionForecastResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "asset": payload.asset,
            "module": _MODULE,
        },
    )


# ─── Supply Chain Anomaly Check ───────────────────────────────────────────────

@router.post(
    "/supply-chain-check",
    response_model=SupplyChainCheckResponse,
    summary="Supply Chain Shipment Anomaly Detection",
    tags=["Vault AI"],
)
async def supply_chain_check(payload: SupplyChainCheckRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)

    logger.info(
        f"[{_MODULE.upper()}] REQUEST | request_id={request_id} "
        f"shipment_id={payload.shipment_id} "
        f"carrier={payload.carrier} "
        f"origin={payload.origin_country}→{payload.destination_country}"
    )

    shipment_data = payload.model_dump(exclude={"shipment_id"})

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                detect_supply_chain_anomaly,
                payload.shipment_id,
                shipment_data,
            ),
            timeout=settings.SCORING_TIMEOUT,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except asyncio.TimeoutError:
        logger.error(f"[{_MODULE.upper()}] TIMEOUT | request_id={request_id}")
        raise HTTPException(status_code=504, detail="Supply chain check timed out.")
    except Exception:
        logger.exception(f"[{_MODULE.upper()}] ERROR | request_id={request_id}")
        raise HTTPException(status_code=500, detail="Internal error during supply chain check.")

    logger.info(
        f"[{_MODULE.upper()}] RESULT | request_id={request_id} "
        f"shipment_id={payload.shipment_id} "
        f"anomaly={result['anomaly_detected']} score={result['anomaly_score']} "
        f"action={result['recommended_action']}"
    )

    return SupplyChainCheckResponse(
        status="success",
        data=result,
        metadata={
            "request_id": request_id,
            "shipment_id": payload.shipment_id,
            "module": _MODULE,
        },
    )
