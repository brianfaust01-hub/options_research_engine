"""
Project Stonks
Trade Construction Engine
"""

from datetime import datetime

from models.trade_recommendation import TradeRecommendation
from option_selector import select_best_contract


def _extract_expiration_from_contract_symbol(contract_symbol: str):
    """
    yfinance contract symbols usually look like:
    TSLA260731C00435000
    AMD260731C00600000

    The expiration is always the 6 digits immediately before C or P.
    """

    if not contract_symbol:
        return None

    for option_marker in ["C", "P"]:
        marker_index = contract_symbol.find(option_marker)

        if marker_index >= 6:
            raw_date = contract_symbol[marker_index - 6:marker_index]

            try:
                parsed = datetime.strptime(raw_date, "%y%m%d").date()
                return parsed.isoformat()
            except ValueError:
                return None

    return None


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

            if "Expiration" in best_contract:
                expiration = best_contract["Expiration"]

            if expiration is None and "contractSymbol" in best_contract:
                expiration = _extract_expiration_from_contract_symbol(
                    best_contract["contractSymbol"]
                )

            if expiration is None and "DTE" in best_contract:
                expiration = f"{int(best_contract['DTE'])} DTE"

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