"""
Project Stonks
Research Engine
"""

from dataclasses import asdict

from strategies.momentum import evaluate_momentum
from strategies.trend import evaluate_trend
from strategies.market_regime import evaluate_market_regime


def evaluate_strategies(row):

    modules = [
        evaluate_momentum(row),
        evaluate_trend(row),
        evaluate_market_regime(row),
    ]

    confidence = round(
        sum(module.confidence for module in modules)
        / len(modules)
    )

    bullish_votes = sum(
        module.signal == "Bullish"
        for module in modules
    )

    bearish_votes = len(modules) - bullish_votes

    direction = (
        "Bullish"
        if bullish_votes >= bearish_votes
        else "Bearish"
    )

    reasons = []

    for module in modules:
        reasons.extend(module.reasons)

    return {
        "Strategy": "Consensus",
        "Direction": direction,
        "StrategyScore": confidence,
        "TrendScore": round(
            sum(module.trend for module in modules)
            / len(modules)
        ),
        "MomentumScore": round(
            sum(module.momentum for module in modules)
            / len(modules)
        ),
        "RiskScore": round(
            sum(module.risk for module in modules)
            / len(modules)
        ),
        "LiquidityScore": round(
            sum(module.liquidity for module in modules)
            / len(modules)
        ),
        "StrategyReasons": "; ".join(reasons),
    }