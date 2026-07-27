"""
Project Stonks
Portfolio Allocation Engine

Sprint 33B

Purpose
-------
Convert the context-independent Institutional Trade Score into a
context-aware Portfolio Score.

Institutional Trade Score answers:

    "How good is this trade?"

Portfolio Score answers:

    "How desirable is this trade in today's market environment?"

The allocator no longer attempts to reconstruct trade quality by parsing
human-readable notes.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from config import (
    DEFENSIVE_ALLOCATION_MULTIPLIER,
    PORTFOLIO_SCORE_MARKET_MULTIPLIER,
    RISK_ON_ALLOCATION_MULTIPLIER,
    SELECTIVE_ALLOCATION_MULTIPLIER,
)


DEFAULT_MAX_RECOMMENDATIONS = 3


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


def _is_executable_trade(
    row: pd.Series,
) -> bool:
    """
    Confirm that a row represents a complete option recommendation that
    can be considered for allocation.
    """

    if _safe_text(row.get("action")) != "Evaluate Options":
        return False

    required_text_fields = [
        "option_strategy",
        "expiration",
    ]

    for field in required_text_fields:
        if _safe_text(row.get(field)) is None:
            return False

    strike = _safe_float(
        row.get("strike")
    )

    premium = _safe_float(
        row.get("premium")
    )

    contracts = _safe_int(
        row.get("contracts")
    )

    institutional_score = _safe_float(
        row.get("institutional_trade_score")
    )

    if strike is None:
        return False

    if premium is None or premium <= 0:
        return False

    if contracts is None or contracts <= 0:
        return False

    if (
        institutional_score is None
        or institutional_score <= 0
    ):
        return False

    return True


def _market_multiplier(
    market_context: dict,
) -> float:
    """
    Apply the configured multiplier for the current risk environment.
    """

    if not PORTFOLIO_SCORE_MARKET_MULTIPLIER:
        return 1.0

    risk_mode = market_context.get(
        "risk_mode",
        "Normal",
    )

    if risk_mode == "Defensive":
        return DEFENSIVE_ALLOCATION_MULTIPLIER

    if risk_mode == "Selective":
        return SELECTIVE_ALLOCATION_MULTIPLIER

    return RISK_ON_ALLOCATION_MULTIPLIER


def _directional_alignment_multiplier(
    row: pd.Series,
    market_context: dict,
) -> float:
    """
    Preserve the existing directional market-regime protection.

    This does not determine whether the trade itself is good. It only
    adjusts its portfolio desirability in the current market regime.
    """

    market_regime = market_context.get(
        "market_regime",
        "Unknown",
    )

    option_strategy = _safe_text(
        row.get("option_strategy")
    )

    if (
        market_regime == "Bearish"
        and option_strategy == "Long Call"
    ):
        return 0.50

    if (
        market_regime == "Bullish"
        and option_strategy == "Long Put"
    ):
        return 0.70

    return 1.0


def _calculate_portfolio_score(
    row: pd.Series,
    market_context: dict,
) -> float:
    """
    Convert Institutional Trade Score into Portfolio Score.

    Portfolio Score =
        Institutional Trade Score
        x Market Risk Multiplier
        x Directional Alignment Multiplier
    """

    if not _is_executable_trade(row):
        return 0.0

    institutional_score = _safe_float(
        row.get("institutional_trade_score")
    )

    if institutional_score is None:
        return 0.0

    market_multiplier = _market_multiplier(
        market_context
    )

    directional_multiplier = (
        _directional_alignment_multiplier(
            row=row,
            market_context=market_context,
        )
    )

    portfolio_score = (
        institutional_score
        * market_multiplier
        * directional_multiplier
    )

    return round(
        max(
            0.0,
            min(
                100.0,
                portfolio_score,
            ),
        ),
        1,
    )


def _build_portfolio_reason(
    row: pd.Series,
    market_context: dict,
) -> str:
    if not _is_executable_trade(row):
        return "Trade is not executable or lacks an Institutional Trade Score"

    institutional_score = _safe_float(
        row.get("institutional_trade_score")
    )

    institutional_grade = _safe_text(
        row.get("institutional_trade_grade")
    )

    risk_mode = market_context.get(
        "risk_mode",
        "Normal",
    )

    market_multiplier = _market_multiplier(
        market_context
    )

    directional_multiplier = (
        _directional_alignment_multiplier(
            row=row,
            market_context=market_context,
        )
    )

    parts = [
        (
            "Institutional Trade Score "
            f"{institutional_score:.1f}"
        ),
    ]

    if institutional_grade is not None:
        parts.append(
            f"Grade {institutional_grade}"
        )

    parts.append(
        (
            f"Market mode {risk_mode} "
            f"({market_multiplier:.2f}x)"
        )
    )

    if directional_multiplier < 1.0:
        parts.append(
            (
                "Directional market adjustment "
                f"({directional_multiplier:.2f}x)"
            )
        )

    return "; ".join(parts)


def allocate_portfolio(
    trades_df: pd.DataFrame,
    market_context: dict,
    max_recommendations: int = DEFAULT_MAX_RECOMMENDATIONS,
) -> pd.DataFrame:
    """
    Rank executable trades by Portfolio Score and assign allocation
    decisions.

    Existing compatibility columns are preserved:

    - allocation_score
    - allocation_rank
    - allocation_decision
    - PortfolioStatus

    `allocation_score` is now an alias for `portfolio_score`.
    """

    trades_df = trades_df.copy()

    if trades_df.empty:
        return trades_df

    if max_recommendations < 0:
        raise ValueError(
            "max_recommendations cannot be negative."
        )

    # ------------------------------------------------------------------
    # Market context
    # ------------------------------------------------------------------

    trades_df["market_regime"] = market_context.get(
        "market_regime"
    )

    trades_df["risk_mode"] = market_context.get(
        "risk_mode"
    )

    trades_df["allocation_bias"] = market_context.get(
        "allocation_bias"
    )

    trades_df["market_score"] = market_context.get(
        "market_score"
    )

    trades_df["portfolio_market_multiplier"] = (
        _market_multiplier(
            market_context
        )
    )

    trades_df[
        "portfolio_directional_multiplier"
    ] = trades_df.apply(
        lambda row: _directional_alignment_multiplier(
            row=row,
            market_context=market_context,
        ),
        axis=1,
    )

    # ------------------------------------------------------------------
    # Portfolio scoring
    # ------------------------------------------------------------------

    trades_df["portfolio_score"] = (
        trades_df.apply(
            lambda row: _calculate_portfolio_score(
                row=row,
                market_context=market_context,
            ),
            axis=1,
        )
    )

    # Preserve compatibility with existing reports and downstream code.
    trades_df["allocation_score"] = (
        trades_df["portfolio_score"]
    )

    trades_df["portfolio_score_reason"] = (
        trades_df.apply(
            lambda row: _build_portfolio_reason(
                row=row,
                market_context=market_context,
            ),
            axis=1,
        )
    )

    # ------------------------------------------------------------------
    # Default allocation state
    # ------------------------------------------------------------------

    trades_df["allocation_rank"] = pd.NA

    trades_df["allocation_decision"] = (
        "No Allocation"
    )

    trades_df["PortfolioStatus"] = (
        "NOT_ALLOCATED"
    )

    # ------------------------------------------------------------------
    # Rank executable trades
    # ------------------------------------------------------------------

    executable_mask = trades_df.apply(
        _is_executable_trade,
        axis=1,
    )

    eligible = trades_df[
        executable_mask
        & (
            trades_df["portfolio_score"]
            > 0
        )
    ].copy()

    eligible = eligible.sort_values(
        [
            "portfolio_score",
            "institutional_trade_score",
            "execution_score",
            "trade_quality_score",
            "confidence",
        ],
        ascending=[
            False,
            False,
            False,
            False,
            False,
        ],
        na_position="last",
    )

    for rank, index in enumerate(
        eligible.index,
        start=1,
    ):
        trades_df.loc[
            index,
            "allocation_rank",
        ] = rank

        if rank <= max_recommendations:
            trades_df.loc[
                index,
                "allocation_decision",
            ] = "Allocate"

            trades_df.loc[
                index,
                "PortfolioStatus",
            ] = "OPEN"

        else:
            trades_df.loc[
                index,
                "allocation_decision",
            ] = "Watch"

    return trades_df