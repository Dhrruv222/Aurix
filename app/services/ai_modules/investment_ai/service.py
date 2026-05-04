"""
investment_ai/service.py
────────────────────────
Portfolio optimization and investment recommendation engine.

Current implementation: rule-based profile blending (MVP).
ML hook is provided — swap `compute_recommendation_ml` when an
optimization model (e.g. mean-variance, RL-based) is available.
"""

from app.core.logging import get_logger
from app.schemas.schemas import PortfolioRequest, PortfolioResponse

logger = get_logger(__name__)

# ─── Risk Profile Targets ──────────────────────────────────────────────────────

RISK_PROFILES: dict[str, dict[str, float]] = {
    "low":        {"gold": 70.0, "stocks": 20.0, "crypto": 10.0},
    "medium":     {"gold": 55.0, "stocks": 30.0, "crypto": 15.0},
    "high":       {"gold": 30.0, "stocks": 40.0, "crypto": 30.0},
    "aggressive": {"gold": 20.0, "stocks": 35.0, "crypto": 45.0},
}

PROFILE_NOTES: dict[str, str] = {
    "low":        "Conservative profile → heavy gold allocation for stability.",
    "medium":     "Medium risk profile → balanced allocation across assets.",
    "high":       "High risk profile → increased equity and crypto exposure.",
    "aggressive": "Aggressive profile → maximum growth, higher volatility expected.",
}

_ASSETS = ("gold", "stocks", "crypto")


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def normalize_allocation(portfolio: dict[str, float]) -> dict[str, float]:
    """
    Normalize raw portfolio values to percentages summing to 100.
    Falls back to equal-weight split if portfolio is empty or all-zero.
    """
    current = {asset: float(portfolio.get(asset, 0.0) or 0.0) for asset in _ASSETS}
    total = sum(max(v, 0.0) for v in current.values())

    if total <= 0:
        return {"gold": 33.34, "stocks": 33.33, "crypto": 33.33}

    normalized = {
        asset: round((max(current[asset], 0.0) / total) * 100.0, 2)
        for asset in _ASSETS
    }
    # Correct floating-point drift on stocks
    drift = round(100.0 - sum(normalized.values()), 2)
    normalized["stocks"] = round(normalized["stocks"] + drift, 2)
    return normalized


def _blend_allocation(
    current: dict[str, float],
    target: dict[str, float],
    target_weight: float = 0.7,
) -> dict[str, float]:
    """
    Blend target profile (70%) with current allocation (30%) to avoid
    abrupt rebalancing.

    target_weight: fraction assigned to the target profile (0.0–1.0).

    TODO: replace with Markowitz mean-variance or RL-based rebalancing.
    """
    current_weight = 1.0 - target_weight
    blended = {
        asset: round((target[asset] * target_weight) + (current[asset] * current_weight), 2)
        for asset in _ASSETS
    }
    drift = round(100.0 - sum(blended.values()), 2)
    blended["stocks"] = round(blended["stocks"] + drift, 2)
    return blended


# ─── Core Rule-Based Recommender ──────────────────────────────────────────────

def compute_recommendation(data: PortfolioRequest) -> PortfolioResponse:
    """
    Produce a blended portfolio recommendation based on the user's risk
    profile and current holdings.

    Steps:
      1. Validate risk profile
      2. Normalize current portfolio to percentages
      3. Blend normalized current with target profile weights
      4. Return allocation + explanatory notes
    """
    profile = data.risk_profile.lower()

    if profile not in RISK_PROFILES:
        raise ValueError(
            f"Unknown risk_profile: '{profile}'. Valid: {list(RISK_PROFILES.keys())}"
        )

    current = normalize_allocation(data.portfolio)
    target = RISK_PROFILES[profile].copy()
    allocation = _blend_allocation(current, target)

    notes = [
        PROFILE_NOTES[profile],
        "Recommendation blends target profile weights (70%) with current allocation (30%).",
    ]

    logger.debug(
        f"[INVESTMENT_AI] user_id={data.user_id} profile={profile} "
        f"allocation={allocation}"
    )

    return PortfolioResponse(
        recommended_allocation=allocation,
        notes=notes,
    )


# ─── ML Hook ──────────────────────────────────────────────────────────────────

def compute_recommendation_ml(data: PortfolioRequest) -> PortfolioResponse:
    """
    ML-powered portfolio optimizer.

    TODO: Replace blending logic with a trained optimization model.
    Expected integration:
        1. Build feature vector: risk_profile, current allocation, market signals
        2. Call optimizer.predict(features) → target weights
        3. Apply constraints (min/max per asset, turnover limits)
        4. Return PortfolioResponse with model-generated notes

    Example (skeleton):
        features = build_portfolio_features(data)
        weights = optimizer_model.predict([features])[0]
        allocation = dict(zip(_ASSETS, weights))
        ...
    """
    # Fallback to rule-based until model is ready
    return compute_recommendation(data)


# ─── Smart Rebalancing Engine ─────────────────────────────────────────────────

# Drift threshold: if any asset deviates more than this from target, flag for rebalance
_DRIFT_THRESHOLD_PCT: float = 5.0

# Minimum trade size in USD — smaller trades are suppressed (not cost-effective)
_MIN_TRADE_USD: float = 50.0


def compute_rebalancing_plan(
    user_id: str,
    portfolio_values_usd: dict[str, float],
    risk_profile: str,
) -> dict:
    """
    Compute a smart rebalancing plan for a multi-asset portfolio.

    Inputs:
        portfolio_values_usd  — dict of {asset: USD value}, e.g. {"gold": 5000, "stocks": 2000, "crypto": 500}
        risk_profile          — low / medium / high / aggressive

    Logic:
      1. Normalise current portfolio to percentages
      2. Compare each asset to its target allocation (from risk profile)
      3. Flag assets that have drifted beyond threshold
      4. Compute the exact USD buy/sell to reach target allocation
      5. Suppress trades below the minimum trade size

    Returns:
        total_portfolio_usd    — float
        current_allocation     — dict: current % per asset
        target_allocation      — dict: target % per asset
        drift                  — dict: deviation (current - target) per asset
        rebalance_needed       — bool
        trades                 — list of trade instructions
        summary                — str: human-readable summary
    """
    profile = risk_profile.lower()
    if profile not in RISK_PROFILES:
        raise ValueError(f"Unknown risk_profile: '{profile}'. Valid: {list(RISK_PROFILES.keys())}")

    # Compute totals
    total = sum(max(float(v), 0.0) for v in portfolio_values_usd.values())
    if total <= 0:
        raise ValueError("Portfolio total value must be greater than zero.")

    current_pct = {
        asset: round((float(portfolio_values_usd.get(asset, 0.0)) / total) * 100.0, 2)
        for asset in _ASSETS
    }
    target_pct = RISK_PROFILES[profile]

    # Drift per asset (positive = overweight, negative = underweight)
    drift = {
        asset: round(current_pct[asset] - target_pct[asset], 2)
        for asset in _ASSETS
    }

    rebalance_needed = any(abs(d) >= _DRIFT_THRESHOLD_PCT for d in drift.values())

    trades: list[dict] = []
    for asset in _ASSETS:
        target_usd = round(total * target_pct[asset] / 100.0, 2)
        current_usd = round(float(portfolio_values_usd.get(asset, 0.0)), 2)
        delta_usd = round(target_usd - current_usd, 2)

        if abs(delta_usd) < _MIN_TRADE_USD:
            continue  # suppress noise trades

        trades.append({
            "asset": asset,
            "action": "BUY" if delta_usd > 0 else "SELL",
            "amount_usd": abs(delta_usd),
            "current_usd": current_usd,
            "target_usd": target_usd,
            "drift_pct": drift[asset],
        })

    # Sort: largest trades first for execution priority
    trades.sort(key=lambda t: t["amount_usd"], reverse=True)

    if not rebalance_needed:
        summary = (
            f"Portfolio is within drift tolerance ({_DRIFT_THRESHOLD_PCT}% per asset). "
            "No rebalancing required."
        )
    elif trades:
        sells = [t for t in trades if t["action"] == "SELL"]
        buys = [t for t in trades if t["action"] == "BUY"]
        summary = (
            f"Rebalancing required: "
            f"{len(sells)} sell(s), {len(buys)} buy(s). "
            f"Total trade volume: ${sum(t['amount_usd'] for t in trades):,.2f}."
        )
    else:
        summary = "Drift detected but all trade amounts are below minimum trade size."

    logger.info(
        f"[INVESTMENT_AI] compute_rebalancing_plan | user_id={user_id} "
        f"profile={profile} total_usd={total:.2f} "
        f"rebalance_needed={rebalance_needed} trades={len(trades)}"
    )

    return {
        "total_portfolio_usd": round(total, 2),
        "current_allocation": current_pct,
        "target_allocation": dict(target_pct),
        "drift": drift,
        "rebalance_needed": rebalance_needed,
        "trades": trades,
        "summary": summary,
    }


# ─── Crowdfunding Project Scorer ──────────────────────────────────────────────

# Score weight breakdown (must sum to 100)
_CROWD_WEIGHTS = {
    "team_score":         25,   # team experience and track record
    "market_score":       20,   # total addressable market size
    "traction_score":     20,   # revenue / users / growth evidence
    "financials_score":   20,   # burn rate, runway, unit economics
    "risk_score":         15,   # regulatory, competitive, execution risk
}

_ROI_ANNUAL_MULTIPLIERS = {
    "A": (2.5, 5.0),    # grade A: 2.5x–5x annualised return estimate
    "B": (1.5, 2.5),
    "C": (1.0, 1.5),
    "D": (0.5, 1.0),
    "F": (0.0, 0.5),
}

_GRADE_BANDS = [
    (80, "A", "Excellent — low risk, high conviction"),
    (65, "B", "Good — moderate risk, solid fundamentals"),
    (50, "C", "Fair — notable risks, proceed with caution"),
    (35, "D", "Poor — significant concerns"),
    (0,  "F", "High Risk — not recommended"),
]


def score_crowdfunding_project(user_id: str, project_data: dict) -> dict:
    """
    Score a crowdfunding / startup investment opportunity for risk and ROI.

    Input project_data fields:
        team_experience_years (int)          — years of relevant experience
        previous_exits (int)                 — prior successful exits by founders
        market_size_usd_m (float)            — TAM in USD millions
        monthly_revenue_usd (float)          — current MRR
        monthly_growth_rate_pct (float)      — MoM revenue growth %
        runway_months (int)                  — months of cash remaining
        burn_rate_usd (float)                — monthly burn in USD
        num_competitors (int)                — direct competitor count
        has_regulatory_approval (bool)       — key permits in place
        sector (str)                         — fintech / proptech / healthtech / other

    Returns:
        composite_score (float, 0–100)
        grade (str): A / B / C / D / F
        grade_label (str)
        subscores (dict): per-dimension scores
        roi_estimate (dict): low / high annualised ROI estimate
        risk_flags (list[str]): active risk signals
        recommendation (str): invest / watchlist / avoid
    """
    risk_flags: list[str] = []

    # ── Team Score (0–25) ─────────────────────────────────────────────────────
    exp = int(project_data.get("team_experience_years", 0))
    exits = int(project_data.get("previous_exits", 0))
    team_raw = min(exp * 1.5 + exits * 8, 25)
    team_score = round(team_raw, 1)
    if exp < 3:
        risk_flags.append("Team has limited industry experience (< 3 years).")
    if exits == 0:
        risk_flags.append("No previous successful exits by founding team.")

    # ── Market Score (0–20) ───────────────────────────────────────────────────
    tam = float(project_data.get("market_size_usd_m", 0))
    if tam >= 1_000:
        market_score = 20.0
    elif tam >= 500:
        market_score = 16.0
    elif tam >= 100:
        market_score = 11.0
    elif tam >= 10:
        market_score = 6.0
    else:
        market_score = 2.0
        risk_flags.append(f"Small TAM (${tam:.0f}M) — limited growth ceiling.")

    # ── Traction Score (0–20) ─────────────────────────────────────────────────
    mrr = float(project_data.get("monthly_revenue_usd", 0))
    growth = float(project_data.get("monthly_growth_rate_pct", 0))
    traction_raw = min((mrr / 10_000) * 8 + (growth / 5) * 12, 20)
    traction_score = round(traction_raw, 1)
    if mrr == 0:
        risk_flags.append("No monthly revenue — pre-revenue stage.")
    if growth <= 0:
        risk_flags.append("Zero or negative monthly growth rate.")

    # ── Financials Score (0–20) ───────────────────────────────────────────────
    runway = int(project_data.get("runway_months", 0))
    burn = float(project_data.get("burn_rate_usd", 1))
    efficiency = mrr / burn if burn > 0 else 0
    runway_pts = min(runway / 2, 10)                        # up to 10 pts for runway
    efficiency_pts = min(efficiency * 10, 10)               # up to 10 pts for burn efficiency
    financials_score = round(runway_pts + efficiency_pts, 1)
    if runway < 6:
        risk_flags.append(f"Low runway ({runway} months) — near-term capital risk.")
    if efficiency < 0.5:
        risk_flags.append("Burn rate high relative to revenue — poor unit economics.")

    # ── Risk Score (0–15, inverted: lower risk → higher score) ────────────────
    competitors = int(project_data.get("num_competitors", 0))
    has_approval = bool(project_data.get("has_regulatory_approval", False))
    sector = str(project_data.get("sector", "other")).lower()

    risk_deductions = 0
    if competitors >= 10:
        risk_deductions += 5
        risk_flags.append(f"Highly competitive market ({competitors} direct competitors).")
    elif competitors >= 5:
        risk_deductions += 3
    if not has_approval and sector in ("fintech", "healthtech"):
        risk_deductions += 4
        risk_flags.append(f"No regulatory approval for {sector} — compliance risk.")
    inverted_risk = round(max(15 - risk_deductions, 0), 1)

    # ── Composite ─────────────────────────────────────────────────────────────
    subscores = {
        "team":       team_score,
        "market":     market_score,
        "traction":   traction_score,
        "financials": financials_score,
        "risk":       inverted_risk,
    }
    composite = round(sum(subscores.values()), 1)

    grade, grade_label = "F", "High Risk — not recommended"
    for threshold, g, label in _GRADE_BANDS:
        if composite >= threshold:
            grade, grade_label = g, label
            break

    # ROI estimate
    low_mult, high_mult = _ROI_ANNUAL_MULTIPLIERS[grade]
    roi_estimate = {
        "annual_return_low_pct": round((low_mult - 1) * 100, 0),
        "annual_return_high_pct": round((high_mult - 1) * 100, 0),
        "basis": "Historical comparable-stage returns by grade band. Not a guarantee.",
    }

    # Recommendation
    if grade in ("A", "B"):
        recommendation = "invest"
    elif grade == "C":
        recommendation = "watchlist"
    else:
        recommendation = "avoid"

    logger.info(
        f"[INVESTMENT_AI] score_crowdfunding_project | user_id={user_id} "
        f"grade={grade} composite={composite} recommendation={recommendation}"
    )

    return {
        "composite_score": composite,
        "grade": grade,
        "grade_label": grade_label,
        "subscores": subscores,
        "roi_estimate": roi_estimate,
        "risk_flags": risk_flags if risk_flags else ["No major risk flags detected."],
        "recommendation": recommendation,
    }
