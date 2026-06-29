"""
Project Stonks
Trade Construction Engine
"""

from models.trade_recommendation import TradeRecommendation
from option_selector import select_best_contract


def construct_trade(row) -> TradeRecommendation:

    option_strategy = None
    expiration = None
    strike = None
    premium = None

    notes = [
        f"Research Score: {row['StrategyScore']}",
        f"Trend: {row['TrendScore']}",
        f"Momentum: {row['MomentumScore']}",
        row["StrategyReasons"],
    ]

    if row["Action"] == "Evaluate Options":

        best_contract = select_best_contract(
            ticker=row["Ticker"],
            opportunity_type=row["OpportunityType"],
        )

        if best_contract is not None:

            option_strategy = (
                "Long Call"
                if "Call" in row["OpportunityType"]
                else "Long Put"
            )

            expiration = best_contract["contractSymbol"][4:10]
            strike = float(best_contract["strike"])
            premium = float(best_contract["mid"])

            notes.append(f"Recommended premium: ${premium:.2f}")

        else:
            notes.append("No suitable option contract found")

    return TradeRecommendation(
        ticker=row["Ticker"],
        opportunity_type=row["OpportunityType"],
        action=row["Action"],
        confidence=row["OpportunityScore"],
        expected_apr=None,
        option_strategy=option_strategy,
        option_type=option_strategy,
        expiration=expiration,
        strike=strike,
        position_size_pct=None,
        notes=notes,
    )