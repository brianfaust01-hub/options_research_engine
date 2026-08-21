"""
Project Stonks
Opportunity Engine

Sprint 33A

Directional opportunity scoring.

The Opportunity Engine determines whether a security merits a
directional recommendation and constructs the corresponding trade.

Historical persistence is intentionally handled downstream after the
full research, option-selection, and portfolio-allocation pipeline has
completed.
"""

from trade_constructor import construct_trade


def calculate_directional_opportunity_scores(row) -> dict:
    """Calculate directional scores without losing momentum direction.

    New research rows provide MomentumDirection explicitly. The overall
    research Direction is a backward-compatible fallback for older callers.
    """

    trend = row["TrendScore"]
    momentum = row["MomentumScore"]
    momentum_direction = row.get(
        "MomentumDirection",
        row.get("Direction"),
    )
    liquidity = row["LiquidityScore"]
    strategy_score = row["StrategyScore"]

    bullish_score = 0
    bearish_score = 0

    #
    # Trend
    #

    if trend >= 70:
        bullish_score += 40
    elif trend >= 55:
        bullish_score += 25
    elif trend <= 30:
        bearish_score += 40
    elif trend <= 45:
        bearish_score += 25

    #
    # Momentum
    #

    if momentum_direction is None:
        # Preserve the legacy interpretation only for callers that provide
        # neither the new component direction nor the overall direction.
        if momentum >= 70:
            bullish_score += 35
        elif momentum >= 55:
            bullish_score += 20
        elif momentum <= 30:
            bearish_score += 35
        elif momentum <= 45:
            bearish_score += 20
        momentum_points = 0
    elif momentum >= 70:
        momentum_points = 35
    elif momentum >= 55:
        momentum_points = 20
    else:
        momentum_points = 0

    if momentum_direction == "Bullish":
        bullish_score += momentum_points
    elif momentum_direction == "Bearish":
        bearish_score += momentum_points

    #
    # Liquidity
    #

    if liquidity >= 20:
        bullish_score += 10
        bearish_score += 10

    #
    # Strategy quality bonus
    #

    if strategy_score >= 70:

        if bullish_score > bearish_score:
            bullish_score += 15

        elif bearish_score > bullish_score:
            bearish_score += 15

    winning_score = max(
        bullish_score,
        bearish_score,
    )

    losing_score = min(
        bullish_score,
        bearish_score,
    )

    conviction_gap = (
        winning_score
        - losing_score
    )

    return {
        "BullishScore": bullish_score,
        "BearishScore": bearish_score,
        "DirectionalConviction": conviction_gap,
        "WinningScore": winning_score,
    }


def evaluate_opportunities(row):
    scores = calculate_directional_opportunity_scores(row)

    bullish_score = scores["BullishScore"]
    bearish_score = scores["BearishScore"]
    conviction_gap = scores["DirectionalConviction"]
    winning_score = scores["WinningScore"]

    row["BullishScore"] = bullish_score
    row["BearishScore"] = bearish_score
    row["DirectionalConviction"] = conviction_gap

    #
    # Determine recommendation
    #

    if (
        bullish_score >= 75
        and conviction_gap >= 25
    ):

        row["OpportunityType"] = (
            "Long Call Candidate"
        )

        row["Action"] = "Evaluate Options"

        row["OpportunityScore"] = bullish_score

    elif (
        bearish_score >= 75
        and conviction_gap >= 25
    ):

        row["OpportunityType"] = (
            "Long Put Candidate"
        )

        row["Action"] = "Evaluate Options"

        row["OpportunityScore"] = bearish_score

    elif winning_score >= 55:

        row["OpportunityType"] = "Watchlist"

        row["Action"] = "Watch"

        row["OpportunityScore"] = winning_score

    else:

        row["OpportunityType"] = "No Clear Edge"

        row["Action"] = "Pass"

        row["OpportunityScore"] = winning_score

    #
    # Construct recommendation.
    #
    # No journaling occurs here.
    #
    # Historical persistence happens only after the
    # completed recommendation has passed through the
    # portfolio allocator and final enrichment stages.
    #

    return construct_trade(row)
