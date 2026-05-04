"""
market_ai/service.py
─────────────────────
AI Price Forecasting Engine — Geometric Brownian Motion + Monte Carlo.

Supported assets: gold, silver, btc, eth, spy (S&P 500 ETF), xau (alias for gold).

Design:
  - Uses GBM (Geometric Brownian Motion) with market-calibrated parameters.
  - Monte Carlo simulation (500 paths) returns median + p10/p90 confidence band.
  - Seeded with deterministic seed per (asset + horizon) for reproducible results
    across identical requests, while still reflecting statistical uncertainty.
  - Baseline prices are hardcoded to realistic May 2026 market levels.
    In production: replace _ASSET_PARAMS["base_price"] with a live feed call
    (CoinGecko, Alpha Vantage, Quandl, or Bloomberg).

Forecasting accuracy:
  - Short horizons (1–7 days):  reasonable directional signal
  - Medium horizons (7–30 days): wide confidence interval, use trend only
  - Long horizons (> 30 days):  treat as scenario planning, not point forecast
"""

import math
import random
import threading
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Asset Parameters ─────────────────────────────────────────────────────────
# daily_vol: annualised vol / sqrt(252) — approximate daily price move 1-sigma
# annual_drift: expected annualised return (geometric), risk-neutral approximation

_ASSET_PARAMS: dict[str, dict] = {
    "gold":   {"base_price": 2_285.0, "daily_vol": 0.0080, "annual_drift": 0.08,  "unit": "USD/oz"},
    "silver": {"base_price":    27.6, "daily_vol": 0.0120, "annual_drift": 0.06,  "unit": "USD/oz"},
    "btc":    {"base_price": 69_200.0,"daily_vol": 0.0350, "annual_drift": 0.45,  "unit": "USD"},
    "eth":    {"base_price":  3_420.0,"daily_vol": 0.0400, "annual_drift": 0.40,  "unit": "USD"},
    "spy":    {"base_price":   548.0, "daily_vol": 0.0090, "annual_drift": 0.10,  "unit": "USD/share"},
    "xau":    {"base_price": 2_285.0, "daily_vol": 0.0080, "annual_drift": 0.08,  "unit": "USD/oz"},
}

SUPPORTED_ASSETS = set(_ASSET_PARAMS.keys())

_TREND_THRESHOLDS = {
    "strong_bullish":  0.05,
    "bullish":         0.02,
    "bearish":        -0.02,
    "strong_bearish": -0.05,
}

_N_SIMULATIONS = 500

# Per-thread Random instance — avoids lock contention on the shared random state
# when multiple forecast calls run concurrently in different threads.
_thread_local = threading.local()


def _get_rng(seed: int) -> random.Random:
    """Return a seeded Random instance (one per call for determinism)."""
    rng = random.Random(seed)
    return rng


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _classify_trend(pct_change: float) -> str:
    if pct_change >= _TREND_THRESHOLDS["strong_bullish"]:
        return "strong_bullish"
    if pct_change >= _TREND_THRESHOLDS["bullish"]:
        return "bullish"
    if pct_change <= _TREND_THRESHOLDS["strong_bearish"]:
        return "strong_bearish"
    if pct_change <= _TREND_THRESHOLDS["bearish"]:
        return "bearish"
    return "neutral"


def _gbm_simulate(
    current_price: float,
    daily_vol: float,
    annual_drift: float,
    horizon_days: int,
    seed: int,
) -> tuple[float, float, float]:
    """
    Run a Monte Carlo GBM simulation.

    Each path: S(t+1) = S(t) * exp((μ - σ²/2)Δt + σ√Δt * Z)
    where Z ~ N(0,1), Δt = 1 day.

    Returns:
        (median_price, p10_price, p90_price)
    """
    rng = _get_rng(seed)
    daily_drift = annual_drift / 365.0

    terminal_prices: list[float] = []
    for _ in range(_N_SIMULATIONS):
        price = current_price
        for _ in range(horizon_days):
            z = rng.gauss(0, 1)
            price *= math.exp(
                (daily_drift - 0.5 * daily_vol ** 2) + daily_vol * z
            )
        terminal_prices.append(price)

    terminal_prices.sort()
    n = len(terminal_prices)
    median = terminal_prices[n // 2]
    p10 = terminal_prices[int(n * 0.10)]
    p90 = terminal_prices[int(n * 0.90)]

    return round(median, 2), round(p10, 2), round(p90, 2)


# ─── Public API ───────────────────────────────────────────────────────────────

def forecast_price(
    asset: str,
    horizon_days: int = 30,
    current_price: Optional[float] = None,
) -> dict:
    """
    Forecast the price of an asset over the given horizon.

    Args:
        asset         — one of: gold, silver, btc, eth, spy, xau
        horizon_days  — forecast horizon in calendar days (1–365)
        current_price — optional live price override; uses baseline if None

    Returns a dict with:
        asset, current_price, unit, horizon_days,
        forecast_price, confidence_interval (p10, p90),
        pct_change, trend, model, note
    """
    key = asset.lower()
    if key not in SUPPORTED_ASSETS:
        raise ValueError(
            f"Unsupported asset '{asset}'. "
            f"Supported assets: {sorted(SUPPORTED_ASSETS)}"
        )

    if horizon_days < 1 or horizon_days > 365:
        raise ValueError("horizon_days must be between 1 and 365.")

    params = _ASSET_PARAMS[key]
    base_price = current_price if current_price is not None else params["base_price"]

    # Deterministic seed per asset + horizon so identical requests return
    # identical forecasts (useful for caching / testing).
    seed = hash((key, horizon_days)) % (2 ** 31)

    median, p10, p90 = _gbm_simulate(
        current_price=base_price,
        daily_vol=params["daily_vol"],
        annual_drift=params["annual_drift"],
        horizon_days=horizon_days,
        seed=seed,
    )

    pct_change = round((median - base_price) / base_price, 4)
    trend = _classify_trend(pct_change)

    logger.info(
        f"[MARKET_AI] forecast_price | asset={key} horizon={horizon_days}d "
        f"current={base_price:.2f} forecast={median:.2f} "
        f"pct_change={pct_change:.2%} trend={trend}"
    )

    return {
        "asset": key,
        "current_price": round(base_price, 2),
        "unit": params["unit"],
        "horizon_days": horizon_days,
        "forecast_price": median,
        "confidence_interval": {"p10": p10, "p90": p90},
        "pct_change": pct_change,
        "trend": trend,
        "model": "gbm_monte_carlo_v1",
        "note": (
            "Forecast uses GBM Monte Carlo simulation calibrated to historical "
            "market volatility. Confidence interval is p10–p90 across 500 paths. "
            "For live accuracy, supply current_price from a real-time market feed."
        ),
    }


def batch_forecast(
    assets: list[str],
    horizon_days: int = 30,
) -> list[dict]:
    """Forecast multiple assets in a single call."""
    return [forecast_price(asset, horizon_days) for asset in assets]
