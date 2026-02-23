def score_transaction(amount: float, currency: str, location: str | None) -> tuple[int, str, list[str]]:
    reasons = []

    # Simple deterministic MVP (replace later with ML)
    risk = 10

    if amount >= 5000:
        risk += 35
        reasons.append("High amount (>= 5000)")

    if location is None:
        risk += 10
        reasons.append("Missing location")

    if currency not in ("EUR", "USD", "GBP"):
        risk += 10
        reasons.append(f"Unusual currency: {currency}")

    risk = max(0, min(100, risk))

    if risk <= 40:
        decision = "APPROVE"
    elif risk <= 70:
        decision = "REVIEW"
    else:
        decision = "BLOCK"

    if not reasons:
        reasons.append("No risk signals detected (MVP rules)")

    return risk, decision, reasons
