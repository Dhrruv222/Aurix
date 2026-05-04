"""
credit_ai/service.py
────────────────────
Gold-backed loan eligibility and alternative credit scoring engine.

Phase 3: Rule-based implementation — ML hooks provided for future upgrade.
"""

from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Scoring Weights ──────────────────────────────────────────────────────────
_MAX_SCORE = 100
_LTV_MAX = 0.75          # max allowed loan-to-value ratio for gold-backed loans
_MIN_ELIGIBLE_SCORE = 50 # minimum credit score to qualify for any loan product

# Grade bands
_GRADE_BANDS = [
    (80, "A", "Excellent"),
    (65, "B", "Good"),
    (50, "C", "Fair"),
    (35, "D", "Poor"),
    (0,  "E", "Very Poor"),
]


# ─── Credit Scoring ───────────────────────────────────────────────────────────

def compute_credit_score(user_id: str, user_data: dict) -> dict:
    """
    Alternative credit scoring using non-traditional financial signals.

    Signals evaluated:
      1. Savings rate     — consistent saving behaviour (up to 30 pts)
      2. Gold holdings    — collateral quality (up to 25 pts)
      3. Repayment history — on-time repayments (up to 25 pts)
      4. Account tenure   — length of relationship (up to 20 pts)

    Returns:
        credit_score (int, 0–100)
        grade (str): A / B / C / D / E
        grade_label (str): Excellent / Good / Fair / Poor / Very Poor
        factors (list[str]): Score contribution explanations

    TODO (ML): Replace with XGBoost / LightGBM trained on labelled credit data.
    Add open-banking transaction enrichment for richer features.
    """
    score = 0
    factors: list[str] = []

    # Signal 1: Savings rate (0.0–1.0)
    savings_rate = float(user_data.get("savings_rate", 0.0))
    savings_pts = round(min(savings_rate, 1.0) * 30)
    score += savings_pts
    if savings_pts > 0:
        factors.append(f"Savings rate {savings_rate:.0%} contributes {savings_pts}/30 pts.")
    else:
        factors.append("No savings history detected (0/30 pts).")

    # Signal 2: Gold holdings in USD equivalent
    gold_value = float(user_data.get("gold_value_usd", 0.0))
    if gold_value >= 10000:
        gold_pts = 25
    elif gold_value >= 5000:
        gold_pts = 15
    elif gold_value >= 1000:
        gold_pts = 8
    else:
        gold_pts = 0
    score += gold_pts
    factors.append(f"Gold holdings ${gold_value:,.0f} contributes {gold_pts}/25 pts.")

    # Signal 3: Repayment history (0–100% on-time rate)
    repayment_rate = float(user_data.get("repayment_rate", 0.0))
    repayment_pts = round(min(repayment_rate, 1.0) * 25)
    score += repayment_pts
    factors.append(
        f"Repayment history {repayment_rate:.0%} contributes {repayment_pts}/25 pts."
    )

    # Signal 4: Account tenure in months
    tenure_months = int(user_data.get("tenure_months", 0))
    if tenure_months >= 24:
        tenure_pts = 20
    elif tenure_months >= 12:
        tenure_pts = 12
    elif tenure_months >= 6:
        tenure_pts = 6
    else:
        tenure_pts = 0
    score += tenure_pts
    factors.append(f"Account tenure {tenure_months} months contributes {tenure_pts}/20 pts.")

    score = min(score, _MAX_SCORE)

    # Derive grade
    grade, grade_label = "E", "Very Poor"
    for threshold, g, label in _GRADE_BANDS:
        if score >= threshold:
            grade, grade_label = g, label
            break

    logger.info(
        f"[CREDIT_AI] compute_credit_score | user_id={user_id} "
        f"score={score} grade={grade}"
    )

    return {
        "credit_score": score,
        "grade": grade,
        "grade_label": grade_label,
        "factors": factors,
    }


# ─── Loan Eligibility ─────────────────────────────────────────────────────────

def assess_loan_eligibility(user_id: str, loan_request: dict) -> dict:
    """
    Assess eligibility for gold-backed loan products.

    Logic:
      1. Require minimum credit score (>= 50)
      2. Calculate max loan from gold holdings via LTV ratio (max 75%)
      3. Suggest risk-based interest rate: lower score → higher rate

    Returns:
        eligible (bool)
        decision (str): APPROVED / REJECTED
        max_loan_amount (float): maximum loan value in USD
        suggested_rate (float | None): annual interest rate %
        reasons (list[str]): decision explanation

    TODO (ML): Replace with affordability model incorporating income signals,
    open-banking data, and dynamic LTV curves per gold price.
    """
    reasons: list[str] = []

    credit_score = int(loan_request.get("credit_score", 0))
    gold_value_usd = float(loan_request.get("gold_value_usd", 0.0))
    requested_amount = float(loan_request.get("requested_amount", 0.0))

    # Check 1: Minimum credit score
    if credit_score < _MIN_ELIGIBLE_SCORE:
        reasons.append(
            f"Credit score {credit_score} is below minimum threshold {_MIN_ELIGIBLE_SCORE}."
        )
        logger.info(
            f"[CREDIT_AI] assess_loan_eligibility | user_id={user_id} "
            f"decision=REJECTED reason=low_credit_score score={credit_score}"
        )
        return {
            "eligible": False,
            "decision": "REJECTED",
            "max_loan_amount": 0.0,
            "suggested_rate": None,
            "reasons": reasons,
        }

    # Check 2: LTV-based maximum loan
    max_loan = round(gold_value_usd * _LTV_MAX, 2)
    if requested_amount > max_loan:
        reasons.append(
            f"Requested amount {requested_amount:.2f} exceeds max LTV-based loan {max_loan:.2f} "
            f"(75% of gold value {gold_value_usd:.2f})."
        )
        eligible = False
        decision = "REJECTED"
    else:
        reasons.append(
            f"Requested amount {requested_amount:.2f} is within max loan limit {max_loan:.2f}."
        )
        eligible = True
        decision = "APPROVED"

    # Risk-based interest rate
    if eligible:
        if credit_score >= 80:
            rate = 4.5
        elif credit_score >= 65:
            rate = 6.5
        elif credit_score >= 50:
            rate = 9.0
        else:
            rate = None
        reasons.append(f"Credit score {credit_score} → suggested annual rate {rate}%.")
    else:
        rate = None

    logger.info(
        f"[CREDIT_AI] assess_loan_eligibility | user_id={user_id} "
        f"decision={decision} max_loan={max_loan} rate={rate}"
    )

    return {
        "eligible": eligible,
        "decision": decision,
        "max_loan_amount": max_loan,
        "suggested_rate": rate,
        "reasons": reasons,
    }


# ─── Save Now, Buy Later (SNBL) Approval Engine ───────────────────────────────

# SNBL-specific thresholds (more lenient than full loan product)
_SNBL_MIN_CREDIT_SCORE = 40          # lower entry bar than standard loans
_SNBL_MAX_DTI_RATIO = 0.40           # instalment must be ≤ 40% of disposable income
_SNBL_MAX_ITEM_MULTIPLIER = 6.0      # item price ≤ 6× monthly disposable income
_SNBL_COLLATERAL_DISCOUNT = 0.10     # rate reduction if gold covers ≥ 50% of item price


def compute_snbl_approval(user_id: str, snbl_data: dict) -> dict:
    """
    Save Now, Buy Later affordability engine.

    How it works:
      - User picks an item and a number of monthly instalments (1–36).
      - We check whether the monthly instalment fits within their budget.
      - A credit score is computed from their financial profile.
      - We generate a full instalment schedule with optional gold-collateral discount.

    Input fields (snbl_data):
        item_price_usd      (float) — purchase price of the item
        num_instalments     (int)   — 1–36 monthly instalments
        monthly_income      (float) — net monthly income in USD
        monthly_expenses    (float) — fixed monthly outgoings in USD
        savings_rate        (float, 0–1) — current savings rate
        gold_value_usd      (float) — gold held as potential collateral
        repayment_rate      (float, 0–1) — historical repayment rate
        tenure_months       (int)   — account tenure

    Returns:
        approved            (bool)
        decision            (str): APPROVED / DECLINED
        credit_score        (int, 0–100)
        credit_grade        (str): A–E
        monthly_instalment  (float): USD per instalment
        total_cost_usd      (float): total amount paid
        platform_fee_pct    (float): % fee charged (0 if gold-collateralised)
        platform_fee_usd    (float)
        max_item_value_usd  (float): max item price this user can afford via SNBL
        instalment_schedule (list[dict]): full month-by-month plan
        decline_reasons     (list[str])
        notes               (list[str])
    """
    notes: list[str] = []
    decline_reasons: list[str] = []

    item_price = float(snbl_data.get("item_price_usd", 0))
    num_instalments = max(1, min(int(snbl_data.get("num_instalments", 12)), 36))
    monthly_income = float(snbl_data.get("monthly_income", 0))
    monthly_expenses = float(snbl_data.get("monthly_expenses", 0))
    gold_value = float(snbl_data.get("gold_value_usd", 0))

    # ── Credit scoring ────────────────────────────────────────────────────────
    credit_profile = {
        "savings_rate":    float(snbl_data.get("savings_rate", 0)),
        "gold_value_usd":  gold_value,
        "repayment_rate":  float(snbl_data.get("repayment_rate", 0)),
        "tenure_months":   int(snbl_data.get("tenure_months", 0)),
    }
    credit_result = compute_credit_score(user_id, credit_profile)
    credit_score = credit_result["credit_score"]
    credit_grade = credit_result["grade"]

    # ── Disposable income and affordability ───────────────────────────────────
    disposable = max(0.0, monthly_income - monthly_expenses)
    monthly_instalment = round(item_price / num_instalments, 2) if num_instalments > 0 else item_price
    dti_ratio = monthly_instalment / disposable if disposable > 0 else float("inf")
    max_item_value = round(disposable * _SNBL_MAX_DTI_RATIO * num_instalments, 2)

    # ── Platform fee (waived if gold covers ≥ 50% of item price) ─────────────
    gold_covers_half = gold_value >= item_price * 0.5
    if gold_covers_half:
        platform_fee_pct = 0.0
        notes.append(
            "Gold collateral covers ≥ 50% of item price — platform fee waived."
        )
    else:
        # Fee scales from 1% (36 instalments) to 3% (1 instalment)
        platform_fee_pct = round(3.0 - (num_instalments / 36) * 2.0, 2)
        notes.append(
            f"Platform fee of {platform_fee_pct:.1f}% applied "
            f"(add gold collateral to waive)."
        )

    platform_fee_usd = round(item_price * platform_fee_pct / 100, 2)
    total_cost = round(item_price + platform_fee_usd, 2)
    total_instalment = round(total_cost / num_instalments, 2)

    # ── Decision checks ───────────────────────────────────────────────────────
    if credit_score < _SNBL_MIN_CREDIT_SCORE:
        decline_reasons.append(
            f"Credit score {credit_score} is below SNBL minimum ({_SNBL_MIN_CREDIT_SCORE})."
        )

    if dti_ratio > _SNBL_MAX_DTI_RATIO:
        decline_reasons.append(
            f"Monthly instalment ${monthly_instalment:,.2f} exceeds "
            f"{_SNBL_MAX_DTI_RATIO:.0%} of disposable income "
            f"${disposable:,.2f} (DTI ratio: {dti_ratio:.0%}). "
            f"Consider increasing instalments or choosing a lower-priced item."
        )

    if disposable <= 0:
        decline_reasons.append(
            "Monthly expenses exceed income — insufficient disposable income."
        )

    if item_price <= 0:
        decline_reasons.append("Item price must be greater than zero.")

    approved = len(decline_reasons) == 0
    decision = "APPROVED" if approved else "DECLINED"

    # ── Instalment schedule ───────────────────────────────────────────────────
    schedule: list[dict] = []
    if approved:
        for i in range(1, num_instalments + 1):
            # Last instalment absorbs any rounding remainder
            if i == num_instalments:
                instalment_amount = round(total_cost - total_instalment * (num_instalments - 1), 2)
            else:
                instalment_amount = total_instalment
            schedule.append({
                "instalment_number": i,
                "month_offset": i,
                "amount_usd": instalment_amount,
            })

    if approved:
        notes.append(
            f"Approved: ${item_price:,.2f} item payable over {num_instalments} month(s), "
            f"${total_instalment:,.2f}/month. Total cost: ${total_cost:,.2f}."
        )

    logger.info(
        f"[CREDIT_AI] compute_snbl_approval | user_id={user_id} "
        f"decision={decision} credit_score={credit_score} "
        f"item_price={item_price} instalments={num_instalments} "
        f"dti={dti_ratio:.2f}"
    )

    return {
        "approved": approved,
        "decision": decision,
        "credit_score": credit_score,
        "credit_grade": credit_grade,
        "monthly_instalment": total_instalment,
        "total_cost_usd": total_cost,
        "platform_fee_pct": platform_fee_pct,
        "platform_fee_usd": platform_fee_usd,
        "max_item_value_usd": max_item_value,
        "instalment_schedule": schedule,
        "decline_reasons": decline_reasons,
        "notes": notes,
    }
