"""
Project Stonks
Trade Journal

Sprint 33A

Immutable completed-observation journal.

Purpose

Preserve the complete decision state produced by Project Stonks for every
security analyzed in a scan.

Each journal observation is written only after the research, opportunity,
option-selection, portfolio-allocation, market-context, and market-breadth
stages have completed.

The journal is append-only from the perspective of research history.
Existing historical rows are never intentionally modified.

Journal writes are atomic so an interrupted process cannot leave the
primary CSV partially written.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from data_quality import assess_observation

from config import (
    VERSION,
    CONFIG_VERSION,
    ENABLE_JOURNAL_WRITES,
)

from snapshot_writer import (
    write_observation_snapshot,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

JOURNAL_PATH = (
    PROJECT_ROOT
    / "data"
    / "trade_journal.csv"
)


def _classify_trade_status(
    observation: dict,
) -> str:
    """
    Classify the completed recommendation state.
    """

    action = observation.get(
        "action"
    )

    if action == "Watch":
        return "WATCHLIST"

    if action != "Evaluate Options":
        return "PASS"

    option_strategy = observation.get(
        "option_strategy"
    )

    contracts = observation.get(
        "contracts"
    )

    if (
        option_strategy is None
        or pd.isna(option_strategy)
    ):
        return "NOT_EXECUTABLE"

    if (
        contracts is None
        or pd.isna(contracts)
        or float(contracts) <= 0
    ):
        return "NOT_EXECUTABLE"

    return "PAPER_TRADE_CANDIDATE"


def _normalize_value(
    value: Any,
):
    """
    Convert pandas / numpy missing values into None.

    Nested lists and dictionaries are normalized recursively.
    """

    if isinstance(
        value,
        dict,
    ):
        return {
            key: _normalize_value(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            _normalize_value(item)
            for item in value
        ]

    try:
        if pd.isna(value):
            return None
    except (
        TypeError,
        ValueError,
    ):
        pass

    if hasattr(
        value,
        "item",
    ):
        try:
            return value.item()
        except Exception:
            pass

    return value


def _load_existing_journal() -> pd.DataFrame:
    """
    Load the existing immutable journal.
    """

    if not JOURNAL_PATH.exists():
        return pd.DataFrame()

    if JOURNAL_PATH.stat().st_size == 0:
        return pd.DataFrame()

    try:

        return pd.read_csv(
            JOURNAL_PATH,
            low_memory=False,
        )

    except pd.errors.ParserError as error:

        raise RuntimeError(
            "Trade journal is not readable. "
            "Run repair_trade_journal.py before "
            "generating additional observations."
        ) from error


def _write_journal_atomically(
    journal: pd.DataFrame,
) -> None:
    """
    Persist the completed journal atomically.
    """

    JOURNAL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        JOURNAL_PATH.with_suffix(
            ".writing.csv"
        )
    )

    try:

        journal.to_csv(
            temporary_path,
            index=False,
        )

        #
        # Validate the completed temporary file before
        # replacing the primary journal.
        #

        pd.read_csv(
            temporary_path,
            low_memory=False,
        )

        os.replace(
            temporary_path,
            JOURNAL_PATH,
        )

    finally:

        if temporary_path.exists():
            temporary_path.unlink()


def _append_rows_to_journal(
    rows: list[dict],
) -> None:
    """
    Append completed observations using one atomic
    journal transaction.
    """

    if not rows:
        return

    new_rows = pd.DataFrame(
        rows
    )

    existing = (
        _load_existing_journal()
    )

    if existing.empty:

        updated_journal = (
            new_rows
        )

    else:

        updated_journal = pd.concat(
            [
                existing,
                new_rows,
            ],
            ignore_index=True,
            sort=False,
        )

    _write_journal_atomically(
        updated_journal
    )


def _build_completed_observation(
    trade_row: dict,
    research_row: dict,
    market_context: dict,
    market_breadth: dict,
    recommendation_date: str,
) -> dict:
    """
    Construct one complete historical observation.

    Research fields are loaded first and final trade /
    allocation fields are then layered over them.

    This preserves the original research state while
    allowing final downstream values to take precedence
    when a field exists in both datasets.
    """

    observation = {}

    #
    # Complete underlying research state
    #

    observation.update(
        research_row
    )

    #
    # Completed trade / option / allocation state
    #

    observation.update(
        trade_row
    )

    #
    # Canonical metadata
    #

    observation[
        "RecommendationDate"
    ] = recommendation_date

    observation[
        "ProjectVersion"
    ] = VERSION

    observation[
        "ConfigVersion"
    ] = CONFIG_VERSION

    #
    # Market context at decision time
    #

    observation[
        "market_regime"
    ] = market_context.get(
        "market_regime"
    )

    observation[
        "risk_mode"
    ] = market_context.get(
        "risk_mode"
    )

    observation[
        "allocation_bias"
    ] = market_context.get(
        "allocation_bias"
    )

    observation[
        "market_score"
    ] = market_context.get(
        "market_score"
    )

    observation[
        "market_reasons"
    ] = market_context.get(
        "market_reasons"
    )

    #
    # Market breadth at decision time
    #

    observation[
        "breadth_score"
    ] = market_breadth.get(
        "breadth_score"
    )

    observation[
        "breadth_regime"
    ] = market_breadth.get(
        "breadth_regime"
    )

    breadth_reasons = (
        market_breadth.get(
            "breadth_reasons",
            [],
        )
    )

    if isinstance(
        breadth_reasons,
        list,
    ):
        observation[
            "breadth_reasons"
        ] = "; ".join(
            str(reason)
            for reason
            in breadth_reasons
        )

    else:
        observation[
            "breadth_reasons"
        ] = breadth_reasons

    #
    # Canonical underlying research price.
    #
    # This deliberately uses the same Close value that
    # fed the research model instead of performing a new
    # live quote request after the fact.
    #

    entry_underlying_price = (
        observation.get(
            "Close"
        )
    )

    if entry_underlying_price is None:
        entry_underlying_price = (
            observation.get(
                "close"
            )
        )

    observation[
        "EntryUnderlyingPrice"
    ] = entry_underlying_price

    #
    # Completed recommendation status
    #

    observation[
        "TradeStatus"
    ] = _classify_trade_status(
        observation
    )

    normalized_observation = {
        key: _normalize_value(
            value
        )
        for key, value
        in observation.items()
    }

    return assess_observation(
        normalized_observation
    )


def _order_observation(
    observation: dict,
) -> dict:
    """
    Apply stable high-value column ordering while
    preserving every additional research field.
    """

    priority_columns = [
        "RecommendationID",
        "RecommendationDate",
        "ticker",
        "action",
        "opportunity_type",
        "confidence",
        "TradeStatus",
        "EntryUnderlyingPrice",

        #
        # Research scores
        #

        "ResearchScore",
        "TrendScore",
        "MomentumScore",
        "MomentumDirection",
        "LiquidityScore",
        "StrategyScore",
        "OpportunityScore",
        "BullishScore",
        "BearishScore",
        "DirectionalConviction",

        #
        # Data quality and provenance
        #

        "ObservationSchemaGeneration",
        "DataQualityStatus",
        "DataQualityIssues",
        "RecommendationTruthSource",
        "ExecutionTruthSource",
        "BrokerReconciliationStatus",

        #
        # Core indicators
        #

        "Close",
        "SMA_20",
        "SMA_50",
        "SMA_200",
        "RSI_14",
        "MACD",
        "MACD_Signal",
        "ATR_14",
        "Avg_Volume_20",

        #
        # Option selection
        #

        "option_strategy",
        "expiration",
        "strike",
        "premium",
        "contracts",
        "trade_quality_score",
        "trade_quality_grade",
        "execution_score",
        "execution_grade",
        "execution_friction",
        "execution_entry_price",
        "execution_exit_price",
        "broker_delta",
        "broker_gamma",
        "broker_theta",
        "broker_vega",
        "broker_rho",
        "implied_volatility",
        "iv_rank",
        "iv_percentile",
        "estimated_delta",
        "estimated_theta",
        "theta_drag_pct_per_day",
        "gamma_per_premium",
        "vega_per_premium",
        "greeks_source",
        "iv_context_status",

        #
        # Institutional / portfolio decision
        #

        "institutional_trade_score",
        "institutional_trade_grade",
        "portfolio_score",
        "allocation_score",
        "allocation_rank",
        "allocation_decision",
        "portfolio_action",
        "portfolio_action_reason",
        "portfolio_forward_score",
        "portfolio_target_value",
        "portfolio_expected_loss_at_stop",
        "portfolio_capital_utilization_pct",
        "portfolio_utilization_policy",
        "portfolio_utilization_target_pct",
        "portfolio_utilization_target_dollars",
        "portfolio_utilization_quality_score",
        "portfolio_utilization_execution_score",
        "portfolio_utilization_opportunity_count",
        "portfolio_utilization_market_multiplier",
        "portfolio_utilization_reason",
        "portfolio_legacy_fixed_ceiling_pct",
        "portfolio_legacy_fixed_ceiling_dollars",
        "portfolio_full_premium_stress_loss",
        "portfolio_full_premium_stress_loss_pct",
        "portfolio_intentional_cash_pct",
        "portfolio_expected_loss_at_stops_pct",
        "portfolio_turnover_pct",
        "PortfolioStatus",
        "time_edge_score",
        "time_edge_grade",
        "expected_move_window_days",
        "time_edge_data_quality",
        "time_edge_reason",
        "shadow_time_adjusted_score",
        "earnings_date",
        "days_to_earnings",
        "trading_days_to_earnings",
        "earnings_status",
        "earnings_within_thesis_window",
        "earnings_allocation_override",
        "shadow_conservative_contracts",
        "shadow_balanced_contracts",
        "shadow_aggressive_contracts",
        "shadow_planned_loss_pct",
        "shadow_stressed_loss_pct",
        "portfolio_market_multiplier",
        "portfolio_directional_multiplier",

        #
        # Market state
        #

        "market_regime",
        "risk_mode",
        "allocation_bias",
        "market_score",
        "market_reasons",
        "breadth_score",
        "breadth_regime",
        "breadth_reasons",

        #
        # Versioning / immutable artifacts
        #

        "ProjectVersion",
        "ConfigVersion",
        "SnapshotPath",
        "SnapshotSchemaVersion",
    ]

    remaining = [
        column
        for column
        in observation.keys()
        if column
        not in priority_columns
    ]

    ordered_columns = (
        priority_columns
        + remaining
    )

    return {
        column: observation.get(
            column
        )
        for column
        in ordered_columns
    }


def log_completed_observations(
    trades_df: pd.DataFrame,
    research_df: pd.DataFrame,
    market_context: dict,
    market_breadth: dict,
) -> int:
    """
    Persist one completed immutable observation for
    every analyzed security.

    Parameters
    ----------
    trades_df
        Final recommendation dataframe after option
        selection and portfolio allocation.

    research_df
        Full indicator / research dataframe used to
        generate those recommendations.

    market_context
        Market regime state for the scan.

    market_breadth
        Market breadth state for the scan.

    Returns
    -------
    int
        Number of observations written.
    """

    if not ENABLE_JOURNAL_WRITES:
        return 0

    if trades_df.empty:
        return 0

    if research_df.empty:
        raise ValueError(
            "Cannot journal completed observations "
            "because research_df is empty."
        )

    if "ticker" not in trades_df.columns:
        raise ValueError(
            "trades_df does not contain ticker."
        )

    research_ticker_column = None

    for candidate in (
        "Ticker",
        "ticker",
    ):
        if candidate in research_df.columns:
            research_ticker_column = (
                candidate
            )
            break

    if research_ticker_column is None:
        raise ValueError(
            "research_df does not contain "
            "Ticker or ticker."
        )

    #
    # One consistent observation timestamp for the
    # completed scan.
    #

    recommendation_date = (
        datetime.now()
        .isoformat(
            timespec="seconds"
        )
    )

    #
    # Index the research state once instead of scanning
    # the dataframe for every recommendation.
    #

    research_lookup = {}

    for _, row in (
        research_df.iterrows()
    ):

        ticker = str(
            row[
                research_ticker_column
            ]
        ).upper().strip()

        research_lookup[
            ticker
        ] = row.to_dict()

    completed_rows = []

    for _, trade_row_series in (
        trades_df.iterrows()
    ):

        trade_row = (
            trade_row_series.to_dict()
        )

        ticker = str(
            trade_row.get(
                "ticker",
                ""
            )
        ).upper().strip()

        if not ticker:
            raise ValueError(
                "Encountered final trade row "
                "without a ticker."
            )

        research_row = (
            research_lookup.get(
                ticker
            )
        )

        if research_row is None:
            raise ValueError(
                "No matching research observation "
                f"found for {ticker}."
            )

        observation = (
            _build_completed_observation(
                trade_row=trade_row,
                research_row=research_row,
                market_context=market_context,
                market_breadth=market_breadth,
                recommendation_date=(
                    recommendation_date
                ),
            )
        )

        #
        # Snapshot the complete observation before
        # writing the journal row.
        #

        snapshot_info = (
            write_observation_snapshot(
                observation
            )
        )

        observation[
            "RecommendationID"
        ] = snapshot_info[
            "recommendation_id"
        ]

        observation[
            "SnapshotPath"
        ] = snapshot_info[
            "file_path"
        ]

        observation[
            "SnapshotSchemaVersion"
        ] = snapshot_info[
            "schema_version"
        ]

        completed_rows.append(
            _order_observation(
                observation
            )
        )

    #
    # One journal read + one atomic write for the
    # entire completed daily scan.
    #

    _append_rows_to_journal(
        completed_rows
    )

    return len(
        completed_rows
    )
