"""
Project Stonks
Trade Quality Engine

Sprint 24

Produces a standardized quality score (0-100) for every executable trade.

This score is intentionally separate from:

- Opportunity Score
- Allocation Score

Opportunity Score:
    Should we investigate this trade?

Allocation Score:
    If capital is limited, should we allocate?

Trade Quality:
    How objectively good is this setup?
"""


def _extract_note(notes, prefix):

    if not isinstance(notes, list):
        return None

    for note in notes:

        if isinstance(note, str) and note.startswith(prefix):
            return note.replace(prefix, "").strip()

    return None


def _extract_numeric(notes, prefix):

    value = _extract_note(notes, prefix)

    if value is None:
        return None

    value = (
        value.replace("%", "")
        .replace("$", "")
        .replace("of premium per day", "")
        .strip()
    )

    try:
        return float(value)

    except ValueError:
        return None


def evaluate_trade_quality(trade, market_context=None, breadth=None):

    score = 0
    reasons = []

    #########################################
    # Research confidence (0-30)
    #########################################

    confidence = trade.confidence

    score += confidence * 0.30

    #########################################
    # Contract quality (0-25)
    #########################################

    contract_score = _extract_numeric(
        trade.notes,
        "Contract Score:"
    )

    if contract_score is not None:

        score += contract_score * 0.25

        if contract_score >= 90:
            reasons.append("Excellent option contract")

    #########################################
    # Delta (0-10)
    #########################################

    delta = _extract_numeric(
        trade.notes,
        "Delta:"
    )

    if delta is not None:

        delta = abs(delta)

        if 0.35 <= delta <= 0.50:
            score += 10
            reasons.append("Ideal delta")

        elif 0.25 <= delta <= 0.60:
            score += 6

    #########################################
    # Theta drag (0-10)
    #########################################

    theta_drag = _extract_numeric(
        trade.notes,
        "Theta drag:"
    )

    if theta_drag is not None:

        if theta_drag <= 2:
            score += 10
            reasons.append("Low theta decay")

        elif theta_drag <= 3:
            score += 6

        elif theta_drag > 4:
            score -= 5

    #########################################
    # Liquidity (0-10)
    #########################################

    spread = _extract_numeric(
        trade.notes,
        "Spread %:"
    )

    if spread is not None:

        if spread <= 0.05:
            score += 10
            reasons.append("Excellent liquidity")

        elif spread <= 0.10:
            score += 7

        elif spread <= 0.15:
            score += 5

    #########################################
    # Market alignment (0-10)
    #########################################

    if market_context is not None:

        if (
            market_context.get("market_regime") == "Bullish"
            and trade.option_strategy == "Long Call"
        ):
            score += 10
            reasons.append("Aligned with market")

        if (
            market_context.get("market_regime") == "Bearish"
            and trade.option_strategy == "Long Put"
        ):
            score += 10
            reasons.append("Aligned with market")

    #########################################
    # Breadth confirmation (0-5)
    #########################################

    if breadth is not None:

        if breadth.get("BreadthScore", 0) >= 70:
            score += 5
            reasons.append("Strong market breadth")

    #########################################

    score = max(0, min(round(score), 100))

    if score >= 90:
        grade = "A+"

    elif score >= 80:
        grade = "A"

    elif score >= 70:
        grade = "B"

    elif score >= 60:
        grade = "C"

    else:
        grade = "D"

    return {
        "score": score,
        "grade": grade,
        "reasons": reasons,
    }