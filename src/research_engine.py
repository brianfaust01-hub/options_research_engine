"""
Project Stonks
Research Engine

Sprint 28A:
Consensus research engine with expected holding-period estimation.

The research engine answers:

1. What is the directional thesis?
2. How strong is the thesis?
3. How long should the thesis reasonably take to play out?

The holding-period estimate is used later by the option selector to prefer
contracts with enough DTE for the thesis to develop.
"""

from strategies.momentum import evaluate_momentum
from strategies.trend import evaluate_trend
from strategies.market_regime import evaluate_market_regime


def _estimate_holding_period(modules):
    """
    Estimate how long the trade thesis should reasonably take to play out.

    Returns:
        Expected holding period in calendar days.

    Interpretation:
        30 days = short momentum / faster swing
        45 days = balanced trend + momentum setup
        60 days = slower trend-continuation setup
    """

    trend_score = max(
        (module.trend for module in modules),
        default=0,
    )

    momentum_score = max(
        (module.momentum for module in modules),
        default=0,
    )

    # Strong trend, weaker momentum:
    # let the trade breathe.
    if trend_score >= 90 and momentum_score < 70:
        return 60

    # Strong trend and strong momentum:
    # normal swing-trade horizon.
    if trend_score >= 75 and momentum_score >= 70:
        return 45

    # Mostly momentum:
    # shorter-duration thesis.
    if momentum_score >= 80:
        return 30

    # Default balanced horizon.
    return 45


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

    bullish_score = sum(
        module.confidence for module in bullish_modules
    )

    bearish_score = sum(
        module.confidence for module in bearish_modules
    )

    if bullish_score > bearish_score:
        direction = "Bullish"
        confidence = round(
            bullish_score / max(1, len(bullish_modules))
        )

    elif bearish_score > bullish_score:
        direction = "Bearish"
        confidence = round(
            bearish_score / max(1, len(bearish_modules))
        )

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

    holding_period_days = _estimate_holding_period(modules)

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
        "HoldingPeriodDays": holding_period_days,
        "StrategyReasons": "; ".join(reasons),
    }