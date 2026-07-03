"""
Project Stonks
Opportunity Engine

Sprint 19:
Directional scoring with structured journaling support.
"""

from trade_constructor import construct_trade
from trade_journal import log_trade_recommendation


def evaluate_opportunities(row):
    trend = row["TrendScore"]
    momentum = row["MomentumScore"]
    liquidity = row["LiquidityScore"]
    strategy_score = row["StrategyScore"]

    bullish_score = 0
    bearish_score = 0

    if trend >= 70:
        bullish_score += 40
    elif trend >= 55:
        bullish_score += 25
    elif trend <= 30:
        bearish_score += 40
    elif trend <= 45:
        bearish_score += 25

    if momentum >= 70:
        bullish_score += 35
    elif momentum >= 55:
        bullish_score += 20
    elif momentum <= 30:
        bearish_score += 35
    elif momentum <= 45:
        bearish_score += 20

    if liquidity >= 20:
        bullish_score += 10
        bearish_score += 10

    if strategy_score >= 70:
        if bullish_score > bearish_score:
            bullish_score += 15
        elif bearish_score > bullish_score:
            bearish_score += 15

    winning_score = max(bullish_score, bearish_score)
    losing_score = min(bullish_score, bearish_score)
    conviction_gap = winning_score - losing_score

    row["BullishScore"] = bullish_score
    row["BearishScore"] = bearish_score
    row["DirectionalConviction"] = conviction_gap

    if bullish_score >= 75 and conviction_gap >= 25:
        row["OpportunityType"] = "Long Call Candidate"
        row["Action"] = "Evaluate Options"
        row["OpportunityScore"] = bullish_score

    elif bearish_score >= 75 and conviction_gap >= 25:
        row["OpportunityType"] = "Long Put Candidate"
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

    trade = construct_trade(row)

    if row["Action"] in ["Evaluate Options", "Watch"]:
        log_trade_recommendation(trade)

    return trade