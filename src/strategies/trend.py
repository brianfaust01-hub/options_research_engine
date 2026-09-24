"""
Project Stonks
Trend Research Module
"""

from models.research_result import ResearchResult


def evaluate_trend(row) -> ResearchResult:

    trend = 0
    reasons = []

    if row["Above_SMA_20"]:
        trend += 25
        reasons.append("Above 20 SMA")

    if row["Above_SMA_50"]:
        trend += 35
        reasons.append("Above 50 SMA")

    if row["Above_SMA_200"]:
        trend += 40
        reasons.append("Above 200 SMA")

    signal = "Bullish" if trend >= 50 else "Bearish"

    # ``trend`` is a bullish-position score: a low value is strong evidence
    # for the bearish signal, not low confidence in that signal. Keep the
    # bullish-position score in ``trend`` for downstream directional scoring,
    # while reporting confidence symmetrically in the direction selected.
    directional_confidence = (
        trend
        if signal == "Bullish"
        else 100 - trend
    )

    return ResearchResult(
        module="Trend",
        signal=signal,
        confidence=directional_confidence,
        trend=trend,
        momentum=0,
        risk=0,
        liquidity=0,
        reasons=reasons,
    )
