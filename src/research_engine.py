"""
Project Stonks
Research Engine

Sprint 15 fix:
Build consensus from directional module signals instead of averaging
unrelated trend/momentum fields across all modules.
"""

from strategies.momentum import evaluate_momentum
from strategies.trend import evaluate_trend
from strategies.market_regime import evaluate_market_regime


def evaluate_strategies(row):

    modules = [
        evaluate_momentum(row),
        evaluate_trend(row),
        evaluate_market_regime(row),
    ]

    bullish_modules = [
        module for module in modules
        if module.signal == "Bullish"
    ]

    bearish_modules = [
        module for module in modules
        if module.signal == "Bearish"
    ]

    bullish_score = sum(module.confidence for module in bullish_modules)
    bearish_score = sum(module.confidence for module in bearish_modules)

    if bullish_score > bearish_score:
        direction = "Bullish"
        confidence = round(bullish_score / max(1, len(bullish_modules)))
    elif bearish_score > bullish_score:
        direction = "Bearish"
        confidence = round(bearish_score / max(1, len(bearish_modules)))
    else:
        direction = "Neutral"
        confidence = round(
            sum(module.confidence for module in modules)
            / len(modules)
        )

    trend_modules = [
        module.trend for module in modules
        if module.trend > 0
    ]

    momentum_modules = [
        module.momentum for module in modules
        if module.momentum > 0
    ]

    liquidity_modules = [
        module.liquidity for module in modules
        if module.liquidity > 0
    ]

    risk_modules = [
        module.risk for module in modules
        if module.risk > 0
    ]

    reasons = []

    for module in modules:
        reasons.extend(module.reasons)

    return {
        "Strategy": "Consensus",
        "Direction": direction,
        "StrategyScore": confidence,
        "TrendScore": round(
            sum(trend_modules) / max(1, len(trend_modules))
        ),
        "MomentumScore": round(
            sum(momentum_modules) / max(1, len(momentum_modules))
        ),
        "RiskScore": round(
            sum(risk_modules) / max(1, len(risk_modules))
        ),
        "LiquidityScore": round(
            sum(liquidity_modules) / max(1, len(liquidity_modules))
        ),
        "StrategyReasons": "; ".join(reasons),
    }