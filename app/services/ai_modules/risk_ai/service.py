"""
risk_ai/service.py
──────────────────
Anomaly detection, AML pattern checking, and compliance reporting engine.

Phase 3: Rule-based implementation — ML hooks provided for future upgrade.
"""

import hashlib
from datetime import datetime, timezone

from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Thresholds (tune via config in later phases) ─────────────────────────────
_ANOMALY_HIGH_AMOUNT = 15000.0      # single transaction flag
_ANOMALY_RAPID_COUNT = 5            # transactions in one request payload
_AML_STRUCTURING_BAND = (9000.0, 10000.0)  # just-below-10k structuring band
_AML_ROUND_AMOUNT_THRESHOLD = 5000.0        # suspiciously round large amounts

# Known high-risk jurisdictions (mirrors core_ai)
_HIGH_RISK_LOCATIONS = frozenset({"KP", "IR", "SY", "CU", "SD", "MM"})


# ─── Anomaly Detection ────────────────────────────────────────────────────────

def detect_anomaly(user_id: str, transaction_data: dict) -> dict:
    """
    Rule-based anomaly detection across transaction signals.

    Evaluated signals:
      1. Amount spike — single transaction above high-amount threshold
      2. Rapid burst  — unusually high transaction count in payload
      3. Location     — high-risk jurisdiction
      4. Off-hours    — transaction hour outside 06:00–22:00

    Returns:
        anomaly_detected (bool)
        anomaly_score (float, 0–100)
        flags (list[str]) — active anomaly descriptions

    TODO (ML): Replace with Isolation Forest / Autoencoder trained on
    per-user behavioural baselines. Add Redis velocity counters.
    """
    flags: list[str] = []
    score = 0.0

    amount = float(transaction_data.get("amount", 0))
    location = str(transaction_data.get("location") or "").upper()
    hour = int(transaction_data.get("hour_of_day", 12))  # 0–23
    tx_count = int(transaction_data.get("recent_tx_count", 1))

    # Signal 1: Amount spike
    if amount > _ANOMALY_HIGH_AMOUNT:
        score += 40.0
        flags.append(f"Transaction amount {amount:.2f} exceeds anomaly threshold {_ANOMALY_HIGH_AMOUNT:.2f}.")

    # Signal 2: Rapid transaction burst
    if tx_count >= _ANOMALY_RAPID_COUNT:
        score += 25.0
        flags.append(f"High transaction velocity: {tx_count} recent transactions detected.")

    # Signal 3: High-risk location
    if location in _HIGH_RISK_LOCATIONS:
        score += 25.0
        flags.append(f"Transaction from high-risk jurisdiction: {location}.")

    # Signal 4: Off-hours activity
    if hour < 6 or hour > 22:
        score += 10.0
        flags.append(f"Transaction at unusual hour: {hour:02d}:xx (outside 06:00–22:00).")

    score = round(min(score, 100.0), 2)
    anomaly_detected = score >= 40.0

    logger.info(
        f"[RISK_AI] detect_anomaly | user_id={user_id} "
        f"score={score} anomaly_detected={anomaly_detected} flags={len(flags)}"
    )

    return {
        "anomaly_detected": anomaly_detected,
        "anomaly_score": score,
        "flags": flags if flags else ["No anomaly signals detected."],
    }


# ─── AML Pattern Detection ────────────────────────────────────────────────────

def check_aml_patterns(user_id: str, transaction_data: dict) -> dict:
    """
    Rule-based AML (Anti-Money Laundering) pattern detection.

    Patterns checked:
      1. Structuring — amount just below reporting threshold (9k–10k)
      2. Round-amount — suspiciously round large transaction
      3. High-risk jurisdiction — OFAC / FATF flagged country
      4. Multiple currencies — multiple currencies in one transaction context

    Returns:
        aml_flag (bool)
        risk_level (str): LOW / MEDIUM / HIGH
        patterns (list[str]) — matched AML pattern descriptions

    TODO (ML): Replace with graph-based network analysis model.
    Add cross-user transaction graph traversal for layering detection.
    """
    patterns: list[str] = []
    risk_points = 0

    amount = float(transaction_data.get("amount", 0))
    location = str(transaction_data.get("location") or "").upper()
    currencies_used = transaction_data.get("currencies_used", [])

    # Pattern 1: Structuring (just below 10k)
    low, high = _AML_STRUCTURING_BAND
    if low <= amount < high:
        risk_points += 40
        patterns.append(
            f"Structuring pattern: amount {amount:.2f} is just below the reporting threshold."
        )

    # Pattern 2: Suspicious round amount
    if amount >= _AML_ROUND_AMOUNT_THRESHOLD and amount % 1000 == 0:
        risk_points += 20
        patterns.append(f"Round-amount pattern: {amount:.2f} is a suspiciously round large sum.")

    # Pattern 3: High-risk jurisdiction
    if location in _HIGH_RISK_LOCATIONS:
        risk_points += 30
        patterns.append(f"High-risk jurisdiction: {location} is on the AML watchlist.")

    # Pattern 4: Multiple currencies
    if isinstance(currencies_used, list) and len(currencies_used) > 2:
        risk_points += 10
        patterns.append(
            f"Multiple currencies detected: {currencies_used} — possible layering signal."
        )

    if risk_points >= 60:
        risk_level = "HIGH"
    elif risk_points >= 30:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    aml_flag = risk_level in ("MEDIUM", "HIGH")

    logger.info(
        f"[RISK_AI] check_aml_patterns | user_id={user_id} "
        f"risk_level={risk_level} aml_flag={aml_flag} patterns={len(patterns)}"
    )

    return {
        "aml_flag": aml_flag,
        "risk_level": risk_level,
        "patterns": patterns if patterns else ["No AML patterns detected."],
    }


# ─── Regulatory Compliance Report ────────────────────────────────────────────

def generate_compliance_report(
    report_id: str,
    transactions: list[dict],
    reporting_period: str = "",
) -> dict:
    """
    Aggregate a batch of transactions through the risk engine and generate a
    structured regulatory compliance report ready for submission or audit.

    Each transaction dict should contain:
        transaction_id  (str)
        user_id         (str)
        amount          (float)
        location        (str, 2-char ISO)
        hour_of_day     (int, 0–23)
        recent_tx_count (int)
        currencies_used (list[str])

    Report output:
        report_id               — deterministic SHA-256 fingerprint
        generated_at            — ISO timestamp
        reporting_period        — supplied label (e.g. "2026-04")
        total_transactions      — int
        flagged_count           — int
        high_risk_count         — int
        medium_risk_count       — int
        clean_count             — int
        flagged_transactions    — list of flagged entries with full detail
        risk_summary_by_user    — aggregated per-user flag counts
        top_risk_patterns       — ranked list of most common AML/anomaly patterns
        recommendations         — list of recommended actions
    """
    flagged: list[dict] = []
    pattern_counter: dict[str, int] = {}
    user_flag_counts: dict[str, int] = {}

    for tx in transactions:
        tx_id = str(tx.get("transaction_id", "unknown"))
        user_id = str(tx.get("user_id", "unknown"))

        anomaly = detect_anomaly(user_id, tx)
        aml = check_aml_patterns(user_id, tx)

        is_flagged = anomaly["anomaly_detected"] or aml["aml_flag"]

        if is_flagged:
            # Determine composite risk level
            if aml["risk_level"] == "HIGH" or anomaly["anomaly_score"] >= 65:
                composite_risk = "HIGH"
            elif aml["risk_level"] == "MEDIUM" or anomaly["anomaly_score"] >= 40:
                composite_risk = "MEDIUM"
            else:
                composite_risk = "LOW"

            all_patterns = (
                [f for f in anomaly["flags"] if "No anomaly" not in f]
                + [p for p in aml["patterns"] if "No AML" not in p]
            )

            flagged.append({
                "transaction_id": tx_id,
                "user_id": user_id,
                "amount": tx.get("amount"),
                "location": tx.get("location"),
                "composite_risk_level": composite_risk,
                "anomaly_score": anomaly["anomaly_score"],
                "aml_risk_level": aml["risk_level"],
                "patterns_detected": all_patterns,
                "recommended_action": (
                    "ESCALATE_TO_COMPLIANCE" if composite_risk == "HIGH"
                    else "MANUAL_REVIEW"
                ),
            })

            # Tally patterns for frequency analysis
            for pattern in all_patterns:
                # Use only the first ~60 chars as a key to group similar messages
                key = pattern[:60]
                pattern_counter[key] = pattern_counter.get(key, 0) + 1

            # Per-user flag tally
            user_flag_counts[user_id] = user_flag_counts.get(user_id, 0) + 1

    high_risk_count = sum(1 for f in flagged if f["composite_risk_level"] == "HIGH")
    medium_risk_count = sum(1 for f in flagged if f["composite_risk_level"] == "MEDIUM")
    clean_count = len(transactions) - len(flagged)

    # Top risk patterns sorted by frequency
    top_patterns = sorted(
        [{"pattern": k, "occurrences": v} for k, v in pattern_counter.items()],
        key=lambda x: x["occurrences"],
        reverse=True,
    )[:10]

    # Risk summary per user (only flagged users)
    risk_summary_by_user = [
        {"user_id": uid, "flagged_transaction_count": count}
        for uid, count in sorted(user_flag_counts.items(), key=lambda x: -x[1])
    ]

    # Recommendations
    recommendations: list[str] = []
    if high_risk_count > 0:
        recommendations.append(
            f"{high_risk_count} HIGH-RISK transaction(s) require immediate escalation "
            "to the compliance officer."
        )
    if medium_risk_count > 0:
        recommendations.append(
            f"{medium_risk_count} MEDIUM-RISK transaction(s) flagged for manual review "
            "within 48 hours."
        )
    if clean_count == len(transactions):
        recommendations.append(
            "All transactions passed risk screening — no regulatory action required."
        )
    if top_patterns:
        most_common = top_patterns[0]["pattern"]
        recommendations.append(
            f"Most frequent risk pattern: \"{most_common}\" — "
            "consider policy review or enhanced monitoring."
        )

    # Deterministic report fingerprint (SHA-256 of report_id + transaction IDs)
    fingerprint_input = report_id + "".join(
        str(tx.get("transaction_id", "")) for tx in transactions
    )
    fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()[:16]

    generated_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        f"[RISK_AI] generate_compliance_report | report_id={report_id} "
        f"total={len(transactions)} flagged={len(flagged)} "
        f"high={high_risk_count} medium={medium_risk_count}"
    )

    return {
        "report_id": report_id,
        "report_fingerprint": fingerprint,
        "generated_at": generated_at,
        "reporting_period": reporting_period or "unspecified",
        "total_transactions": len(transactions),
        "flagged_count": len(flagged),
        "high_risk_count": high_risk_count,
        "medium_risk_count": medium_risk_count,
        "clean_count": clean_count,
        "flagged_transactions": flagged,
        "risk_summary_by_user": risk_summary_by_user,
        "top_risk_patterns": top_patterns,
        "recommendations": recommendations,
    }
