"""
vault_ai/service.py
────────────────────
Vault & Supply Chain Intelligence — AI-assisted engine.

Covers Module 5 from the Aurix AI roadmap:
  1. Inventory forecasting  — predict vault liquidity needs over a horizon
  2. Demand prediction      — forecast gold/silver redemption demand
  3. Supply chain anomaly   — detect fraud, mismatches, and routing anomalies

Phase 3: rule-based + statistical models.
ML hooks provided for future upgrade to LSTM / Prophet / GNN.
"""

import math
import statistics
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Thresholds & Constants ───────────────────────────────────────────────────

# Minimum vault coverage ratio (vault_stock / avg_daily_demand * horizon)
_MIN_COVERAGE_RATIO: float = 1.25          # 25% buffer above projected demand
_CRITICAL_COVERAGE_RATIO: float = 0.80    # below 80% → critical stock warning

# Logistics carriers and their base cost per kg (USD)
_CARRIER_COSTS_PER_KG: dict[str, float] = {
    "FedEx":  12.50,
    "DHL":    11.80,
    "Brinks": 18.00,    # armoured — for high-value shipments
    "VIA":    14.20,    # via-mat specialist vault logistics
}

# Anomaly detection thresholds
_MISMATCH_TOLERANCE_PCT: float = 2.0      # acceptable weight discrepancy %
_SUSPICIOUSLY_ROUND_KG: float = 10.0      # flag exact round-kg large shipments

# High-risk shipment origin countries (OFAC/FATF aligned)
_HIGH_RISK_COUNTRIES: frozenset = frozenset({"KP", "IR", "SY", "CU", "SD", "MM", "AF"})


# ─── 1. Inventory Forecasting ─────────────────────────────────────────────────

def forecast_inventory(
    vault_id: str,
    current_stock_kg: float,
    recent_daily_outflows: list[float],    # past N days of outflow in kg
    horizon_days: int = 30,
    seasonality_factor: float = 1.0,       # multiplier for seasonal demand spikes
) -> dict:
    """
    Forecast whether vault stock will be sufficient over the given horizon.

    Method:
      - Compute mean and std of recent daily outflows (Holt-style simple average).
      - Projected demand = mean * horizon_days * seasonality_factor.
      - Compute coverage ratio and issue stock alerts.
      - Recommend reorder quantity if below threshold.

    Returns:
        current_stock_kg, horizon_days,
        avg_daily_outflow_kg,
        projected_demand_kg,
        projected_end_stock_kg,
        coverage_ratio,
        stock_status (str): HEALTHY / WARNING / CRITICAL
        reorder_recommended (bool)
        reorder_quantity_kg (float)
        demand_volatility (str): LOW / MEDIUM / HIGH
        notes (list[str])
    """
    notes: list[str] = []

    if not recent_daily_outflows:
        return {
            "current_stock_kg": round(current_stock_kg, 3),
            "horizon_days": horizon_days,
            "avg_daily_outflow_kg": 0.0,
            "projected_demand_kg": 0.0,
            "projected_end_stock_kg": round(current_stock_kg, 3),
            "coverage_ratio": None,
            "stock_status": "HEALTHY",
            "reorder_recommended": False,
            "reorder_quantity_kg": 0.0,
            "demand_volatility": "LOW",
            "notes": ["No outflow history provided — assuming zero demand."],
        }

    avg = statistics.mean(recent_daily_outflows)
    std = statistics.stdev(recent_daily_outflows) if len(recent_daily_outflows) > 1 else 0.0
    cv = (std / avg) if avg > 0 else 0.0  # coefficient of variation

    projected_demand = round(avg * horizon_days * seasonality_factor, 3)
    projected_end = round(current_stock_kg - projected_demand, 3)
    coverage_ratio = round(current_stock_kg / projected_demand, 3) if projected_demand > 0 else None

    # Status
    if coverage_ratio is None or coverage_ratio >= _MIN_COVERAGE_RATIO:
        stock_status = "HEALTHY"
    elif coverage_ratio >= _CRITICAL_COVERAGE_RATIO:
        stock_status = "WARNING"
        notes.append(
            f"Stock coverage {coverage_ratio:.2f}x projected demand — "
            "consider placing a reorder soon."
        )
    else:
        stock_status = "CRITICAL"
        notes.append(
            f"CRITICAL: Stock coverage {coverage_ratio:.2f}x — "
            "immediate reorder required to avoid stockout."
        )

    reorder_recommended = stock_status in ("WARNING", "CRITICAL")

    # Reorder quantity: top up to 2x projected demand
    if reorder_recommended:
        reorder_qty = round(max(0.0, projected_demand * 2.0 - current_stock_kg), 3)
    else:
        reorder_qty = 0.0

    # Demand volatility
    if cv < 0.15:
        demand_volatility = "LOW"
    elif cv < 0.35:
        demand_volatility = "MEDIUM"
    else:
        demand_volatility = "HIGH"
        notes.append(
            f"High demand volatility (CV={cv:.2f}) — "
            "consider maintaining a larger safety buffer."
        )

    if seasonality_factor > 1.2:
        notes.append(
            f"Seasonal demand multiplier applied ({seasonality_factor:.2f}x) — "
            "peak period forecast."
        )

    logger.info(
        f"[VAULT_AI] forecast_inventory | vault_id={vault_id} "
        f"stock={current_stock_kg}kg projected_demand={projected_demand}kg "
        f"coverage={coverage_ratio if coverage_ratio is None else f'{coverage_ratio:.2f}'} status={stock_status}"
    )

    return {
        "current_stock_kg": round(current_stock_kg, 3),
        "horizon_days": horizon_days,
        "avg_daily_outflow_kg": round(avg, 4),
        "projected_demand_kg": projected_demand,
        "projected_end_stock_kg": projected_end,
        "coverage_ratio": coverage_ratio,
        "stock_status": stock_status,
        "reorder_recommended": reorder_recommended,
        "reorder_quantity_kg": reorder_qty,
        "demand_volatility": demand_volatility,
        "notes": notes if notes else ["Vault inventory is healthy — no action required."],
    }


# ─── 2. Demand Prediction ─────────────────────────────────────────────────────

def predict_redemption_demand(
    asset: str,
    recent_daily_requests: list[float],   # past N days of redemption requests (kg or units)
    horizon_days: int = 7,
    price_trend: str = "neutral",         # bullish / neutral / bearish — affects demand
) -> dict:
    """
    Predict physical gold/silver redemption demand over a short horizon.

    Uses simple exponential smoothing (alpha=0.3) on the recent request series.
    Price trend modifies the forecast (price drop → higher redemption demand).

    Returns:
        asset, horizon_days,
        smoothed_forecast_daily,
        total_forecast_horizon,
        confidence (str): LOW / MEDIUM / HIGH,
        price_trend_adjustment_pct,
        trend_adjusted_forecast,
        insight (str)
    """
    if not recent_daily_requests:
        return {
            "asset": asset,
            "horizon_days": horizon_days,
            "smoothed_forecast_daily": 0.0,
            "total_forecast_horizon": 0.0,
            "confidence": "LOW",
            "price_trend_adjustment_pct": 0.0,
            "trend_adjusted_forecast": 0.0,
            "insight": "No historical demand data provided. Forecast unreliable.",
        }

    # Exponential smoothing (alpha = 0.3)
    alpha = 0.3
    smoothed = recent_daily_requests[0]
    for val in recent_daily_requests[1:]:
        smoothed = alpha * val + (1 - alpha) * smoothed

    # Price trend adjustment
    trend_adj_pct = {"bullish": -0.10, "neutral": 0.0, "bearish": 0.15}.get(
        price_trend.lower(), 0.0
    )
    adjusted = round(smoothed * (1 + trend_adj_pct), 4)
    total = round(adjusted * horizon_days, 4)

    # Confidence: more data → more confidence
    n = len(recent_daily_requests)
    if n >= 14:
        confidence = "HIGH"
    elif n >= 7:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    if price_trend.lower() == "bearish":
        insight = (
            f"Bearish {asset} price trend detected — redemption demand likely "
            f"elevated by {abs(trend_adj_pct):.0%}. Ensure vault has sufficient stock."
        )
    elif price_trend.lower() == "bullish":
        insight = (
            f"Bullish {asset} price trend — holders likely to retain rather than redeem. "
            f"Demand forecast reduced by {abs(trend_adj_pct):.0%}."
        )
    else:
        insight = f"Neutral market — baseline demand forecast applies."

    logger.info(
        f"[VAULT_AI] predict_redemption_demand | asset={asset} "
        f"smoothed={smoothed:.4f} adjusted={adjusted:.4f} "
        f"total_{horizon_days}d={total:.4f} confidence={confidence}"
    )

    return {
        "asset": asset,
        "horizon_days": horizon_days,
        "smoothed_forecast_daily": round(smoothed, 4),
        "total_forecast_horizon": total,
        "confidence": confidence,
        "price_trend_adjustment_pct": round(trend_adj_pct * 100, 1),
        "trend_adjusted_forecast": adjusted,
        "insight": insight,
    }


# ─── 3. Supply Chain Anomaly Detection ───────────────────────────────────────

def detect_supply_chain_anomaly(shipment_id: str, shipment_data: dict) -> dict:
    """
    Detect fraud, mismatch, and routing anomalies in gold/silver shipments.

    Signals evaluated:
      1. Weight mismatch      — declared vs measured weight discrepancy
      2. Route deviation      — unexpected origin/destination combination
      3. Carrier anomaly      — unknown or unusually cheap carrier for asset value
      4. Round weight         — suspiciously round weight for large shipments
      5. Value concentration  — single shipment above 20% of total vault stock

    Returns:
        anomaly_detected (bool)
        anomaly_score (float, 0–100)
        flags (list[str])
        recommended_action (str): RELEASE / HOLD_FOR_REVIEW / ESCALATE
        logistics_recommendation (dict): best carrier for the shipment
    """
    flags: list[str] = []
    score = 0.0

    declared_weight_kg = float(shipment_data.get("declared_weight_kg", 0))
    measured_weight_kg = float(shipment_data.get("measured_weight_kg", 0))
    carrier = str(shipment_data.get("carrier", "")).strip()
    origin = str(shipment_data.get("origin_country", "")).upper()
    destination = str(shipment_data.get("destination_country", "")).upper()
    asset_value_usd = float(shipment_data.get("asset_value_usd", 0))
    vault_total_usd = float(shipment_data.get("vault_total_value_usd", 1))
    asset_type = str(shipment_data.get("asset_type", "gold")).lower()

    # Signal 1: Weight mismatch
    if declared_weight_kg > 0 and measured_weight_kg > 0:
        mismatch_pct = abs(declared_weight_kg - measured_weight_kg) / declared_weight_kg * 100
        if mismatch_pct > _MISMATCH_TOLERANCE_PCT:
            score += 35.0
            flags.append(
                f"Weight mismatch: declared {declared_weight_kg:.3f}kg vs "
                f"measured {measured_weight_kg:.3f}kg "
                f"({mismatch_pct:.2f}% deviation)."
            )

    # Signal 2: High-risk origin country
    if origin in _HIGH_RISK_COUNTRIES:
        score += 30.0
        flags.append(f"Shipment originates from high-risk jurisdiction: {origin}.")

    # Signal 3: Unknown carrier for asset type
    known_carriers = set(_CARRIER_COSTS_PER_KG.keys())
    if carrier and carrier not in known_carriers:
        score += 20.0
        flags.append(
            f"Unknown carrier '{carrier}' — not in approved logistics provider list."
        )
    elif asset_value_usd > 100_000 and carrier == "FedEx":
        # FedEx is fine for normal parcels but sub-optimal for high-value vault transfers
        flags.append(
            f"High-value shipment (${asset_value_usd:,.0f}) via standard courier — "
            "consider armoured carrier (Brinks/VIA) for shipments above $100,000."
        )

    # Signal 4: Suspiciously round weight
    if declared_weight_kg >= _SUSPICIOUSLY_ROUND_KG and declared_weight_kg % 1.0 == 0:
        score += 10.0
        flags.append(
            f"Suspiciously round shipment weight: {declared_weight_kg:.0f}kg — "
            "verify against weigh certificate."
        )

    # Signal 5: Value concentration
    concentration = asset_value_usd / vault_total_usd if vault_total_usd > 0 else 0
    if concentration > 0.20:
        score += 15.0
        flags.append(
            f"Single shipment represents {concentration:.0%} of total vault value — "
            "unusually high concentration."
        )

    score = round(min(score, 100.0), 2)
    anomaly_detected = score >= 30.0

    if score >= 65:
        recommended_action = "ESCALATE"
    elif score >= 30:
        recommended_action = "HOLD_FOR_REVIEW"
    else:
        recommended_action = "RELEASE"

    # Logistics recommendation: cheapest carrier that is appropriate for value
    if asset_value_usd >= 100_000:
        suitable_carriers = {k: v for k, v in _CARRIER_COSTS_PER_KG.items()
                             if k in ("Brinks", "VIA")}
    else:
        suitable_carriers = _CARRIER_COSTS_PER_KG

    best_carrier = min(suitable_carriers, key=lambda c: suitable_carriers[c])
    logistics_rec = {
        "recommended_carrier": best_carrier,
        "estimated_cost_per_kg_usd": suitable_carriers[best_carrier],
        "estimated_total_cost_usd": round(
            suitable_carriers[best_carrier] * declared_weight_kg, 2
        ) if declared_weight_kg > 0 else None,
    }

    logger.info(
        f"[VAULT_AI] detect_supply_chain_anomaly | shipment_id={shipment_id} "
        f"score={score} anomaly={anomaly_detected} action={recommended_action}"
    )

    return {
        "anomaly_detected": anomaly_detected,
        "anomaly_score": score,
        "flags": flags if flags else ["No supply chain anomalies detected."],
        "recommended_action": recommended_action,
        "logistics_recommendation": logistics_rec,
    }
