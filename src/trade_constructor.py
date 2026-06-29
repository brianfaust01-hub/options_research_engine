"""
Project Stonks
Trade Construction Engine
"""

from models.trade_recommendation import TradeRecommendation


def construct_trade(row) -> TradeRecommendation:

    notes = [
        f"Research Score: {row['StrategyScore']}",
        f"Trend: {row['TrendScore']}",
        f"Momentum: {row['MomentumScore']}",
        row["StrategyReasons"],
    ]

    return TradeRecommendation(
        ticker=row["Ticker"],
        opportunity_type=row["OpportunityType"],
        action=row["Action"],
        confidence=row["OpportunityScore"],
        expected_apr=None,
        option_strategy=None,
        option_type=None,
        expiration=None,
        strike=None,
        position_size_pct=None,
        notes=notes,
    )