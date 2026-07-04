"""
Project Stonks
Market Regime Module

Ticker-level regime contribution.
Broad SPY-level regime is handled by market_context.py.
"""

from models.research_result import ResearchResult


def evaluate_market_regime(row) -> ResearchResult:

    score = 0
    reasons = []

    if row["Above_SMA_200"]:
        score += 45
        reasons.append("Long-term trend positive")
    else:
        reasons.append("Long-term trend negative")

    if row["Above_SMA_50"]:
        score += 25
        reasons.append("Intermediate trend positive")
    else:
        reasons.append("Intermediate trend negative")

    if row["MACD_Bullish"]:
        score += 30
        reasons.append("Momentum positive")
    else:
        reasons.append("Momentum negative")

    if score >= 70:
        signal = "Bullish"
    elif score <= 35:
        signal = "Bearish"
    else:
        signal = "Neutral"

    return ResearchResult(
        module="Market Regime",
        signal=signal,
        confidence=score,
        trend=0,
        momentum=0,
        risk=score,
        liquidity=0,
        reasons=reasons,
    )