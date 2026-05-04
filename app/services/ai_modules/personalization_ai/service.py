"""
personalization_ai/service.py
──────────────────────────────
User-facing personalised financial insights and goal optimization engine.

Phase 3: Rule-based implementation — LLM / ML hooks provided for future upgrade.
"""

import math

from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Category Keywords (simple keyword-matching stub) ─────────────────────────
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "food":        ["restaurant", "cafe", "grocery", "food", "dining", "eat"],
    "travel":      ["hotel", "flight", "airline", "airbnb", "transport", "uber", "taxi"],
    "investment":  ["gold", "crypto", "stock", "etf", "fund", "portfolio"],
    "savings":     ["save", "deposit", "vault", "goal", "savings"],
    "utilities":   ["electricity", "water", "internet", "phone", "bill", "utility"],
    "shopping":    ["amazon", "shop", "retail", "purchase", "buy"],
    "other":       [],
}


def _categorize_transaction(description: str) -> str:
    desc = description.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in desc for kw in keywords):
            return category
    return "other"


# ─── Spending Pattern Analysis ────────────────────────────────────────────────

def analyze_spending_patterns(user_id: str, transaction_history: list) -> dict:
    """
    Categorise transactions and compute a spending/savings breakdown.

    Input transaction_history items expected format:
        [{"description": str, "amount": float, "type": "debit"|"credit"}, ...]

    Returns:
        categories (dict): spending per category in USD
        total_spent (float)
        total_saved (float)
        savings_rate (float): saved / (spent + saved), 0.0–1.0
        trend (str): growing_savings / declining_savings / stable / insufficient_data
        summary (str): human-readable behaviour summary

    TODO (ML): Replace keyword matching with NLP transaction classifier.
    Add time-series model for trend detection.
    """
    categories: dict[str, float] = {k: 0.0 for k in _CATEGORY_KEYWORDS}
    total_spent = 0.0
    total_saved = 0.0

    for tx in transaction_history:
        amount = float(tx.get("amount", 0.0))
        tx_type = str(tx.get("type", "debit")).lower()
        description = str(tx.get("description", ""))

        if tx_type == "credit":
            total_saved += amount
        else:
            total_spent += amount
            category = _categorize_transaction(description)
            categories[category] = round(categories[category] + amount, 2)

    # Remove zero categories for clean output
    categories = {k: v for k, v in categories.items() if v > 0}

    total = total_spent + total_saved
    savings_rate = round(total_saved / total, 4) if total > 0 else 0.0

    if not transaction_history:
        trend = "insufficient_data"
        summary = "No transaction history provided."
    elif savings_rate >= 0.3:
        trend = "growing_savings"
        summary = f"Strong savings behaviour — {savings_rate:.0%} of income saved."
    elif savings_rate >= 0.1:
        trend = "stable"
        summary = f"Moderate savings — {savings_rate:.0%} of income saved. Consider increasing gold/investment allocation."
    else:
        trend = "declining_savings"
        summary = f"Low savings rate ({savings_rate:.0%}). Recommend reviewing discretionary spending."

    logger.info(
        f"[PERSONALIZATION_AI] analyze_spending_patterns | user_id={user_id} "
        f"total_spent={total_spent:.2f} savings_rate={savings_rate:.2%} trend={trend}"
    )

    return {
        "categories": categories,
        "total_spent": round(total_spent, 2),
        "total_saved": round(total_saved, 2),
        "savings_rate": savings_rate,
        "trend": trend,
        "summary": summary,
    }


# ─── User Insights Generator ──────────────────────────────────────────────────

def generate_user_insights(user_id: str, user_data: dict) -> dict:
    """
    Generate personalised financial insights for the user dashboard.

    Signals evaluated:
      1. Savings rate — suggest increasing if low
      2. Investment exposure — flag if under-invested
      3. Gold allocation — suggest if no gold holdings
      4. Spending patterns — highlight top spending category

    Returns:
        insights (list[str]): actionable insight messages
        recommendations (list[str]): suggested next actions
        behavior_summary (str): one-line behavioural profile

    TODO (ML / LLM): Replace rule-based insights with LLM-generated personalised
    summaries using transaction context. Add goal-tracking progress integration.
    """
    insights: list[str] = []
    recommendations: list[str] = []

    savings_rate = float(user_data.get("savings_rate", 0.0))
    investment_pct = float(user_data.get("investment_allocation_pct", 0.0))
    gold_value_usd = float(user_data.get("gold_value_usd", 0.0))
    top_category = str(user_data.get("top_spending_category", "unknown"))

    # Insight 1: Savings rate
    if savings_rate < 0.10:
        insights.append(f"Your savings rate is {savings_rate:.0%} — below the recommended 10%.")
        recommendations.append("Set up an automated Save Now goal to target 15% monthly savings.")
    elif savings_rate >= 0.30:
        insights.append(f"Excellent savings discipline — {savings_rate:.0%} monthly savings rate.")

    # Insight 2: Investment exposure
    if investment_pct < 10.0:
        insights.append("Less than 10% of your portfolio is in growth assets (stocks/crypto).")
        recommendations.append(
            "Consider allocating a portion to your investment portfolio based on your risk profile."
        )

    # Insight 3: Gold holdings
    if gold_value_usd == 0:
        insights.append("You have no gold holdings — gold provides portfolio stability.")
        recommendations.append(
            "Explore gold allocation via the Aurix Vault to hedge against market volatility."
        )
    else:
        insights.append(f"Gold holdings: ${gold_value_usd:,.0f} — providing collateral value for loans.")

    # Insight 4: Top spending category
    if top_category not in ("unknown", "investment", "savings"):
        insights.append(f"Your top spending category this period is '{top_category}'.")
        if top_category in ("food", "shopping"):
            recommendations.append(
                f"Review your '{top_category}' spending — small reductions can significantly boost savings."
            )

    # Behaviour summary
    if savings_rate >= 0.3 and investment_pct >= 20:
        behavior_summary = "Disciplined saver and active investor — well-positioned for long-term growth."
    elif savings_rate >= 0.1:
        behavior_summary = "Moderate financial behaviour — room to grow investment and savings allocations."
    else:
        behavior_summary = "High spending relative to savings — consider a structured financial plan."

    if not insights:
        insights.append("Your financial profile looks balanced. Keep it up.")

    logger.info(
        f"[PERSONALIZATION_AI] generate_user_insights | user_id={user_id} "
        f"insights={len(insights)} recommendations={len(recommendations)}"
    )

    return {
        "insights": insights,
        "recommendations": recommendations,
        "behavior_summary": behavior_summary,
    }


# ─── Goal Optimization ────────────────────────────────────────────────────────

# Expected annual return rates by risk profile (post-cost estimates)
_PROFILE_RETURNS: dict[str, float] = {
    "low":        0.04,   # 4% — gold-heavy, conservative
    "medium":     0.07,   # 7% — balanced gold/stocks/crypto
    "high":       0.10,   # 10% — equity and crypto-weighted
    "aggressive": 0.14,   # 14% — high crypto / growth equity
}

# Recommended allocation per risk profile (mirrors investment_ai)
_PROFILE_ALLOCATIONS: dict[str, dict] = {
    "low":        {"gold": 70.0, "stocks": 20.0, "crypto": 10.0},
    "medium":     {"gold": 55.0, "stocks": 30.0, "crypto": 15.0},
    "high":       {"gold": 30.0, "stocks": 40.0, "crypto": 30.0},
    "aggressive": {"gold": 20.0, "stocks": 35.0, "crypto": 45.0},
}


def optimize_financial_goal(user_id: str, goal_data: dict) -> dict:
    """
    Compute the monthly savings and investment plan to reach a financial goal.

    Uses compound interest (future-value annuity formula):
        FV = PV*(1+r)^n + PMT * ((1+r)^n - 1) / r

    Solving for PMT (required monthly contribution):
        PMT = (FV - PV*(1+r)^n) * r / ((1+r)^n - 1)

    Inputs (from goal_data dict):
        target_amount (float)       — goal target in USD
        current_savings (float)     — current savings balance in USD
        monthly_income (float)      — monthly take-home income in USD
        monthly_expenses (float)    — fixed monthly expenses in USD
        risk_profile (str)          — low / medium / high / aggressive
        time_horizon_months (int)   — target months to reach goal

    Returns:
        required_monthly_savings  — float: how much to save per month
        is_achievable             — bool: within disposable income range
        recommended_allocation    — dict: how to split monthly savings
        monthly_allocation_usd    — dict: actual USD amounts per asset class
        projected_months_actual   — int: months to goal saving max disposable
        shortfall_or_surplus      — float: (surplus if positive, shortfall if negative)
        annual_return_assumption  — float: return rate used
        tips                      — list[str]: actionable suggestions
    """
    target_amount = float(goal_data.get("target_amount", 0.0))
    current_savings = float(goal_data.get("current_savings", 0.0))
    monthly_income = float(goal_data.get("monthly_income", 0.0))
    monthly_expenses = float(goal_data.get("monthly_expenses", 0.0))
    risk_profile = str(goal_data.get("risk_profile", "medium")).lower()
    time_horizon_months = int(goal_data.get("time_horizon_months", 12))

    # Validate inputs
    if risk_profile not in _PROFILE_RETURNS:
        risk_profile = "medium"
    if time_horizon_months < 1:
        time_horizon_months = 1

    disposable = max(0.0, monthly_income - monthly_expenses)
    annual_rate = _PROFILE_RETURNS[risk_profile]
    monthly_rate = annual_rate / 12.0
    n = time_horizon_months

    # Required PMT to reach target_amount in n months
    if monthly_rate > 0 and n > 0:
        growth_factor = (1 + monthly_rate) ** n
        pv_grown = current_savings * growth_factor
        gap = target_amount - pv_grown

        if gap <= 0:
            # Already there — current savings compound to target with no extra contributions
            required_monthly = 0.0
        else:
            annuity_factor = (growth_factor - 1) / monthly_rate
            required_monthly = round(gap / annuity_factor, 2)
    else:
        # Fallback: simple division
        gap = target_amount - current_savings
        required_monthly = round(max(0.0, gap) / n, 2)

    is_achievable = required_monthly <= disposable

    # How long will it take if user saves max disposable?
    if disposable > 0 and monthly_rate > 0:
        # Solve for n: FV = PV*(1+r)^n + PMT*((1+r)^n - 1)/r
        # Iterate (Newton would be cleaner; simple loop is fine for <600 months)
        balance = current_savings
        projected_months_actual = 0
        for _ in range(600):
            if balance >= target_amount:
                break
            balance = balance * (1 + monthly_rate) + disposable
            projected_months_actual += 1
        else:
            projected_months_actual = -1  # cannot reach goal in 50 years
    elif disposable > 0:
        gap = max(0.0, target_amount - current_savings)
        projected_months_actual = math.ceil(gap / disposable) if gap > 0 else 0
    else:
        projected_months_actual = -1

    # Shortfall or surplus vs required
    shortfall_or_surplus = round(disposable - required_monthly, 2)

    # Recommended allocation of the monthly savings amount
    allocation_pct = _PROFILE_ALLOCATIONS[risk_profile]
    save_amount = min(required_monthly, disposable) if is_achievable else disposable
    monthly_allocation_usd = {
        asset: round(save_amount * pct / 100.0, 2)
        for asset, pct in allocation_pct.items()
    }

    # Tips
    tips: list[str] = []
    if not is_achievable:
        tips.append(
            f"Required monthly savings ({required_monthly:.2f}) exceeds your disposable "
            f"income ({disposable:.2f}). Consider extending the time horizon or reducing "
            "the target amount."
        )
    if disposable < monthly_income * 0.10:
        tips.append(
            "Your monthly expenses are very high relative to income. "
            "Reducing fixed costs by 10% could significantly accelerate your goal."
        )
    if risk_profile in ("low",) and time_horizon_months > 36:
        tips.append(
            "For a long horizon (> 3 years), consider a medium risk profile "
            "to benefit from higher compound returns."
        )
    if projected_months_actual > 0 and projected_months_actual < time_horizon_months:
        tips.append(
            f"At maximum savings, you could reach your goal in {projected_months_actual} months "
            f"— {time_horizon_months - projected_months_actual} months ahead of target."
        )
    if current_savings >= target_amount:
        tips.append("Your current savings already meet the goal target. No additional contributions needed.")

    if not tips:
        tips.append(
            f"On track: save {required_monthly:.2f}/month and reach your goal "
            f"in {time_horizon_months} months."
        )

    logger.info(
        f"[PERSONALIZATION_AI] optimize_financial_goal | user_id={user_id} "
        f"target={target_amount:.2f} required_monthly={required_monthly:.2f} "
        f"achievable={is_achievable} horizon={time_horizon_months}mo"
    )

    return {
        "required_monthly_savings": required_monthly,
        "is_achievable": is_achievable,
        "recommended_allocation": allocation_pct,
        "monthly_allocation_usd": monthly_allocation_usd,
        "projected_months_actual": projected_months_actual,
        "shortfall_or_surplus": shortfall_or_surplus,
        "annual_return_assumption": annual_rate,
        "tips": tips,
    }
