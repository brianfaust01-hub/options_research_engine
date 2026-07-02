"""
Project Stonks
Trade Construction Engine
"""

from datetime import datetime

from models.trade_recommendation import TradeRecommendation
from option_selector import select_best_contract


def _extract_expiration_from_contract_symbol(contract_symbol: str):
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


def _safe_note(label: str, contract, field: str, decimals: int = 2):
    if field not in contract:
        return None

    value = contract[field]

    try:
        return f"{label}: {float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return f"{label}: {value}"


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

            contract_notes = [
                _safe_note("Contract Score", best_contract, "ContractScore", 0),
                _safe_note("Delta", best_contract, "delta", 2),
                _safe_note("Theta", best_contract, "theta", 2),
                _safe_note("Spread %", best_contract, "spread_pct", 2),
                _safe_note("Open Interest", best_contract, "openInterest", 0),
                _safe_note("Volume", best_contract, "volume", 0),
                _safe_note("DTE", best_contract, "DTE", 0),
            ]

            for note in contract_notes:
                if note is not None:
                    notes.append(note)

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
        premium=premium,
        position_size_pct=None,
        notes=notes,
    )