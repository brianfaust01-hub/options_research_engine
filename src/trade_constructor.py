"""
Project Stonks
Trade Construction Engine

Sprint 32B:
Adds execution-quality analytics to holding-period-aware option selection.

Execution metrics are observational only while the Execution Engine remains
in test mode. They do not alter contract selection, position sizing, trade
quality, or portfolio allocation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from exit_rules import build_exit_plan
from models.trade_recommendation import TradeRecommendation
from option_selector import select_best_contract
from position_sizing import calculate_position_size
from trade_quality import evaluate_trade_quality


def _extract_expiration_from_contract_symbol(
    contract_symbol: str,
) -> str | None:
    if not contract_symbol:
        return None

    for option_marker in ["C", "P"]:
        marker_index = contract_symbol.find(
            option_marker
        )

        if marker_index >= 6:
            raw_date = contract_symbol[
                marker_index - 6:marker_index
            ]

            try:
                parsed = datetime.strptime(
                    raw_date,
                    "%y%m%d",
                ).date()

                return parsed.isoformat()

            except ValueError:
                return None

    return None


def _safe_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(
    value: Any,
) -> int | None:
    numeric_value = _safe_float(value)

    if numeric_value is None:
        return None

    return int(numeric_value)


def _safe_bool(
    value: Any,
    default: bool = False,
) -> bool:
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {
            "true",
            "1",
            "yes",
            "y",
        }:
            return True

        if normalized in {
            "false",
            "0",
            "no",
            "n",
        }:
            return False

    return bool(value)


def _safe_text(
    value: Any,
) -> str | None:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    text = str(value).strip()

    return text if text else None


def _safe_note(
    label: str,
    contract,
    field: str,
    decimals: int = 2,
) -> str | None:
    if field not in contract:
        return None

    value = contract[field]

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    try:
        return (
            f"{label}: "
            f"{float(value):.{decimals}f}"
        )
    except (TypeError, ValueError):
        return f"{label}: {value}"


def _percent_note(
    label: str,
    value: float | None,
) -> str | None:
    if value is None:
        return None

    return f"{label}: {value:.2%}"


def _dollar_note(
    label: str,
    value: float | None,
) -> str | None:
    if value is None:
        return None

    return f"{label}: ${value:.2f}"


def construct_trade(
    row,
) -> TradeRecommendation:
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

    # ------------------------------------------------------------------
    # Sprint 32B execution fields
    # ------------------------------------------------------------------

    execution_score = None
    execution_grade = None
    execution_friction = None

    spread_pct = None
    spread_dollars = None

    research_price = None
    research_price_method = None

    execution_entry_price = None
    execution_entry_method = None

    execution_exit_price = None
    execution_exit_method = None

    entry_execution_cost_pct = None
    immediate_liquidation_return_pct = None

    last_trade_price = None
    option_volume = None
    option_open_interest = None

    execution_engine_test_mode = False

    holding_period_days = row.get(
        "HoldingPeriodDays",
        None,
    )

    notes = [
        f"Research Score: {row['StrategyScore']}",
        f"Trend: {row['TrendScore']}",
        f"Momentum: {row['MomentumScore']}",
        (
            "Expected Holding Period: "
            f"{holding_period_days} days"
        ),
        row["StrategyReasons"],
    ]

    if row["Action"] == "Evaluate Options":
        best_contract = select_best_contract(
            ticker=row["Ticker"],
            opportunity_type=row["OpportunityType"],
            expected_holding_days=holding_period_days,
        )

        if best_contract is not None:
            option_strategy = (
                "Long Call"
                if "Call" in row["OpportunityType"]
                else "Long Put"
            )

            expiration = _safe_text(
                best_contract.get("Expiration")
            )

            if (
                expiration is None
                and best_contract.get(
                    "contractSymbol"
                )
            ):
                expiration = (
                    _extract_expiration_from_contract_symbol(
                        str(
                            best_contract[
                                "contractSymbol"
                            ]
                        )
                    )
                )

            if (
                expiration is None
                and best_contract.get("DTE")
                is not None
            ):
                contract_dte = _safe_int(
                    best_contract.get("DTE")
                )

                if contract_dte is not None:
                    expiration = (
                        f"{contract_dte} DTE"
                    )

            strike = _safe_float(
                best_contract.get("strike")
            )

            # Existing research and sizing logic continues to use
            # midpoint premium during execution-engine test mode.
            premium = _safe_float(
                best_contract.get("mid")
            )

            # ----------------------------------------------------------
            # Sprint 32B execution metadata
            # ----------------------------------------------------------

            execution_score = _safe_float(
                best_contract.get(
                    "ExecutionScore"
                )
            )

            execution_grade = _safe_text(
                best_contract.get(
                    "ExecutionGrade"
                )
            )

            execution_friction = _safe_text(
                best_contract.get(
                    "ExecutionFriction"
                )
            )

            spread_pct = _safe_float(
                best_contract.get(
                    "spread_pct"
                )
            )

            spread_dollars = _safe_float(
                best_contract.get(
                    "SpreadDollars"
                )
            )

            research_price = _safe_float(
                best_contract.get(
                    "ResearchPrice"
                )
            )

            research_price_method = _safe_text(
                best_contract.get(
                    "ResearchPriceMethod"
                )
            )

            execution_entry_price = _safe_float(
                best_contract.get(
                    "ExecutionEntryPrice"
                )
            )

            execution_entry_method = _safe_text(
                best_contract.get(
                    "ExecutionEntryMethod"
                )
            )

            execution_exit_price = _safe_float(
                best_contract.get(
                    "ExecutionExitPrice"
                )
            )

            execution_exit_method = _safe_text(
                best_contract.get(
                    "ExecutionExitMethod"
                )
            )

            entry_execution_cost_pct = _safe_float(
                best_contract.get(
                    "EntryExecutionCostPct"
                )
            )

            immediate_liquidation_return_pct = (
                _safe_float(
                    best_contract.get(
                        "ImmediateLiquidationReturnPct"
                    )
                )
            )

            last_trade_price = _safe_float(
                best_contract.get(
                    "LastTradePrice"
                )
            )

            option_volume = _safe_int(
                best_contract.get(
                    "OptionVolume"
                )
            )

            option_open_interest = _safe_int(
                best_contract.get(
                    "OptionOpenInterest"
                )
            )

            execution_engine_test_mode = _safe_bool(
                best_contract.get(
                    "ExecutionEngineTestMode"
                ),
                default=False,
            )

            if (
                strike is not None
                and premium is not None
                and premium > 0
            ):
                sizing = calculate_position_size(
                    confidence=row[
                        "OpportunityScore"
                    ],
                    premium=premium,
                    option_strategy=(
                        option_strategy
                    ),
                )

                position_size_pct = sizing[
                    "position_size_pct"
                ]

                position_value = sizing[
                    "position_value"
                ]

                max_risk_dollars = sizing[
                    "max_risk_dollars"
                ]

                contracts = sizing[
                    "contracts"
                ]

                dte = _safe_int(
                    best_contract.get("DTE")
                )

                theta = _safe_float(
                    best_contract.get("theta")
                )

                exit_plan = build_exit_plan(
                    confidence=row[
                        "OpportunityScore"
                    ],
                    premium=premium,
                    dte=dte,
                    theta=theta,
                )

                profit_target_pct = exit_plan[
                    "profit_target_pct"
                ]

                stop_loss_pct = exit_plan[
                    "stop_loss_pct"
                ]

                time_stop_dte = exit_plan[
                    "time_stop_dte"
                ]

                notes.append(
                    f"Recommended premium: "
                    f"${premium:.2f}"
                )

                contract_notes = [
                    _safe_note(
                        "Contract Score",
                        best_contract,
                        "ContractScore",
                        0,
                    ),
                    _safe_note(
                        "Horizon Fit Score",
                        best_contract,
                        "HorizonFitScore",
                        0,
                    ),
                    _safe_note(
                        "Final Contract Score",
                        best_contract,
                        "FinalContractScore",
                        0,
                    ),
                    _safe_note(
                        "Preferred Min DTE",
                        best_contract,
                        "PreferredMinDTE",
                        0,
                    ),
                    _safe_note(
                        "Preferred Max DTE",
                        best_contract,
                        "PreferredMaxDTE",
                        0,
                    ),
                    _safe_note(
                        "Delta",
                        best_contract,
                        "delta",
                        2,
                    ),
                    _safe_note(
                        "Theta",
                        best_contract,
                        "theta",
                        2,
                    ),
                    _safe_note(
                        "Open Interest",
                        best_contract,
                        "openInterest",
                        0,
                    ),
                    _safe_note(
                        "Volume",
                        best_contract,
                        "volume",
                        0,
                    ),
                    _safe_note(
                        "DTE",
                        best_contract,
                        "DTE",
                        0,
                    ),
                ]

                for note in contract_notes:
                    if note is not None:
                        notes.append(note)

                # ------------------------------------------------------
                # Execution-engine notes
                # ------------------------------------------------------

                execution_notes = [
                    (
                        f"Execution Score: "
                        f"{execution_score:.0f}"
                        if execution_score
                        is not None
                        else None
                    ),
                    (
                        f"Execution Grade: "
                        f"{execution_grade}"
                        if execution_grade
                        is not None
                        else None
                    ),
                    (
                        f"Execution Friction: "
                        f"{execution_friction}"
                        if execution_friction
                        is not None
                        else None
                    ),
                    _percent_note(
                        "Bid/Ask Spread",
                        spread_pct,
                    ),
                    _dollar_note(
                        "Bid/Ask Spread Dollars",
                        spread_dollars,
                    ),
                    (
                        "Research Price Method: "
                        f"{research_price_method}"
                        if research_price_method
                        is not None
                        else None
                    ),
                    _dollar_note(
                        "Research Price",
                        research_price,
                    ),
                    (
                        "Execution Entry Method: "
                        f"{execution_entry_method}"
                        if execution_entry_method
                        is not None
                        else None
                    ),
                    _dollar_note(
                        "Execution Entry Price",
                        execution_entry_price,
                    ),
                    (
                        "Execution Exit Method: "
                        f"{execution_exit_method}"
                        if execution_exit_method
                        is not None
                        else None
                    ),
                    _dollar_note(
                        "Execution Exit Price",
                        execution_exit_price,
                    ),
                    _percent_note(
                        "Entry Execution Cost",
                        entry_execution_cost_pct,
                    ),
                    _percent_note(
                        "Immediate Liquidation Return",
                        immediate_liquidation_return_pct,
                    ),
                    _dollar_note(
                        "Last Trade Price",
                        last_trade_price,
                    ),
                    (
                        f"Option Volume: "
                        f"{option_volume}"
                        if option_volume
                        is not None
                        else None
                    ),
                    (
                        f"Option Open Interest: "
                        f"{option_open_interest}"
                        if option_open_interest
                        is not None
                        else None
                    ),
                    (
                        "Execution Engine Mode: TEST"
                        if execution_engine_test_mode
                        else None
                    ),
                ]

                for note in execution_notes:
                    if note is not None:
                        notes.append(note)

                notes.append(
                    "Recommended contracts: "
                    f"{contracts}"
                )

                notes.append(
                    f"Position value: "
                    f"${position_value:.2f}"
                )

                notes.append(
                    f"Max risk: "
                    f"${max_risk_dollars:.2f}"
                )

                for exit_note in exit_plan[
                    "exit_notes"
                ]:
                    notes.append(exit_note)

                if contracts == 0:
                    notes.append(
                        "Position size reduced to 0 "
                        "because contract cost exceeds "
                        "risk limits"
                    )

            else:
                notes.append(
                    "Selected contract did not contain "
                    "a valid strike and midpoint premium"
                )

        else:
            notes.append(
                "No suitable option contract found"
            )

    trade = TradeRecommendation(
        ticker=row["Ticker"],
        opportunity_type=row[
            "OpportunityType"
        ],
        action=row["Action"],
        confidence=row[
            "OpportunityScore"
        ],
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
        trade_quality_score=(
            trade_quality_score
        ),
        trade_quality_grade=(
            trade_quality_grade
        ),
        execution_score=execution_score,
        execution_grade=execution_grade,
        execution_friction=(
            execution_friction
        ),
        spread_pct=spread_pct,
        spread_dollars=spread_dollars,
        research_price=research_price,
        research_price_method=(
            research_price_method
        ),
        execution_entry_price=(
            execution_entry_price
        ),
        execution_entry_method=(
            execution_entry_method
        ),
        execution_exit_price=(
            execution_exit_price
        ),
        execution_exit_method=(
            execution_exit_method
        ),
        entry_execution_cost_pct=(
            entry_execution_cost_pct
        ),
        immediate_liquidation_return_pct=(
            immediate_liquidation_return_pct
        ),
        last_trade_price=last_trade_price,
        option_volume=option_volume,
        option_open_interest=(
            option_open_interest
        ),
        execution_engine_test_mode=(
            execution_engine_test_mode
        ),
        notes=notes,
    )

    if (
        option_strategy is not None
        and contracts is not None
        and contracts > 0
    ):
        quality = evaluate_trade_quality(
            trade
        )

        trade.trade_quality_score = quality[
            "score"
        ]

        trade.trade_quality_grade = quality[
            "grade"
        ]

        trade.notes.append(
            "Trade Quality Score: "
            f"{quality['score']}"
        )

        trade.notes.append(
            "Trade Quality Grade: "
            f"{quality['grade']}"
        )

        for reason in quality["reasons"]:
            trade.notes.append(
                "Trade Quality Reason: "
                f"{reason}"
            )

    return trade