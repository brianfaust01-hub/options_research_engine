"""
Project Stonks
Market Regime Module
"""

from models.research_result import ResearchResult


def evaluate_market_regime(row) -> ResearchResult:

    score = 0
    reasons = []

    if row["Above_SMA_200"]:
        score += 50
        reasons.append("Long-term trend positive")

    if row["MACD_Bullish"]:
        score += 50
        reasons.append("Momentum positive")

    signal = "Bullish" if score >= 50 else "Bearish"

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