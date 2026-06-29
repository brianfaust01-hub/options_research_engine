"""
Project Stonks
Opportunity Engine

Converts research evidence into possible options opportunities.
"""


def evaluate_opportunities(row) -> dict:
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
        return {
            "OpportunityType": "Long Call Candidate",
            "Action": "Evaluate Options",
            "OpportunityScore": long_call_score,
        }

    if long_put_score >= 75:
        return {
            "OpportunityType": "Long Put Candidate",
            "Action": "Evaluate Options",
            "OpportunityScore": long_put_score,
        }

    if watch_score >= 55:
        return {
            "OpportunityType": "Watchlist",
            "Action": "Watch",
            "OpportunityScore": watch_score,
        }

    return {
        "OpportunityType": "No Clear Edge",
        "Action": "Pass",
        "OpportunityScore": max(long_call_score, long_put_score, watch_score),
    }