"""
orchestration_ai/service.py
────────────────────────────
API Orchestration AI — smart broker routing and fee optimization engine.

Covers Module 7 from the Aurix AI roadmap:
  1. Smart broker routing    — score Revolut, Binance, eToro, DriveWealth
                               by latency, fee, liquidity, and asset support
  2. Best execution engine   — pick the venue that minimises total execution cost
  3. Fee optimization        — compare fee structures and compute net savings
  4. Cross-platform sync     — identify portfolio overlaps and concentration risk

Phase 3: Scoring tables + rule-based engine.
ML hook provided for future reinforcement-learning–based routing.
"""

from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Broker Capability Profiles ───────────────────────────────────────────────

_BROKERS: dict[str, dict] = {
    "Revolut": {
        "supported_assets": {"gold", "silver", "crypto", "etf", "stocks", "forex"},
        "base_fee_pct": 0.50,           # 0.5% base trading fee
        "min_fee_usd": 0.00,
        "latency_ms": 120,              # typical order execution latency
        "liquidity_score": 7.5,         # out of 10
        "kyc_tier": 2,                  # KYC level required (1=basic, 3=institutional)
        "max_order_usd": 500_000,
        "geographic_coverage": ["EU", "UK", "US"],
        "strengths": ["Low fees for retail", "Instant settlement", "Multi-currency"],
        "weaknesses": ["Limited institutional tools", "No margin lending for gold"],
    },
    "Binance": {
        "supported_assets": {"crypto", "stablecoin", "etf", "futures"},
        "base_fee_pct": 0.10,           # BNB discount applied at tiered volumes
        "min_fee_usd": 0.00,
        "latency_ms": 45,
        "liquidity_score": 9.5,
        "kyc_tier": 1,
        "max_order_usd": 10_000_000,
        "geographic_coverage": ["GLOBAL"],
        "strengths": ["Deepest crypto liquidity", "Very low fees", "USDT pairs"],
        "weaknesses": ["No traditional gold/silver vault", "Regulatory complexity"],
    },
    "eToro": {
        "supported_assets": {"gold", "silver", "crypto", "stocks", "etf", "cfd"},
        "base_fee_pct": 1.00,
        "min_fee_usd": 0.00,
        "latency_ms": 200,
        "liquidity_score": 7.0,
        "kyc_tier": 2,
        "max_order_usd": 2_000_000,
        "geographic_coverage": ["EU", "UK", "MENA", "APAC"],
        "strengths": ["Copy trading", "Physical gold/silver", "Social features"],
        "weaknesses": ["Higher spreads", "Withdrawal fees"],
    },
    "DriveWealth": {
        "supported_assets": {"stocks", "etf", "fractional"},
        "base_fee_pct": 0.00,           # zero-commission, but spread-based
        "min_fee_usd": 0.00,
        "latency_ms": 300,
        "liquidity_score": 6.5,
        "kyc_tier": 2,
        "max_order_usd": 1_000_000,
        "geographic_coverage": ["US", "LATAM", "APAC"],
        "strengths": ["Fractional US stocks", "B2B/whitelabel API", "Zero commission"],
        "weaknesses": ["US equities only", "Slower execution"],
    },
}

# Weight matrix for broker scoring (must sum to 1.0)
_SCORE_WEIGHTS = {
    "fee_score":       0.30,
    "latency_score":   0.25,
    "liquidity_score": 0.25,
    "asset_coverage":  0.20,
}


# ─── 1. Smart Broker Routing ─────────────────────────────────────────────────

def route_broker(
    user_id: str,
    asset_type: str,
    order_size_usd: float,
    priority: str = "cost",            # cost / speed / liquidity
    required_kyc_tier: int = 1,
    user_region: str = "EU",
) -> dict:
    """
    Score and rank available brokers for a given order.

    Scoring factors:
      - Fee score     : normalised inverse of total fee for this order size
      - Latency score : normalised inverse of execution latency
      - Liquidity     : broker liquidity_score from profile
      - Asset support : 1.0 if broker supports the asset, 0 otherwise

    Returns:
        recommended_broker (str)
        ranked_brokers (list): all eligible brokers sorted by score
        rationale (str): reason for top pick
        execution_estimate (dict): estimated fee + latency for recommended broker
    """
    asset_norm = asset_type.lower().replace("-", "").replace(" ", "")
    eligible: list[dict] = []

    for name, profile in _BROKERS.items():
        # Hard filters
        if order_size_usd > profile["max_order_usd"]:
            continue
        if required_kyc_tier > profile["kyc_tier"]:
            continue
        if (user_region not in profile["geographic_coverage"]
                and "GLOBAL" not in profile["geographic_coverage"]):
            continue
        # Asset support
        if asset_norm not in profile["supported_assets"]:
            continue

        eligible.append({"name": name, "profile": profile})

    if not eligible:
        logger.warning(
            f"[ORCHESTRATION_AI] route_broker | user_id={user_id} "
            f"no eligible brokers for asset={asset_type} region={user_region}"
        )
        return {
            "recommended_broker": None,
            "ranked_brokers": [],
            "rationale": (
                f"No eligible broker found for asset='{asset_type}' "
                f"in region '{user_region}' for order size ${order_size_usd:,.0f}."
            ),
            "execution_estimate": None,
        }

    # Compute normalised scores
    min_fee = min(b["profile"]["base_fee_pct"] for b in eligible)
    max_fee = max(b["profile"]["base_fee_pct"] for b in eligible)
    min_lat = min(b["profile"]["latency_ms"] for b in eligible)
    max_lat = max(b["profile"]["latency_ms"] for b in eligible)

    scored: list[dict] = []
    for b in eligible:
        p = b["profile"]

        # Normalise fee (lower is better → invert)
        if max_fee > min_fee:
            fee_score = 1.0 - (p["base_fee_pct"] - min_fee) / (max_fee - min_fee)
        else:
            fee_score = 1.0

        # Normalise latency (lower is better → invert)
        if max_lat > min_lat:
            lat_score = 1.0 - (p["latency_ms"] - min_lat) / (max_lat - min_lat)
        else:
            lat_score = 1.0

        liq_score = p["liquidity_score"] / 10.0
        asset_score = 1.0  # already filtered to only supported assets

        # Priority adjustment: boost the relevant dimension
        weights = dict(_SCORE_WEIGHTS)
        if priority == "speed":
            weights["latency_score"] += 0.15
            weights["fee_score"] -= 0.15
        elif priority == "liquidity":
            weights["liquidity_score"] += 0.15
            weights["fee_score"] -= 0.15
        # Default "cost" keeps original weights

        composite = (
            weights["fee_score"]       * fee_score
            + weights["latency_score"] * lat_score
            + weights["liquidity_score"] * liq_score
            + weights["asset_coverage"] * asset_score
        )

        estimated_fee_usd = round(order_size_usd * p["base_fee_pct"] / 100, 2)

        scored.append({
            "broker": b["name"],
            "composite_score": round(composite * 100, 2),
            "estimated_fee_usd": estimated_fee_usd,
            "estimated_fee_pct": p["base_fee_pct"],
            "latency_ms": p["latency_ms"],
            "liquidity_score": p["liquidity_score"],
            "strengths": p["strengths"],
            "weaknesses": p["weaknesses"],
        })

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    top = scored[0]

    rationale = (
        f"{top['broker']} selected as best execution venue "
        f"(score {top['composite_score']:.1f}/100) "
        f"for {asset_type} order of ${order_size_usd:,.0f}. "
        f"Estimated fee: ${top['estimated_fee_usd']:,.2f} "
        f"({top['estimated_fee_pct']}%), latency ~{top['latency_ms']}ms."
    )

    logger.info(
        f"[ORCHESTRATION_AI] route_broker | user_id={user_id} "
        f"asset={asset_type} order_usd={order_size_usd} "
        f"recommended={top['broker']} score={top['composite_score']}"
    )

    return {
        "recommended_broker": top["broker"],
        "ranked_brokers": scored,
        "rationale": rationale,
        "execution_estimate": {
            "broker": top["broker"],
            "estimated_fee_usd": top["estimated_fee_usd"],
            "estimated_fee_pct": top["estimated_fee_pct"],
            "estimated_latency_ms": top["latency_ms"],
        },
    }


# ─── 2. Fee Optimization Engine ──────────────────────────────────────────────

def optimize_fees(
    user_id: str,
    planned_trades: list[dict],         # list of {asset_type, order_size_usd}
    current_broker: str,
) -> dict:
    """
    Compare the user's current broker against alternatives for a set of planned
    trades and quantify the potential fee savings.

    Input trade format: {"asset_type": "gold", "order_size_usd": 10000}

    Returns:
        current_broker
        current_total_fees_usd
        optimized_total_fees_usd
        estimated_savings_usd
        savings_pct
        per_trade_recommendations (list)
        summary (str)
    """
    current_profile = _BROKERS.get(current_broker)
    if not current_profile:
        raise ValueError(
            f"Unknown broker: '{current_broker}'. "
            f"Valid brokers: {list(_BROKERS.keys())}"
        )

    total_current = 0.0
    total_optimized = 0.0
    per_trade: list[dict] = []

    for trade in planned_trades:
        asset = str(trade.get("asset_type", "")).lower()
        size = float(trade.get("order_size_usd", 0))

        current_fee = round(size * current_profile["base_fee_pct"] / 100, 2)

        # Find cheapest broker that supports this asset
        best_broker_name = current_broker
        best_fee = current_fee
        for name, prof in _BROKERS.items():
            if asset not in prof["supported_assets"]:
                continue
            candidate_fee = round(size * prof["base_fee_pct"] / 100, 2)
            if candidate_fee < best_fee:
                best_fee = candidate_fee
                best_broker_name = name

        savings = round(current_fee - best_fee, 2)
        total_current += current_fee
        total_optimized += best_fee

        per_trade.append({
            "asset_type": asset,
            "order_size_usd": size,
            "current_broker": current_broker,
            "current_fee_usd": current_fee,
            "recommended_broker": best_broker_name,
            "optimized_fee_usd": best_fee,
            "savings_usd": savings,
        })

    total_current = round(total_current, 2)
    total_optimized = round(total_optimized, 2)
    total_savings = round(total_current - total_optimized, 2)
    savings_pct = round(total_savings / total_current * 100, 1) if total_current > 0 else 0.0

    if total_savings <= 0:
        summary = (
            f"'{current_broker}' is already cost-optimal for the planned trades. "
            "No fee savings identified."
        )
    else:
        summary = (
            f"Switching or splitting trades could save ${total_savings:,.2f} "
            f"({savings_pct:.1f}%) versus routing all orders through {current_broker}."
        )

    logger.info(
        f"[ORCHESTRATION_AI] optimize_fees | user_id={user_id} "
        f"current_broker={current_broker} current_fees={total_current} "
        f"optimized_fees={total_optimized} savings={total_savings}"
    )

    return {
        "current_broker": current_broker,
        "current_total_fees_usd": total_current,
        "optimized_total_fees_usd": total_optimized,
        "estimated_savings_usd": total_savings,
        "savings_pct": savings_pct,
        "per_trade_recommendations": per_trade,
        "summary": summary,
    }


# ─── 3. Cross-Platform Portfolio Sync ────────────────────────────────────────

def sync_portfolio_intelligence(
    user_id: str,
    portfolios_by_broker: dict[str, dict[str, float]],  # {broker: {asset: usd_value}}
) -> dict:
    """
    Aggregate multi-broker portfolio data, identify overlaps and concentration
    risk across platforms.

    Returns:
        unified_portfolio (dict): merged USD values per asset
        total_value_usd (float)
        concentration_risks (list): assets > 40% of total
        broker_exposures (dict): % of portfolio per broker
        overlap_warnings (list): same asset at multiple brokers
        diversification_score (float, 0–100)
        insights (list[str])
    """
    # Merge all positions
    unified: dict[str, float] = {}
    for broker, holdings in portfolios_by_broker.items():
        for asset, value in holdings.items():
            unified[asset] = round(unified.get(asset, 0.0) + float(value), 2)

    total = round(sum(unified.values()), 2)
    if total <= 0:
        return {
            "unified_portfolio": {},
            "total_value_usd": 0.0,
            "concentration_risks": [],
            "broker_exposures": {},
            "overlap_warnings": [],
            "diversification_score": 0.0,
            "insights": ["No portfolio data provided."],
        }

    concentration_risks: list[dict] = []
    for asset, value in unified.items():
        pct = round(value / total * 100, 2)
        if pct > 40.0:
            concentration_risks.append({
                "asset": asset,
                "value_usd": value,
                "portfolio_pct": pct,
                "warning": f"{asset} represents {pct:.1f}% of portfolio — high concentration.",
            })

    # Broker exposures
    broker_exposures = {
        broker: round(sum(holdings.values()) / total * 100, 2)
        for broker, holdings in portfolios_by_broker.items()
    }

    # Overlap warnings (same asset across >1 broker)
    overlap_warnings: list[str] = []
    for asset in unified:
        brokers_with_asset = [
            b for b, holdings in portfolios_by_broker.items() if asset in holdings
        ]
        if len(brokers_with_asset) > 1:
            overlap_warnings.append(
                f"'{asset}' held at {len(brokers_with_asset)} brokers: "
                f"{', '.join(brokers_with_asset)}. Consider consolidating."
            )

    # Herfindahl–Hirschman Index for diversification
    # HHI = sum(share^2); low HHI = diverse; max=10000 (one asset)
    n_assets = len(unified)
    if n_assets == 1:
        diversification_score = 0.0
    else:
        hhi = sum((v / total * 100) ** 2 for v in unified.values())
        # Normalise: perfect diversity = 10000/n, full concentration = 10000
        min_hhi = 10000 / n_assets
        diversification_score = round(
            max(0.0, min(100.0, (10000 - hhi) / (10000 - min_hhi) * 100)), 2
        )

    insights: list[str] = []
    if concentration_risks:
        assets_at_risk = [c["asset"] for c in concentration_risks]
        insights.append(
            f"Concentration risk: {', '.join(assets_at_risk)} — consider rebalancing."
        )
    if overlap_warnings:
        insights.append(
            f"{len(overlap_warnings)} asset(s) duplicated across brokers — "
            "consolidation may reduce management overhead and fees."
        )
    if diversification_score >= 75:
        insights.append("Portfolio is well-diversified across asset classes.")
    elif diversification_score >= 50:
        insights.append("Moderate diversification — room for improvement.")
    else:
        insights.append("Low diversification score — portfolio is highly concentrated.")

    logger.info(
        f"[ORCHESTRATION_AI] sync_portfolio_intelligence | user_id={user_id} "
        f"total={total} n_assets={n_assets} "
        f"diversification={diversification_score} "
        f"concentration_risks={len(concentration_risks)}"
    )

    return {
        "unified_portfolio": unified,
        "total_value_usd": total,
        "concentration_risks": concentration_risks,
        "broker_exposures": broker_exposures,
        "overlap_warnings": overlap_warnings,
        "diversification_score": diversification_score,
        "insights": insights if insights else ["No portfolio issues detected."],
    }
