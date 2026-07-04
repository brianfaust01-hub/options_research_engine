"""
Project Stonks
Trade Construction Engine
"""

from datetime import datetime

from exit_rules import build_exit_plan
from models.trade_recommendation import TradeRecommendation
from option_selector import select_best_contract
from position_sizing import calculate_position_size
from trade_quality import evaluate_trade_quality


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

    position_size_pct = None
    position_value = None
    max_risk_dollars = None
    contracts = None

    profit_target_pct = None
    stop_loss_pct = None
    time_stop_dte = None

    trade_quality_score = None
    trade_quality_grade = None

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

            sizing = calculate_position_size(
                confidence=row["OpportunityScore"],
                premium=premium,
                option_strategy=option_strategy,
            )

            position_size_pct = sizing["position_size_pct"]
            position_value = sizing["position_value"]
            max_risk_dollars = sizing["max_risk_dollars"]
            contracts = sizing["contracts"]

            dte = None
            theta = None

            if "DTE" in best_contract:
                dte = int(best_contract["DTE"])

            if "theta" in best_contract:
                theta = float(best_contract["theta"])

            exit_plan = build_exit_plan(
                confidence=row["OpportunityScore"],
                premium=premium,
                dte=dte,
                theta=theta,
            )

            profit_target_pct = exit_plan["profit_target_pct"]
            stop_loss_pct = exit_plan["stop_loss_pct"]
            time_stop_dte = exit_plan["time_stop_dte"]

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

            notes.append(f"Recommended contracts: {contracts}")
            notes.append(f"Position value: ${position_value:.2f}")
            notes.append(f"Max risk: ${max_risk_dollars:.2f}")

            for exit_note in exit_plan["exit_notes"]:
                notes.append(exit_note)

            if contracts == 0:
                notes.append(
                    "Position size reduced to 0 because contract cost exceeds risk limits"
                )

        else:
            notes.append("No suitable option contract found")

    trade = TradeRecommendation(
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
        position_size_pct=position_size_pct,
        position_value=position_value,
        max_risk_dollars=max_risk_dollars,
        contracts=contracts,
        profit_target_pct=profit_target_pct,
        stop_loss_pct=stop_loss_pct,
        time_stop_dte=time_stop_dte,
        trade_quality_score=trade_quality_score,
        trade_quality_grade=trade_quality_grade,
        notes=notes,
    )

    if option_strategy is not None and contracts is not None and contracts > 0:
        quality = evaluate_trade_quality(trade)

        trade.trade_quality_score = quality["score"]
        trade.trade_quality_grade = quality["grade"]

        trade.notes.append(f"Trade Quality Score: {quality['score']}")
        trade.notes.append(f"Trade Quality Grade: {quality['grade']}")

        for reason in quality["reasons"]:
            trade.notes.append(f"Trade Quality Reason: {reason}")

    return trade