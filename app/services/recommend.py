def recommend(portfolio: dict[str, float], risk_profile: str) -> tuple[dict[str, float], list[str]]:
    notes = []

    # Normalize input portfolio (if not summing to 100)
    total = sum(portfolio.values()) if portfolio else 0
    if total <= 0:
        portfolio = {"gold": 50, "stocks": 30, "crypto": 20}
        total = 100
        notes.append("Portfolio missing; using default allocation")

    norm = {k: (v / total) * 100 for k, v in portfolio.items()}

    if risk_profile == "low":
        rec = {"gold": 65, "stocks": 25, "crypto": 10}
        notes.append("Low risk profile → higher gold allocation")
    elif risk_profile == "high":
        rec = {"gold": 40, "stocks": 35, "crypto": 25}
        notes.append("High risk profile → higher growth assets")
    else:
        rec = {"gold": 55, "stocks": 30, "crypto": 15}
        notes.append("Medium risk profile → balanced allocation")

    notes.append(f"Current allocation: {norm}")
    return rec, notes
