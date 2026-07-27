"""
Project Stonks
Execution and Liquidity Retrospective

Sprint 32D

Purpose
-------
Audit a recent subset of historical recommendations to determine:

- Whether selected options have excessive bid/ask spreads
- Whether inexpensive contracts tend to have wider spreads
- Whether low open interest or volume is associated with wider spreads
- Whether DTE is associated with execution quality
- How many trades would fail proposed spread thresholds
- Whether current position-size constraints are forcing recommendations
  toward cheaper, less-liquid contracts

This module is READ ONLY.

It does not modify:
- trade_journal.csv
- recommendation snapshots
- paper_portfolio.csv
- contract selection
- allocation decisions

Usage
-----
Default: analyze the most recent 250 executable recommendations.

    python src\\execution_liquidity_retrospective.py

Analyze the most recent 500:

    python src\\execution_liquidity_retrospective.py --limit 500

Analyze recommendations from the last 7 calendar days:

    python src\\execution_liquidity_retrospective.py --days 7

Analyze all available executable recommendations:

    python src\\execution_liquidity_retrospective.py --all

Analyze only snapshot-era recommendations:

    python src\\execution_liquidity_retrospective.py --snapshot-only
"""

from __future__ import annotations

import argparse
import ast
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent

JOURNAL_PATH = (
    PROJECT_ROOT
    / "data"
    / "trade_journal.csv"
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

REPORTS_DIR = (
    PROJECT_ROOT
    / "reports"
)


DEFAULT_LIMIT = 250
CURRENT_PORTFOLIO_VALUE = 15_000
LARGER_PORTFOLIO_VALUE = 100_000

POSITION_SIZE_SCENARIOS = [
    0.03,
    0.05,
    0.08,
    0.12,
]

SPREAD_THRESHOLDS = [
    0.05,
    0.10,
    0.15,
    0.20,
]

OUTPUT_COLUMNS = [
    "RecommendationID",
    "RecommendationDate",
    "ticker",
    "option_strategy",
    "expiration",
    "dte",
    "strike",
    "premium",
    "research_price",
    "execution_entry_price",
    "execution_exit_price",
    "spread_dollars",
    "spread_pct",
    "entry_execution_cost_pct",
    "immediate_liquidation_return_pct",
    "execution_score",
    "execution_grade",
    "execution_friction",
    "option_open_interest",
    "option_volume",
    "delta",
    "theta",
    "contracts",
    "position_value",
    "position_size_pct",
    "trade_quality_score",
    "trade_quality_grade",
    "SnapshotPath",
]


# ---------------------------------------------------------------------
# Safe conversions
# ---------------------------------------------------------------------

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

    if isinstance(value, str):
        value = (
            value
            .replace("%", "")
            .replace("$", "")
            .replace(",", "")
            .strip()
        )

        if not value:
            return None

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

    try:
        return int(numeric_value)
    except (TypeError, ValueError):
        return None


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

    if not text:
        return None

    return text


def _first_present(
    row: pd.Series,
    names: list[str],
):
    for name in names:
        if name not in row.index:
            continue

        value = row.get(name)

        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass

        if value is not None:
            return value

    return None


# ---------------------------------------------------------------------
# Notes parsing
# ---------------------------------------------------------------------

def _parse_notes(
    value: Any,
) -> list[str]:
    if isinstance(value, list):
        return [
            str(item)
            for item in value
        ]

    text = _safe_text(value)

    if text is None:
        return []

    try:
        parsed = ast.literal_eval(text)

        if isinstance(parsed, list):
            return [
                str(item)
                for item in parsed
            ]

    except (
        ValueError,
        SyntaxError,
    ):
        pass

    return [text]


def _note_value(
    notes: list[str],
    prefixes: list[str],
) -> str | None:
    for note in notes:
        if not isinstance(note, str):
            continue

        for prefix in prefixes:
            if note.startswith(prefix):
                return note[
                    len(prefix):
                ].strip()

    return None


def _note_float(
    notes: list[str],
    prefixes: list[str],
    percent: bool = False,
) -> float | None:
    value = _note_value(
        notes,
        prefixes,
    )

    numeric_value = _safe_float(
        value
    )

    if numeric_value is None:
        return None

    if percent:
        return numeric_value / 100

    return numeric_value


# ---------------------------------------------------------------------
# Snapshot parsing
# ---------------------------------------------------------------------

def _load_snapshot(
    path_value: Any,
) -> dict:
    path_text = _safe_text(
        path_value
    )

    if path_text is None:
        return {}

    path = Path(path_text)

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        return {}

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            value = json.load(file)

        if isinstance(value, dict):
            return value

    except (
        OSError,
        json.JSONDecodeError,
    ):
        pass

    return {}


def _snapshot_value(
    snapshot: dict,
    names: list[str],
):
    containers = [
        snapshot,
        snapshot.get(
            "trade",
            {},
        ),
        snapshot.get(
            "research",
            {},
        ),
        snapshot.get(
            "execution_engine",
            {},
        ),
    ]

    for container in containers:
        if not isinstance(
            container,
            dict,
        ):
            continue

        for name in names:
            if name in container:
                value = container[
                    name
                ]

                if value is not None:
                    return value

    return None


# ---------------------------------------------------------------------
# Row normalization
# ---------------------------------------------------------------------

def _calculate_dte(
    expiration_value: Any,
    recommendation_date_value: Any,
) -> int | None:
    expiration_text = _safe_text(
        expiration_value
    )

    if expiration_text is None:
        return None

    if expiration_text.endswith(
        " DTE"
    ):
        return _safe_int(
            expiration_text.replace(
                " DTE",
                "",
            )
        )

    expiration = pd.to_datetime(
        expiration_text,
        errors="coerce",
    )

    recommendation_date = pd.to_datetime(
        recommendation_date_value,
        errors="coerce",
    )

    if (
        pd.isna(expiration)
        or pd.isna(recommendation_date)
    ):
        return None

    return int(
        (
            expiration.normalize()
            - recommendation_date.normalize()
        ).days
    )


def _normalize_row(
    row: pd.Series,
) -> dict:
    notes = _parse_notes(
        _first_present(
            row,
            [
                "notes",
                "Notes",
            ],
        )
    )

    snapshot = _load_snapshot(
        _first_present(
            row,
            [
                "SnapshotPath",
                "snapshot_path",
            ],
        )
    )

    def value(
        column_names: list[str],
        snapshot_names: list[str],
        note_prefixes: list[str] | None = None,
    ):
        direct_value = _first_present(
            row,
            column_names,
        )

        if direct_value is not None:
            return direct_value

        snapshot_result = _snapshot_value(
            snapshot,
            snapshot_names,
        )

        if snapshot_result is not None:
            return snapshot_result

        if note_prefixes:
            return _note_value(
                notes,
                note_prefixes,
            )

        return None

    recommendation_date = value(
        [
            "RecommendationDate",
            "recommendation_date",
        ],
        [
            "RecommendationDate",
            "recommendation_date",
        ],
    )

    expiration = value(
        [
            "expiration",
            "Expiration",
        ],
        [
            "expiration",
            "Expiration",
        ],
    )

    spread_pct = _safe_float(
        value(
            [
                "spread_pct",
                "SpreadPct",
                "SpreadPercent",
            ],
            [
                "spread_pct",
                "SpreadPct",
            ],
        )
    )

    if spread_pct is None:
        spread_pct = _note_float(
            notes,
            [
                "Bid/Ask Spread:",
                "Spread %:",
            ],
            percent=True,
        )

    spread_dollars = _safe_float(
        value(
            [
                "spread_dollars",
                "SpreadDollars",
            ],
            [
                "spread_dollars",
                "SpreadDollars",
            ],
        )
    )

    if spread_dollars is None:
        spread_dollars = _note_float(
            notes,
            [
                "Bid/Ask Spread Dollars:",
            ],
        )

    premium = _safe_float(
        value(
            [
                "premium",
                "Premium",
            ],
            [
                "premium",
                "Premium",
            ],
            [
                "Recommended premium:",
            ],
        )
    )

    research_price = _safe_float(
        value(
            [
                "research_price",
                "ResearchPrice",
            ],
            [
                "research_price",
                "ResearchPrice",
            ],
        )
    )

    if research_price is None:
        research_price = _note_float(
            notes,
            [
                "Research Price:",
            ],
        )

    if research_price is None:
        research_price = premium

    execution_entry_price = _safe_float(
        value(
            [
                "execution_entry_price",
                "ExecutionEntryPrice",
            ],
            [
                "execution_entry_price",
                "ExecutionEntryPrice",
            ],
        )
    )

    if execution_entry_price is None:
        execution_entry_price = _note_float(
            notes,
            [
                "Execution Entry Price:",
            ],
        )

    execution_exit_price = _safe_float(
        value(
            [
                "execution_exit_price",
                "ExecutionExitPrice",
            ],
            [
                "execution_exit_price",
                "ExecutionExitPrice",
            ],
        )
    )

    if execution_exit_price is None:
        execution_exit_price = _note_float(
            notes,
            [
                "Execution Exit Price:",
            ],
        )

    entry_execution_cost_pct = _safe_float(
        value(
            [
                "entry_execution_cost_pct",
                "EntryExecutionCostPct",
            ],
            [
                "entry_execution_cost_pct",
                "EntryExecutionCostPct",
            ],
        )
    )

    if entry_execution_cost_pct is None:
        entry_execution_cost_pct = _note_float(
            notes,
            [
                "Entry Execution Cost:",
            ],
            percent=True,
        )

    immediate_liquidation_return_pct = _safe_float(
        value(
            [
                "immediate_liquidation_return_pct",
                "ImmediateLiquidationReturnPct",
            ],
            [
                "immediate_liquidation_return_pct",
                "ImmediateLiquidationReturnPct",
            ],
        )
    )

    if immediate_liquidation_return_pct is None:
        immediate_liquidation_return_pct = _note_float(
            notes,
            [
                "Immediate Liquidation Return:",
            ],
            percent=True,
        )

    option_open_interest = _safe_int(
        value(
            [
                "option_open_interest",
                "OptionOpenInterest",
                "openInterest",
            ],
            [
                "option_open_interest",
                "OptionOpenInterest",
                "openInterest",
            ],
        )
    )

    if option_open_interest is None:
        option_open_interest = _safe_int(
            _note_value(
                notes,
                [
                    "Option Open Interest:",
                    "Open Interest:",
                ],
            )
        )

    option_volume = _safe_int(
        value(
            [
                "option_volume",
                "OptionVolume",
                "volume",
            ],
            [
                "option_volume",
                "OptionVolume",
                "volume",
            ],
        )
    )

    if option_volume is None:
        option_volume = _safe_int(
            _note_value(
                notes,
                [
                    "Option Volume:",
                    "Volume:",
                ],
            )
        )

    delta = _safe_float(
        value(
            [
                "delta",
                "Delta",
            ],
            [
                "delta",
                "Delta",
            ],
        )
    )

    if delta is None:
        delta = _note_float(
            notes,
            [
                "Delta:",
            ],
        )

    theta = _safe_float(
        value(
            [
                "theta",
                "Theta",
            ],
            [
                "theta",
                "Theta",
            ],
        )
    )

    if theta is None:
        theta = _note_float(
            notes,
            [
                "Theta:",
            ],
        )

    dte = _safe_int(
        value(
            [
                "dte",
                "DTE",
                "RecommendationDTE",
            ],
            [
                "dte",
                "DTE",
                "RecommendationDTE",
            ],
        )
    )

    if dte is None:
        dte = _safe_int(
            _note_value(
                notes,
                [
                    "DTE:",
                ],
            )
        )

    if dte is None:
        dte = _calculate_dte(
            expiration,
            recommendation_date,
        )

    position_value = _safe_float(
        value(
            [
                "position_value",
                "PositionValue",
            ],
            [
                "position_value",
                "PositionValue",
            ],
        )
    )

    if position_value is None:
        position_value = _note_float(
            notes,
            [
                "Position value:",
            ],
        )

    position_size_pct = _safe_float(
        value(
            [
                "position_size_pct",
                "PositionSizePct",
            ],
            [
                "position_size_pct",
                "PositionSizePct",
            ],
        )
    )

    if position_size_pct is None:
        note_position_size = _note_float(
            notes,
            [
                "Position Size:",
            ],
            percent=True,
        )

        if note_position_size is not None:
            position_size_pct = (
                note_position_size
            )

    return {
        "RecommendationID": value(
            [
                "RecommendationID",
                "recommendation_id",
            ],
            [
                "RecommendationID",
                "recommendation_id",
            ],
        ),
        "RecommendationDate": recommendation_date,
        "ticker": _safe_text(
            value(
                [
                    "ticker",
                    "Ticker",
                ],
                [
                    "ticker",
                    "Ticker",
                ],
            )
        ),
        "action": _safe_text(
            value(
                [
                    "action",
                    "Action",
                ],
                [
                    "action",
                    "Action",
                ],
            )
        ),
        "TradeStatus": _safe_text(
            value(
                [
                    "TradeStatus",
                    "trade_status",
                ],
                [
                    "TradeStatus",
                    "trade_status",
                ],
            )
        ),
        "option_strategy": _safe_text(
            value(
                [
                    "option_strategy",
                    "OptionStrategy",
                ],
                [
                    "option_strategy",
                    "OptionStrategy",
                ],
            )
        ),
        "expiration": _safe_text(
            expiration
        ),
        "dte": dte,
        "strike": _safe_float(
            value(
                [
                    "strike",
                    "Strike",
                ],
                [
                    "strike",
                    "Strike",
                ],
            )
        ),
        "premium": premium,
        "research_price": research_price,
        "execution_entry_price": (
            execution_entry_price
        ),
        "execution_exit_price": (
            execution_exit_price
        ),
        "spread_dollars": spread_dollars,
        "spread_pct": spread_pct,
        "entry_execution_cost_pct": (
            entry_execution_cost_pct
        ),
        "immediate_liquidation_return_pct": (
            immediate_liquidation_return_pct
        ),
        "execution_score": _safe_float(
            value(
                [
                    "execution_score",
                    "ExecutionScore",
                ],
                [
                    "execution_score",
                    "ExecutionScore",
                ],
                [
                    "Execution Score:",
                ],
            )
        ),
        "execution_grade": _safe_text(
            value(
                [
                    "execution_grade",
                    "ExecutionGrade",
                ],
                [
                    "execution_grade",
                    "ExecutionGrade",
                ],
                [
                    "Execution Grade:",
                ],
            )
        ),
        "execution_friction": _safe_text(
            value(
                [
                    "execution_friction",
                    "ExecutionFriction",
                ],
                [
                    "execution_friction",
                    "ExecutionFriction",
                ],
                [
                    "Execution Friction:",
                ],
            )
        ),
        "option_open_interest": (
            option_open_interest
        ),
        "option_volume": option_volume,
        "delta": delta,
        "theta": theta,
        "contracts": _safe_int(
            value(
                [
                    "contracts",
                    "Contracts",
                ],
                [
                    "contracts",
                    "Contracts",
                ],
            )
        ),
        "position_value": position_value,
        "position_size_pct": (
            position_size_pct
        ),
        "trade_quality_score": _safe_float(
            value(
                [
                    "trade_quality_score",
                    "TradeQualityScore",
                ],
                [
                    "trade_quality_score",
                    "TradeQualityScore",
                ],
                [
                    "Trade Quality Score:",
                ],
            )
        ),
        "trade_quality_grade": _safe_text(
            value(
                [
                    "trade_quality_grade",
                    "TradeQualityGrade",
                ],
                [
                    "trade_quality_grade",
                    "TradeQualityGrade",
                ],
                [
                    "Trade Quality Grade:",
                ],
            )
        ),
        "SnapshotPath": _safe_text(
            _first_present(
                row,
                [
                    "SnapshotPath",
                    "snapshot_path",
                ],
            )
        ),
    }


# ---------------------------------------------------------------------
# Dataset selection
# ---------------------------------------------------------------------

def _load_journal() -> pd.DataFrame:
    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(
            f"Journal not found: {JOURNAL_PATH}"
        )

    return pd.read_csv(
        JOURNAL_PATH,
        low_memory=False,
    )


def _is_executable(
    row: pd.Series,
) -> bool:
    action = _safe_text(
        row.get("action")
    )

    status = _safe_text(
        row.get("TradeStatus")
    )

    contracts = _safe_int(
        row.get("contracts")
    )

    premium = _safe_float(
        row.get("premium")
    )

    option_strategy = _safe_text(
        row.get("option_strategy")
    )

    if action != "Evaluate Options":
        return False

    if status in {
        "NOT_EXECUTABLE",
        "PASS",
        "WATCHLIST",
    }:
        return False

    return (
        option_strategy is not None
        and premium is not None
        and premium > 0
        and contracts is not None
        and contracts > 0
    )


def _select_sample(
    dataframe: pd.DataFrame,
    limit: int | None,
    days: int | None,
    snapshot_only: bool,
) -> pd.DataFrame:
    selected = dataframe.copy()

    selected[
        "RecommendationDate"
    ] = pd.to_datetime(
        selected["RecommendationDate"],
        errors="coerce",
    )

    selected = selected[
        selected.apply(
            _is_executable,
            axis=1,
        )
    ].copy()

    if snapshot_only:
        selected = selected[
            selected[
                "SnapshotPath"
            ].notna()
        ].copy()

    if days is not None:
        cutoff = (
            pd.Timestamp.now()
            - pd.Timedelta(
                days=days,
            )
        )

        selected = selected[
            selected[
                "RecommendationDate"
            ] >= cutoff
        ].copy()

    selected = selected.sort_values(
        "RecommendationDate",
        ascending=False,
        na_position="last",
    )

    if limit is not None:
        selected = selected.head(
            limit
        ).copy()

    return selected.reset_index(
        drop=True
    )


# ---------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------

def _premium_bucket(
    value: Any,
) -> str:
    premium = _safe_float(
        value
    )

    if premium is None:
        return "Unknown"

    if premium < 1:
        return "<$1"

    if premium < 2:
        return "$1-$2"

    if premium < 5:
        return "$2-$5"

    if premium < 10:
        return "$5-$10"

    return "$10+"


def _dte_bucket(
    value: Any,
) -> str:
    dte = _safe_float(
        value
    )

    if dte is None:
        return "Unknown"

    if dte <= 30:
        return "<=30"

    if dte <= 45:
        return "31-45"

    if dte <= 60:
        return "46-60"

    if dte <= 90:
        return "61-90"

    return "91+"


def _oi_bucket(
    value: Any,
) -> str:
    open_interest = _safe_float(
        value
    )

    if open_interest is None:
        return "Unknown"

    if open_interest < 25:
        return "<25"

    if open_interest < 100:
        return "25-99"

    if open_interest < 250:
        return "100-249"

    if open_interest < 1000:
        return "250-999"

    return "1000+"


def _volume_bucket(
    value: Any,
) -> str:
    volume = _safe_float(
        value
    )

    if volume is None:
        return "Unknown"

    if volume < 10:
        return "<10"

    if volume < 50:
        return "10-49"

    if volume < 200:
        return "50-199"

    if volume < 1000:
        return "200-999"

    return "1000+"


def _describe_spread(
    dataframe: pd.DataFrame,
) -> dict:
    spreads = pd.to_numeric(
        dataframe["spread_pct"],
        errors="coerce",
    ).dropna()

    if spreads.empty:
        return {
            "count": 0,
            "average": None,
            "median": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "maximum": None,
        }

    return {
        "count": int(
            len(spreads)
        ),
        "average": float(
            spreads.mean()
        ),
        "median": float(
            spreads.median()
        ),
        "p75": float(
            spreads.quantile(
                0.75
            )
        ),
        "p90": float(
            spreads.quantile(
                0.90
            )
        ),
        "p95": float(
            spreads.quantile(
                0.95
            )
        ),
        "maximum": float(
            spreads.max()
        ),
    }


def _group_spread_summary(
    dataframe: pd.DataFrame,
    group_column: str,
    order: list[str],
) -> pd.DataFrame:
    rows = []

    for group_name in order:
        group = dataframe[
            dataframe[
                group_column
            ] == group_name
        ]

        spreads = pd.to_numeric(
            group["spread_pct"],
            errors="coerce",
        ).dropna()

        if group.empty:
            continue

        rows.append(
            {
                group_column: group_name,
                "Recommendations": int(
                    len(group)
                ),
                "Spread Observations": int(
                    len(spreads)
                ),
                "Average Spread": (
                    float(
                        spreads.mean()
                    )
                    if not spreads.empty
                    else None
                ),
                "Median Spread": (
                    float(
                        spreads.median()
                    )
                    if not spreads.empty
                    else None
                ),
                "90th Percentile": (
                    float(
                        spreads.quantile(
                            0.90
                        )
                    )
                    if not spreads.empty
                    else None
                ),
            }
        )

    return pd.DataFrame(
        rows
    )


def _correlation(
    dataframe: pd.DataFrame,
    column_a: str,
    column_b: str,
) -> float | None:
    subset = dataframe[
        [
            column_a,
            column_b,
        ]
    ].copy()

    subset[column_a] = pd.to_numeric(
        subset[column_a],
        errors="coerce",
    )

    subset[column_b] = pd.to_numeric(
        subset[column_b],
        errors="coerce",
    )

    subset = subset.dropna()

    if len(subset) < 3:
        return None

    if (
        subset[column_a].nunique()
        < 2
        or subset[column_b].nunique()
        < 2
    ):
        return None

    return float(
        subset[column_a].corr(
            subset[column_b]
        )
    )


def _threshold_summary(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    spreads = pd.to_numeric(
        dataframe["spread_pct"],
        errors="coerce",
    )

    observed_count = int(
        spreads.notna().sum()
    )

    rows = []

    for threshold in SPREAD_THRESHOLDS:
        failed = int(
            (
                spreads > threshold
            ).sum()
        )

        rows.append(
            {
                "Maximum Spread": threshold,
                "Failed": failed,
                "Observed": observed_count,
                "Failure Rate": (
                    failed
                    / observed_count
                    if observed_count > 0
                    else None
                ),
            }
        )

    return pd.DataFrame(
        rows
    )


def _affordability_summary(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    premiums = pd.to_numeric(
        dataframe["premium"],
        errors="coerce",
    )

    contract_costs = (
        premiums * 100
    )

    rows = []

    for portfolio_value in [
        CURRENT_PORTFOLIO_VALUE,
        LARGER_PORTFOLIO_VALUE,
    ]:
        for max_position_pct in (
            POSITION_SIZE_SCENARIOS
        ):
            budget = (
                portfolio_value
                * max_position_pct
            )

            affordable = (
                contract_costs <= budget
            )

            observed = int(
                contract_costs.notna().sum()
            )

            affordable_count = int(
                affordable.fillna(
                    False
                ).sum()
            )

            rows.append(
                {
                    "Portfolio Value": (
                        portfolio_value
                    ),
                    "Max Position %": (
                        max_position_pct
                    ),
                    "Contract Budget": (
                        budget
                    ),
                    "Affordable": (
                        affordable_count
                    ),
                    "Observed": observed,
                    "Affordable Rate": (
                        affordable_count
                        / observed
                        if observed > 0
                        else None
                    ),
                }
            )

    return pd.DataFrame(
        rows
    )


def _account_constraint_summary(
    dataframe: pd.DataFrame,
) -> dict:
    premiums = pd.to_numeric(
        dataframe["premium"],
        errors="coerce",
    )

    spreads = pd.to_numeric(
        dataframe["spread_pct"],
        errors="coerce",
    )

    current_five_percent_budget = (
        CURRENT_PORTFOLIO_VALUE
        * 0.05
    )

    expensive_for_current = (
        premiums * 100
        > current_five_percent_budget
    )

    valid = (
        premiums.notna()
        & spreads.notna()
    )

    affordable_group = spreads[
        valid
        & ~expensive_for_current
    ]

    unaffordable_group = spreads[
        valid
        & expensive_for_current
    ]

    return {
        "current_5pct_budget": (
            current_five_percent_budget
        ),
        "affordable_count": int(
            len(affordable_group)
        ),
        "unaffordable_count": int(
            len(unaffordable_group)
        ),
        "affordable_average_spread": (
            float(
                affordable_group.mean()
            )
            if not affordable_group.empty
            else None
        ),
        "unaffordable_average_spread": (
            float(
                unaffordable_group.mean()
            )
            if not unaffordable_group.empty
            else None
        ),
        "affordable_median_spread": (
            float(
                affordable_group.median()
            )
            if not affordable_group.empty
            else None
        ),
        "unaffordable_median_spread": (
            float(
                unaffordable_group.median()
            )
            if not unaffordable_group.empty
            else None
        ),
    }


def _format_pct(
    value: Any,
) -> str:
    numeric_value = _safe_float(
        value
    )

    if numeric_value is None:
        return "N/A"

    return f"{numeric_value:.2%}"


def _format_money(
    value: Any,
) -> str:
    numeric_value = _safe_float(
        value
    )

    if numeric_value is None:
        return "N/A"

    return f"${numeric_value:,.2f}"


def _format_summary_table(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    formatted = dataframe.copy()

    for column in [
        "Average Spread",
        "Median Spread",
        "90th Percentile",
        "Maximum Spread",
        "Failure Rate",
        "Max Position %",
        "Affordable Rate",
    ]:
        if column in formatted.columns:
            formatted[column] = (
                formatted[column]
                .apply(_format_pct)
            )

    for column in [
        "Portfolio Value",
        "Contract Budget",
    ]:
        if column in formatted.columns:
            formatted[column] = (
                formatted[column]
                .apply(_format_money)
            )

    return formatted


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------

def _write_markdown_report(
    output_path: Path,
    sample: pd.DataFrame,
    spread_stats: dict,
    premium_summary: pd.DataFrame,
    dte_summary: pd.DataFrame,
    oi_summary: pd.DataFrame,
    volume_summary: pd.DataFrame,
    threshold_summary: pd.DataFrame,
    affordability_summary: pd.DataFrame,
    account_summary: dict,
    correlations: dict,
    worst_spreads: pd.DataFrame,
) -> None:
    lines: list[str] = []

    lines.append(
        "# Project Stonks Execution and Liquidity Retrospective"
    )
    lines.append("")
    lines.append(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    lines.append("")
    lines.append(
        f"Recommendations analyzed: {len(sample)}"
    )
    lines.append(
        "This analysis is read-only and does not alter "
        "contract selection or portfolio allocation."
    )
    lines.append("")

    lines.append(
        "## Overall Spread Distribution"
    )
    lines.append("")
    lines.append(
        f"- Recommendations with spread data: "
        f"{spread_stats['count']}"
    )
    lines.append(
        f"- Average spread: "
        f"{_format_pct(spread_stats['average'])}"
    )
    lines.append(
        f"- Median spread: "
        f"{_format_pct(spread_stats['median'])}"
    )
    lines.append(
        f"- 75th percentile: "
        f"{_format_pct(spread_stats['p75'])}"
    )
    lines.append(
        f"- 90th percentile: "
        f"{_format_pct(spread_stats['p90'])}"
    )
    lines.append(
        f"- 95th percentile: "
        f"{_format_pct(spread_stats['p95'])}"
    )
    lines.append(
        f"- Maximum spread: "
        f"{_format_pct(spread_stats['maximum'])}"
    )
    lines.append("")

    sections = [
        (
            "Spread by Premium Range",
            premium_summary,
        ),
        (
            "Spread by DTE",
            dte_summary,
        ),
        (
            "Spread by Open Interest",
            oi_summary,
        ),
        (
            "Spread by Daily Volume",
            volume_summary,
        ),
        (
            "Proposed Spread Threshold Impact",
            threshold_summary,
        ),
        (
            "Contract Affordability Scenarios",
            affordability_summary,
        ),
    ]

    for title, dataframe in sections:
        lines.append(
            f"## {title}"
        )
        lines.append("")

        if dataframe.empty:
            lines.append(
                "No usable data available."
            )
        else:
            lines.append(
                _format_summary_table(
                    dataframe
                ).to_markdown(
                    index=False
                )
            )

        lines.append("")

    lines.append(
        "## Correlation Analysis"
    )
    lines.append("")
    lines.append(
        f"- Premium vs. spread: "
        f"{correlations['premium_vs_spread']}"
    )
    lines.append(
        f"- Open interest vs. spread: "
        f"{correlations['oi_vs_spread']}"
    )
    lines.append(
        f"- Volume vs. spread: "
        f"{correlations['volume_vs_spread']}"
    )
    lines.append(
        f"- DTE vs. spread: "
        f"{correlations['dte_vs_spread']}"
    )
    lines.append("")

    lines.append(
        "## Current Account-Constraint Comparison"
    )
    lines.append("")
    lines.append(
        f"- Current portfolio: "
        f"{_format_money(CURRENT_PORTFOLIO_VALUE)}"
    )
    lines.append(
        f"- Five-percent contract budget: "
        f"{_format_money(account_summary['current_5pct_budget'])}"
    )
    lines.append(
        f"- Recommendations affordable within that budget: "
        f"{account_summary['affordable_count']}"
    )
    lines.append(
        f"- Recommendations above that budget: "
        f"{account_summary['unaffordable_count']}"
    )
    lines.append(
        f"- Average spread for affordable contracts: "
        f"{_format_pct(account_summary['affordable_average_spread'])}"
    )
    lines.append(
        f"- Average spread for contracts above budget: "
        f"{_format_pct(account_summary['unaffordable_average_spread'])}"
    )
    lines.append(
        f"- Median spread for affordable contracts: "
        f"{_format_pct(account_summary['affordable_median_spread'])}"
    )
    lines.append(
        f"- Median spread for contracts above budget: "
        f"{_format_pct(account_summary['unaffordable_median_spread'])}"
    )
    lines.append("")

    lines.append(
        "### Interpretation Limitation"
    )
    lines.append("")
    lines.append(
        "The journal records the contract that was selected. "
        "It generally does not retain every rejected alternative "
        "contract from the same option chain. Therefore, this report "
        "can determine whether selected cheap contracts tend to have "
        "wider spreads, but it cannot yet prove that a larger account "
        "would have caused the selector to choose a different, more "
        "liquid contract. A candidate-contract leaderboard would be "
        "needed to answer that counterfactual conclusively."
    )
    lines.append("")

    lines.append(
        "## Worst Selected Spreads"
    )
    lines.append("")

    if worst_spreads.empty:
        lines.append(
            "No spread observations available."
        )
    else:
        formatted = worst_spreads.copy()

        for column in [
            "spread_pct",
            "entry_execution_cost_pct",
            "immediate_liquidation_return_pct",
            "position_size_pct",
        ]:
            if column in formatted.columns:
                formatted[column] = (
                    formatted[column]
                    .apply(_format_pct)
                )

        for column in [
            "premium",
            "execution_entry_price",
            "execution_exit_price",
            "spread_dollars",
            "position_value",
        ]:
            if column in formatted.columns:
                formatted[column] = (
                    formatted[column]
                    .apply(_format_money)
                )

        lines.append(
            formatted.to_markdown(
                index=False
            )
        )

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------

def run_retrospective(
    limit: int | None = DEFAULT_LIMIT,
    days: int | None = None,
    snapshot_only: bool = False,
) -> dict:
    raw_journal = _load_journal()

    print(
        "\nNormalizing journal execution data..."
    )

    normalized_rows = [
        _normalize_row(row)
        for _, row in raw_journal.iterrows()
    ]

    normalized = pd.DataFrame(
        normalized_rows
    )

    sample = _select_sample(
        dataframe=normalized,
        limit=limit,
        days=days,
        snapshot_only=snapshot_only,
    )

    if sample.empty:
        raise RuntimeError(
            "No executable recommendations matched "
            "the requested sample."
        )

    sample["PremiumBucket"] = (
        sample["premium"].apply(
            _premium_bucket
        )
    )

    sample["DTEBucket"] = (
        sample["dte"].apply(
            _dte_bucket
        )
    )

    sample["OpenInterestBucket"] = (
        sample[
            "option_open_interest"
        ].apply(
            _oi_bucket
        )
    )

    sample["VolumeBucket"] = (
        sample["option_volume"].apply(
            _volume_bucket
        )
    )

    spread_stats = _describe_spread(
        sample
    )

    premium_summary = _group_spread_summary(
        dataframe=sample,
        group_column="PremiumBucket",
        order=[
            "<$1",
            "$1-$2",
            "$2-$5",
            "$5-$10",
            "$10+",
            "Unknown",
        ],
    )

    dte_summary = _group_spread_summary(
        dataframe=sample,
        group_column="DTEBucket",
        order=[
            "<=30",
            "31-45",
            "46-60",
            "61-90",
            "91+",
            "Unknown",
        ],
    )

    oi_summary = _group_spread_summary(
        dataframe=sample,
        group_column="OpenInterestBucket",
        order=[
            "<25",
            "25-99",
            "100-249",
            "250-999",
            "1000+",
            "Unknown",
        ],
    )

    volume_summary = _group_spread_summary(
        dataframe=sample,
        group_column="VolumeBucket",
        order=[
            "<10",
            "10-49",
            "50-199",
            "200-999",
            "1000+",
            "Unknown",
        ],
    )

    threshold_summary = _threshold_summary(
        sample
    )

    affordability_summary = (
        _affordability_summary(
            sample
        )
    )

    account_summary = (
        _account_constraint_summary(
            sample
        )
    )

    correlations = {
        "premium_vs_spread": (
            _correlation(
                sample,
                "premium",
                "spread_pct",
            )
        ),
        "oi_vs_spread": (
            _correlation(
                sample,
                "option_open_interest",
                "spread_pct",
            )
        ),
        "volume_vs_spread": (
            _correlation(
                sample,
                "option_volume",
                "spread_pct",
            )
        ),
        "dte_vs_spread": (
            _correlation(
                sample,
                "dte",
                "spread_pct",
            )
        ),
    }

    correlations = {
        key: (
            round(value, 4)
            if value is not None
            else "N/A"
        )
        for key, value in correlations.items()
    }

    worst_columns = [
        column
        for column in [
            "RecommendationDate",
            "ticker",
            "expiration",
            "dte",
            "strike",
            "premium",
            "execution_entry_price",
            "execution_exit_price",
            "spread_dollars",
            "spread_pct",
            "entry_execution_cost_pct",
            "immediate_liquidation_return_pct",
            "option_open_interest",
            "option_volume",
            "position_value",
            "position_size_pct",
            "execution_score",
            "execution_grade",
        ]
        if column in sample.columns
    ]

    worst_spreads = (
        sample.dropna(
            subset=["spread_pct"]
        )
        .sort_values(
            "spread_pct",
            ascending=False,
        )
        .head(25)[worst_columns]
        .copy()
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    normalized_output_path = (
        PROCESSED_DIR
        / (
            "execution_liquidity_sample_"
            f"{timestamp}.csv"
        )
    )

    report_path = (
        REPORTS_DIR
        / (
            "execution_liquidity_retrospective_"
            f"{timestamp}.md"
        )
    )

    export_columns = [
        column
        for column in OUTPUT_COLUMNS
        if column in sample.columns
    ]

    sample[
        export_columns
    ].to_csv(
        normalized_output_path,
        index=False,
    )

    _write_markdown_report(
        output_path=report_path,
        sample=sample,
        spread_stats=spread_stats,
        premium_summary=premium_summary,
        dte_summary=dte_summary,
        oi_summary=oi_summary,
        volume_summary=volume_summary,
        threshold_summary=threshold_summary,
        affordability_summary=affordability_summary,
        account_summary=account_summary,
        correlations=correlations,
        worst_spreads=worst_spreads,
    )

    print()
    print(
        "========================================"
    )
    print(
        "Project Stonks Execution Retrospective"
    )
    print(
        "========================================"
    )
    print(
        f"Recommendations analyzed: {len(sample)}"
    )
    print(
        "Recommendations with spread data: "
        f"{spread_stats['count']}"
    )
    print(
        "Average spread: "
        f"{_format_pct(spread_stats['average'])}"
    )
    print(
        "Median spread: "
        f"{_format_pct(spread_stats['median'])}"
    )
    print(
        "90th percentile spread: "
        f"{_format_pct(spread_stats['p90'])}"
    )
    print(
        "Worst spread: "
        f"{_format_pct(spread_stats['maximum'])}"
    )

    print()
    print("Threshold impact")

    for _, threshold_row in (
        threshold_summary.iterrows()
    ):
        print(
            f"- Above "
            f"{_format_pct(threshold_row['Maximum Spread'])}: "
            f"{int(threshold_row['Failed'])} "
            f"({_format_pct(threshold_row['Failure Rate'])})"
        )

    print()
    print("Correlations")
    print(
        "- Premium vs spread: "
        f"{correlations['premium_vs_spread']}"
    )
    print(
        "- Open interest vs spread: "
        f"{correlations['oi_vs_spread']}"
    )
    print(
        "- Volume vs spread: "
        f"{correlations['volume_vs_spread']}"
    )
    print(
        "- DTE vs spread: "
        f"{correlations['dte_vs_spread']}"
    )

    print()
    print(
        "Current $15k portfolio at 5% maximum"
    )
    print(
        "- Contract budget: "
        f"{_format_money(account_summary['current_5pct_budget'])}"
    )
    print(
        "- Affordable recommendations: "
        f"{account_summary['affordable_count']}"
    )
    print(
        "- Above-budget recommendations: "
        f"{account_summary['unaffordable_count']}"
    )
    print(
        "- Affordable average spread: "
        f"{_format_pct(account_summary['affordable_average_spread'])}"
    )
    print(
        "- Above-budget average spread: "
        f"{_format_pct(account_summary['unaffordable_average_spread'])}"
    )

    print()
    print(
        f"Normalized sample: {normalized_output_path}"
    )
    print(
        f"Report: {report_path}"
    )

    return {
        "status": "PASS",
        "sample_size": int(
            len(sample)
        ),
        "spread_statistics": (
            spread_stats
        ),
        "correlations": correlations,
        "account_constraint_summary": (
            account_summary
        ),
        "sample_path": str(
            normalized_output_path
        ),
        "report_path": str(
            report_path
        ),
    }


def _parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Audit recent Project Stonks "
            "recommendations for execution and "
            "liquidity quality."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            "Number of most recent executable "
            "recommendations to analyze."
        ),
    )

    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help=(
            "Analyze recommendations generated "
            "within the last N calendar days."
        ),
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Analyze all executable recommendations."
        ),
    )

    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help=(
            "Analyze only recommendations with a "
            "snapshot path."
        ),
    )

    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_arguments()

    selected_limit = (
        None
        if arguments.all
        else arguments.limit
    )

    run_retrospective(
        limit=selected_limit,
        days=arguments.days,
        snapshot_only=(
            arguments.snapshot_only
        ),
    )