"""
Project Stonks
Opportunity Engine
"""

from trade_constructor import construct_trade
from trade_journal import log_trade_recommendation


def evaluate_opportunities(row):

    trend = row["TrendScore"]
    momentum = row["MomentumScore"]
    liquidity = row["LiquidityScore"]
    confidence = row["StrategyScore"]

    long_call_score = 0
    long_put_score = 0
    watch_score = confidence

    if trend >= 50:
        long_call_score += 35
    else:
        long_put_score += 35

    if momentum >= 50:
        long_call_score += 35
    else:
        long_put_score += 35

    if liquidity >= 20:
        long_call_score += 15
        long_put_score += 15

    if confidence >= 70:
        long_call_score += 15
        long_put_score += 15

    if long_call_score >= 75:
        row["OpportunityType"] = "Long Call Candidate"
        row["Action"] = "Evaluate Options"
        row["OpportunityScore"] = long_call_score

    elif long_put_score >= 75:
        row["OpportunityType"] = "Long Put Candidate"
        row["Action"] = "Evaluate Options"
        row["OpportunityScore"] = long_put_score

    elif watch_score >= 55:
        row["OpportunityType"] = "Watchlist"
        row["Action"] = "Watch"
        row["OpportunityScore"] = watch_score

    else:
        row["OpportunityType"] = "No Clear Edge"
        row["Action"] = "Pass"
        row["OpportunityScore"] = max(
            long_call_score,
            long_put_score,
            watch_score,
        )

    trade = construct_trade(row)

    if row["Action"] in ["Evaluate Options", "Watch"]:
        log_trade_recommendation(trade)

    return trade