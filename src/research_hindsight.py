"""
Project Stonks
Research Hindsight Engine

Sprint 31A

Purpose
-------
Continuously monitor the research quality of every directional recommendation,
regardless of whether the recommendation became an executed position.

Each recommendation receives:

1. Rolling research monitoring while the recommendation is still active.
2. Final hindsight evaluation once its expected holding period has elapsed.

Inputs
------
- data/trade_journal.csv
- Immutable recommendation snapshots when available
- Historical underlying and SPY prices

Outputs
-------
- Timestamped research_hindsight CSV in data/processed/

Historical recommendations and snapshots are never modified.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from schwab.market_data_client import (
    get_normalized_price_history,
)
from trade_journal import JOURNAL_PATH

from trade_journal import JOURNAL_PATH


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

DEFAULT_HOLDING_PERIOD_DAYS = 45
MINIMUM_TRADING_DAYS = 2
FIXED_HORIZON_TRADING_DAYS = (3, 5, 7, 14, 30)
MEANINGFUL_RETURN_THRESHOLD = 0.01
NEUTRAL_RETURN_BAND = 0.0025


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        return None

    parsed = pd.to_datetime(
        value,
        errors="coerce",
        utc=True,
    )

    if pd.isna(parsed):
        return None

    return parsed.tz_convert(None)


def _load_snapshot(path_value: Any) -> dict:
    if path_value is None or pd.isna(path_value):
        return {}

    snapshot_path = Path(str(path_value))

    if not snapshot_path.exists():
        return {}

    try:
        with snapshot_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            snapshot = json.load(file)

        if isinstance(snapshot, dict):
            return snapshot

    except (OSError, json.JSONDecodeError):
        pass

    return {}


def _parse_notes(notes_value: Any) -> list[str]:
    if isinstance(notes_value, list):
        return [str(note) for note in notes_value]

    if notes_value is None or pd.isna(notes_value):
        return []

    if isinstance(notes_value, str):
        try:
            parsed = ast.literal_eval(notes_value)

            if isinstance(parsed, list):
                return [str(note) for note in parsed]

        except (ValueError, SyntaxError):
            pass

        return [notes_value]

    return []


def _holding_period_from_notes(
    notes_value: Any,
) -> int | None:
    notes = _parse_notes(notes_value)
    prefix = "Expected Holding Period:"

    for note in notes:
        if not note.startswith(prefix):
            continue

        value = (
            note.replace(prefix, "")
            .replace("days", "")
            .strip()
        )

        try:
            holding_period = int(float(value))

            if holding_period > 0:
                return holding_period

        except (TypeError, ValueError):
            continue

    return None


def _holding_period_from_snapshot(
    snapshot: dict,
) -> int | None:
    research = snapshot.get("research", {})

    if not isinstance(research, dict):
        return None

    for field in [
        "HoldingPeriodDays",
        "holding_period_days",
    ]:
        value = research.get(field)

        if value is None:
            continue

        try:
            holding_period = int(float(value))

            if holding_period > 0:
                return holding_period

        except (TypeError, ValueError):
            continue

    return None


def _resolve_holding_period(
    row: pd.Series,
    snapshot: dict,
) -> int:
    snapshot_horizon = _holding_period_from_snapshot(
        snapshot
    )

    if snapshot_horizon is not None:
        return snapshot_horizon

    journal_horizon = _holding_period_from_notes(
        row.get("notes")
    )

    if journal_horizon is not None:
        return journal_horizon

    return DEFAULT_HOLDING_PERIOD_DAYS


def _determine_direction(
    row: pd.Series,
) -> str | None:
    option_strategy = str(
        row.get("option_strategy", "")
    ).strip()

    opportunity_type = str(
        row.get("opportunity_type", "")
    ).strip()

    if option_strategy == "Long Call":
        return "BULLISH"

    if option_strategy == "Long Put":
        return "BEARISH"

    if "Call" in opportunity_type:
        return "BULLISH"

    if "Put" in opportunity_type:
        return "BEARISH"

    return None


def _download_prices(
    tickers: list[str],
    start_date,
    end_date,
) -> pd.DataFrame:
    """
    Download underlying tickers and SPY from Schwab.

    Returns a ticker-first MultiIndex DataFrame:

        market_data[ticker]["Close"]

    Only the requested date range is retained.
    """

    symbols = sorted(
        set(
            tickers
            + ["SPY"]
        )
    )

    if not symbols:
        return pd.DataFrame()

    start_timestamp = pd.Timestamp(
        start_date
    )

    end_timestamp = pd.Timestamp(
        end_date
    )

    requested_days = (
        end_timestamp
        - start_timestamp
    ).days

    history_period = (
        2
        if requested_days > 365
        else 1
    )

    frames = {}

    total_symbols = len(symbols)

    for index, ticker in enumerate(
        symbols,
        start=1,
    ):

        print(
            "[research_hindsight] "
            f"{index}/{total_symbols} {ticker}"
        )

        schwab_symbol = (
            str(ticker)
            .upper()
            .strip()
            .replace("-", "/")
        )

        try:

            candles = (
                get_normalized_price_history(
                    ticker=schwab_symbol,
                    period_type="year",
                    period=history_period,
                    frequency_type="daily",
                    frequency=1,
                    need_extended_hours_data=False,
                )
            )

            if not candles:
                print(
                    "Research hindsight market-data "
                    "warning: no history returned "
                    f"for {ticker}"
                )
                continue

            frame = pd.DataFrame(
                candles
            )

            if (
                frame.empty
                or "Datetime" not in frame.columns
                or "Close" not in frame.columns
            ):
                print(
                    "Research hindsight market-data "
                    "warning: invalid history returned "
                    f"for {ticker}"
                )
                continue

            frame["Date"] = pd.to_datetime(
                frame["Datetime"],
                unit="ms",
                utc=True,
            ).dt.tz_convert(
                "America/New_York"
            ).dt.tz_localize(
                None
            ).dt.normalize()

            frame = frame.set_index(
                "Date"
            )

            frame = frame[
                [
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume",
                ]
            ]

            for column in [
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]:
                frame[column] = pd.to_numeric(
                    frame[column],
                    errors="coerce",
                )

            frame = frame[
                (
                    frame.index
                    >= start_timestamp
                )
                & (
                    frame.index
                    < end_timestamp
                )
            ]

            if frame.empty:
                print(
                    "Research hindsight market-data "
                    "warning: no observations in "
                    f"requested range for {ticker}"
                )
                continue

            frames[ticker] = (
                frame.sort_index()
            )

        except Exception as error:

            print(
                "Research hindsight market-data "
                f"download failed for {ticker}: "
                f"{error}"
            )

    if not frames:
        return pd.DataFrame()

    return pd.concat(
        frames,
        axis=1,
    )


def _get_close_series(
    market_data: pd.DataFrame,
    ticker: str,
) -> pd.Series:
    if market_data.empty:
        return pd.Series(dtype="float64")

    try:
        if isinstance(
            market_data.columns,
            pd.MultiIndex,
        ):
            if ("Close", ticker) in market_data.columns:
                return (
                    market_data[("Close", ticker)]
                    .dropna()
                    .sort_index()
                )

            if (ticker, "Close") in market_data.columns:
                return (
                    market_data[(ticker, "Close")]
                    .dropna()
                    .sort_index()
                )

        if "Close" in market_data.columns:
            close_data = market_data["Close"]

            if isinstance(close_data, pd.DataFrame):
                if ticker in close_data.columns:
                    return (
                        close_data[ticker]
                        .dropna()
                        .sort_index()
                    )

            return close_data.dropna().sort_index()

    except (KeyError, TypeError):
        pass

    return pd.Series(dtype="float64")


def _slice_horizon(
    prices: pd.Series,
    recommendation_date: pd.Timestamp,
    evaluation_date: pd.Timestamp,
) -> pd.Series:
    if prices.empty:
        return prices

    date_values = prices.index.date

    return prices[
        (date_values >= recommendation_date.date())
        & (date_values <= evaluation_date.date())
    ]


def _calculate_raw_return(
    entry_price: float,
    exit_price: float,
) -> float | None:
    if entry_price <= 0:
        return None

    return (
        exit_price - entry_price
    ) / entry_price


def _calculate_directional_return(
    raw_return: float | None,
    direction: str | None,
) -> float | None:
    if raw_return is None or direction is None:
        return None

    if direction == "BEARISH":
        return -raw_return

    return raw_return


def _calculate_excursions(
    prices: pd.Series,
    entry_price: float,
    direction: str | None,
) -> tuple[float | None, float | None]:
    if (
        prices.empty
        or entry_price <= 0
        or direction is None
    ):
        return None, None

    raw_returns = (
        prices.astype(float) - entry_price
    ) / entry_price

    if direction == "BEARISH":
        directional_returns = -raw_returns
    else:
        directional_returns = raw_returns

    maximum_favorable_excursion = float(
        directional_returns.max()
    )

    maximum_adverse_excursion = float(
        directional_returns.min()
    )

    return (
        maximum_favorable_excursion,
        maximum_adverse_excursion,
    )


def _calculate_benchmark_return(
    spy_prices: pd.Series,
    recommendation_date: pd.Timestamp,
    evaluation_date: pd.Timestamp,
) -> float | None:
    horizon_prices = _slice_horizon(
        prices=spy_prices,
        recommendation_date=recommendation_date,
        evaluation_date=evaluation_date,
    )

    if len(horizon_prices) < MINIMUM_TRADING_DAYS:
        return None

    entry_price = float(horizon_prices.iloc[0])
    exit_price = float(horizon_prices.iloc[-1])

    return _calculate_raw_return(
        entry_price,
        exit_price,
    )


def _classify_thesis(
    directional_return: float | None,
) -> str:
    if directional_return is None:
        return "UNKNOWN"

    if directional_return > 0:
        return "CORRECT"

    if directional_return < 0:
        return "INCORRECT"

    return "FLAT"


def _classify_meaningful_outcome(
    directional_return: float | None,
    neutral_band: float = NEUTRAL_RETURN_BAND,
    meaningful_threshold: float = MEANINGFUL_RETURN_THRESHOLD,
) -> str:
    """Classify signal magnitude without replacing the legacy direction label."""
    if directional_return is None:
        return "UNKNOWN"
    if directional_return >= meaningful_threshold:
        return "MEANINGFUL_WIN"
    if directional_return <= -meaningful_threshold:
        return "MEANINGFUL_LOSS"
    if abs(directional_return) <= neutral_band:
        return "NOISE"
    return "SMALL_WIN" if directional_return > 0 else "SMALL_LOSS"


def _evaluate_fixed_horizon(
    ticker_prices: pd.Series,
    spy_prices: pd.Series,
    recommendation_date: pd.Timestamp,
    entry_price: float,
    direction: str,
    trading_days: int,
) -> dict:
    """Evaluate an exact number of completed trading sessions after entry."""
    available = ticker_prices[
        ticker_prices.index.date >= recommendation_date.date()
    ].dropna().sort_index()
    prefix = f"Horizon{trading_days}D"
    empty = {
        f"{prefix}Status": "IN_PROGRESS",
        f"{prefix}EvaluationDate": None,
        f"{prefix}UnderlyingReturnPct": None,
        f"{prefix}DirectionalReturnPct": None,
        f"{prefix}SPYReturnPct": None,
        f"{prefix}AlphaVsSPY": None,
        f"{prefix}MaxFavorableExcursionPct": None,
        f"{prefix}MaxAdverseExcursionPct": None,
        f"{prefix}ThesisResult": "UNKNOWN",
        f"{prefix}MagnitudeResult": "UNKNOWN",
        f"{prefix}FirstThresholdEvent": "NONE",
    }

    # Row zero is the entry session; row N is N completed sessions later.
    if len(available) <= trading_days:
        return empty

    horizon_prices = available.iloc[: trading_days + 1]
    exit_price = float(horizon_prices.iloc[-1])
    raw_return = _calculate_raw_return(entry_price, exit_price)
    directional_return = _calculate_directional_return(raw_return, direction)
    favorable, adverse = _calculate_excursions(
        horizon_prices, entry_price, direction
    )
    spy_horizon = spy_prices[
        spy_prices.index.date >= recommendation_date.date()
    ].dropna().sort_index().iloc[: trading_days + 1]
    spy_return = None
    if len(spy_horizon) > trading_days:
        spy_return = _calculate_raw_return(
            float(spy_horizon.iloc[0]), float(spy_horizon.iloc[-1])
        )
    alpha = (
        directional_return - spy_return
        if directional_return is not None and spy_return is not None
        else None
    )

    raw_path = (horizon_prices.astype(float) - entry_price) / entry_price
    directional_path = -raw_path if direction == "BEARISH" else raw_path
    first_event = "NONE"
    for value in directional_path.iloc[1:]:
        if value >= MEANINGFUL_RETURN_THRESHOLD:
            first_event = "FAVORABLE_FIRST"
            break
        if value <= -MEANINGFUL_RETURN_THRESHOLD:
            first_event = "ADVERSE_FIRST"
            break

    return {
        f"{prefix}Status": "COMPLETE",
        f"{prefix}EvaluationDate": horizon_prices.index[-1].date().isoformat(),
        f"{prefix}UnderlyingReturnPct": raw_return,
        f"{prefix}DirectionalReturnPct": directional_return,
        f"{prefix}SPYReturnPct": spy_return,
        f"{prefix}AlphaVsSPY": alpha,
        f"{prefix}MaxFavorableExcursionPct": favorable,
        f"{prefix}MaxAdverseExcursionPct": adverse,
        f"{prefix}ThesisResult": _classify_thesis(directional_return),
        f"{prefix}MagnitudeResult": _classify_meaningful_outcome(
            directional_return
        ),
        f"{prefix}FirstThresholdEvent": first_event,
    }


def _resolve_entry_price(
    row: pd.Series,
    prices: pd.Series,
) -> float | None:
    journal_entry_price = _safe_float(
        row.get("EntryUnderlyingPrice")
    )

    if journal_entry_price is not None:
        return journal_entry_price

    if prices.empty:
        return None

    return float(prices.iloc[0])


def _evaluate_recommendation(
    row: pd.Series,
    market_data: pd.DataFrame,
    spy_prices: pd.Series,
    as_of_date: pd.Timestamp,
) -> dict:
    recommendation_id = row.get(
        "RecommendationID"
    )

    ticker = str(
        row.get("ticker", "")
    ).strip()

    recommendation_date = _parse_datetime(
        row.get("RecommendationDate")
    )

    snapshot = _load_snapshot(
        row.get("SnapshotPath")
    )

    holding_period_days = _resolve_holding_period(
        row,
        snapshot,
    )

    direction = _determine_direction(row)

    result = {
        "RecommendationID": recommendation_id,
        "RecommendationDate": (
            recommendation_date.isoformat()
            if recommendation_date is not None
            else None
        ),
        "Ticker": ticker,
        "Action": row.get("action"),
        "OpportunityType": row.get(
            "opportunity_type"
        ),
        "OptionStrategy": row.get(
            "option_strategy"
        ),
        "Direction": direction,
        "Confidence": _safe_float(
            row.get("confidence")
        ),
        "ResearchScore": _safe_float(
            row.get("ResearchScore", row.get("research_score"))
        ),
        "TimeEdgeScore": _safe_float(
            row.get("time_edge_score")
        ),
        "TimeEdgeGrade": row.get("time_edge_grade"),
        "DirectionalConviction": _safe_float(
            row.get("DirectionalConviction", row.get("directional_conviction"))
        ),
        "BullishScore": _safe_float(
            row.get("BullishScore", row.get("bullish_score"))
        ),
        "BearishScore": _safe_float(
            row.get("BearishScore", row.get("bearish_score"))
        ),
        "InstitutionalTradeScore": _safe_float(
            row.get("InstitutionalTradeScore", row.get("institutional_trade_score"))
        ),
        "ExecutionScore": _safe_float(
            row.get("execution_score")
        ),
        "BrokerDelta": _safe_float(row.get("broker_delta")),
        "BrokerGamma": _safe_float(row.get("broker_gamma")),
        "BrokerTheta": _safe_float(row.get("broker_theta")),
        "BrokerVega": _safe_float(row.get("broker_vega")),
        "BrokerRho": _safe_float(row.get("broker_rho")),
        "ImpliedVolatility": _safe_float(row.get("implied_volatility")),
        "IVRank": _safe_float(row.get("iv_rank")),
        "IVPercentile": _safe_float(row.get("iv_percentile")),
        "EstimatedDelta": _safe_float(row.get("estimated_delta")),
        "EstimatedTheta": _safe_float(row.get("estimated_theta")),
        "ThetaDragPctPerDay": _safe_float(row.get("theta_drag_pct_per_day")),
        "GammaPerPremium": _safe_float(row.get("gamma_per_premium")),
        "VegaPerPremium": _safe_float(row.get("vega_per_premium")),
        "GreeksSource": row.get("greeks_source"),
        "IVContextStatus": row.get("iv_context_status"),
        "AllocationDecision": row.get("allocation_decision"),
        "AllocationRank": _safe_float(row.get("allocation_rank")),
        "MarketRegime": row.get("market_regime"),
        "EarningsDate": row.get("earnings_date"),
        "EarningsStatus": row.get("earnings_status"),
        "ContractOutcomeStatus": "UNAVAILABLE",
        "ContractOutcomeReason": (
            "Historical option quotes are not available; underlying outcomes "
            "must not be presented as option returns."
        ),
        "HoldingPeriodDays": holding_period_days,
        "RecommendationAgeDays": None,
        "EvaluationDate": None,
        "EvaluationStatus": "IN_PROGRESS",
        "EntryUnderlyingPrice": None,
        "CurrentUnderlyingPrice": None,
        "CurrentUnderlyingReturnPct": None,
        "CurrentDirectionalReturnPct": None,
        "CurrentSPYReturnPct": None,
        "CurrentAlphaVsSPY": None,
        "CurrentMaxFavorableExcursionPct": None,
        "CurrentMaxAdverseExcursionPct": None,
        "CurrentThesisResult": "UNKNOWN",
        "FinalUnderlyingPrice": None,
        "FinalUnderlyingReturnPct": None,
        "FinalDirectionalReturnPct": None,
        "FinalSPYReturnPct": None,
        "FinalAlphaVsSPY": None,
        "FinalMaxFavorableExcursionPct": None,
        "FinalMaxAdverseExcursionPct": None,
        "FinalThesisResult": "UNKNOWN",
        "SnapshotAvailable": bool(snapshot),
        "SnapshotPath": row.get("SnapshotPath"),
        "ProjectVersion": row.get(
            "ProjectVersion"
        ),
        "ConfigVersion": row.get(
            "ConfigVersion"
        ),
    }

    for fixed_horizon in FIXED_HORIZON_TRADING_DAYS:
        result.update({
            f"Horizon{fixed_horizon}DStatus": "NOT_EVALUATED",
            f"Horizon{fixed_horizon}DEvaluationDate": None,
            f"Horizon{fixed_horizon}DUnderlyingReturnPct": None,
            f"Horizon{fixed_horizon}DDirectionalReturnPct": None,
            f"Horizon{fixed_horizon}DSPYReturnPct": None,
            f"Horizon{fixed_horizon}DAlphaVsSPY": None,
            f"Horizon{fixed_horizon}DMaxFavorableExcursionPct": None,
            f"Horizon{fixed_horizon}DMaxAdverseExcursionPct": None,
            f"Horizon{fixed_horizon}DThesisResult": "UNKNOWN",
            f"Horizon{fixed_horizon}DMagnitudeResult": "UNKNOWN",
            f"Horizon{fixed_horizon}DFirstThresholdEvent": "NONE",
        })

    if not ticker or recommendation_date is None:
        result["EvaluationStatus"] = "INVALID_INPUT"
        return result

    recommendation_age_days = max(
        0,
        (
            as_of_date.date()
            - recommendation_date.date()
        ).days,
    )

    result["RecommendationAgeDays"] = (
        recommendation_age_days
    )

    evaluation_date = (
        recommendation_date
        + timedelta(days=holding_period_days)
    )

    result["EvaluationDate"] = (
        evaluation_date.isoformat()
    )

    if direction is None:
        result["EvaluationStatus"] = "NO_DIRECTION"
        return result

    ticker_prices = _get_close_series(
        market_data,
        ticker,
    )

    current_prices = _slice_horizon(
        prices=ticker_prices,
        recommendation_date=recommendation_date,
        evaluation_date=as_of_date,
    )

    if len(current_prices) < MINIMUM_TRADING_DAYS:
        result["EvaluationStatus"] = (
            "AWAITING_MARKET_DATA"
        )
        return result

    entry_price = _resolve_entry_price(
        row=row,
        prices=current_prices,
    )

    if entry_price is None or entry_price <= 0:
        result["EvaluationStatus"] = "INVALID_ENTRY_PRICE"
        return result

    current_price = float(
        current_prices.iloc[-1]
    )

    current_raw_return = _calculate_raw_return(
        entry_price,
        current_price,
    )

    current_directional_return = (
        _calculate_directional_return(
            current_raw_return,
            direction,
        )
    )

    current_spy_return = _calculate_benchmark_return(
        spy_prices=spy_prices,
        recommendation_date=recommendation_date,
        evaluation_date=as_of_date,
    )

    current_alpha_vs_spy = None

    if (
        current_directional_return is not None
        and current_spy_return is not None
    ):
        current_alpha_vs_spy = (
            current_directional_return
            - current_spy_return
        )

    (
        current_favorable_excursion,
        current_adverse_excursion,
    ) = _calculate_excursions(
        prices=current_prices,
        entry_price=entry_price,
        direction=direction,
    )

    result.update(
        {
            "EntryUnderlyingPrice": entry_price,
            "CurrentUnderlyingPrice": current_price,
            "CurrentUnderlyingReturnPct": current_raw_return,
            "CurrentDirectionalReturnPct": (
                current_directional_return
            ),
            "CurrentSPYReturnPct": current_spy_return,
            "CurrentAlphaVsSPY": current_alpha_vs_spy,
            "CurrentMaxFavorableExcursionPct": (
                current_favorable_excursion
            ),
            "CurrentMaxAdverseExcursionPct": (
                current_adverse_excursion
            ),
            "CurrentThesisResult": _classify_thesis(
                current_directional_return
            ),
        }
    )

    for fixed_horizon in FIXED_HORIZON_TRADING_DAYS:
        result.update(_evaluate_fixed_horizon(
            ticker_prices=ticker_prices,
            spy_prices=spy_prices,
            recommendation_date=recommendation_date,
            entry_price=entry_price,
            direction=direction,
            trading_days=fixed_horizon,
        ))

    matured = as_of_date >= evaluation_date

    if not matured:
        result["EvaluationStatus"] = "IN_PROGRESS"
        return result

    final_prices = _slice_horizon(
        prices=ticker_prices,
        recommendation_date=recommendation_date,
        evaluation_date=evaluation_date,
    )

    if len(final_prices) < MINIMUM_TRADING_DAYS:
        result["EvaluationStatus"] = (
            "MISSING_FINAL_MARKET_DATA"
        )
        return result

    final_price = float(
        final_prices.iloc[-1]
    )

    final_raw_return = _calculate_raw_return(
        entry_price,
        final_price,
    )

    final_directional_return = (
        _calculate_directional_return(
            final_raw_return,
            direction,
        )
    )

    final_spy_return = _calculate_benchmark_return(
        spy_prices=spy_prices,
        recommendation_date=recommendation_date,
        evaluation_date=evaluation_date,
    )

    final_alpha_vs_spy = None

    if (
        final_directional_return is not None
        and final_spy_return is not None
    ):
        final_alpha_vs_spy = (
            final_directional_return
            - final_spy_return
        )

    (
        final_favorable_excursion,
        final_adverse_excursion,
    ) = _calculate_excursions(
        prices=final_prices,
        entry_price=entry_price,
        direction=direction,
    )

    result.update(
        {
            "EvaluationStatus": "COMPLETE",
            "FinalUnderlyingPrice": final_price,
            "FinalUnderlyingReturnPct": final_raw_return,
            "FinalDirectionalReturnPct": (
                final_directional_return
            ),
            "FinalSPYReturnPct": final_spy_return,
            "FinalAlphaVsSPY": final_alpha_vs_spy,
            "FinalMaxFavorableExcursionPct": (
                final_favorable_excursion
            ),
            "FinalMaxAdverseExcursionPct": (
                final_adverse_excursion
            ),
            "FinalThesisResult": _classify_thesis(
                final_directional_return
            ),
        }
    )

    return result


def generate_research_hindsight() -> dict:
    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(
            f"Trade journal not found: {JOURNAL_PATH}"
        )

    journal = pd.read_csv(JOURNAL_PATH)

    if journal.empty:
        raise ValueError(
            "Trade journal is empty."
        )

    required_columns = [
        "RecommendationID",
        "RecommendationDate",
        "ticker",
        "action",
        "opportunity_type",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in journal.columns
    ]

    if missing_columns:
        raise ValueError(
            "Trade journal is missing required columns: "
            f"{missing_columns}"
        )

    journal = journal[
        journal["RecommendationID"].notna()
    ].copy()

    if journal.empty:
        raise ValueError(
            "No recommendations with RecommendationIDs found."
        )

    parsed_dates = journal[
        "RecommendationDate"
    ].apply(_parse_datetime)

    valid_dates = [
        value
        for value in parsed_dates
        if value is not None
    ]

    if not valid_dates:
        raise ValueError(
            "No valid recommendation dates found."
        )

    tickers = (
        journal["ticker"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    earliest_date = min(
        valid_dates
    ).date()

    as_of_date = pd.Timestamp(
        datetime.now()
    )

    market_data = _download_prices(
        tickers=tickers,
        start_date=earliest_date,
        end_date=(
            as_of_date.date()
            + timedelta(days=1)
        ),
    )

    if market_data.empty:
        raise RuntimeError(
            "Historical market data could not be downloaded."
        )

    spy_prices = _get_close_series(
        market_data,
        "SPY",
    )

    results = [
        _evaluate_recommendation(
            row=row,
            market_data=market_data,
            spy_prices=spy_prices,
            as_of_date=as_of_date,
        )
        for _, row in journal.iterrows()
    ]

    hindsight = pd.DataFrame(results)

    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        PROCESSED_DATA_DIR
        / f"research_hindsight_{timestamp}.csv"
    )

    hindsight.to_csv(
        output_path,
        index=False,
    )

    complete = int(
        (
            hindsight["EvaluationStatus"]
            == "COMPLETE"
        ).sum()
    )

    in_progress = int(
        (
            hindsight["EvaluationStatus"]
            == "IN_PROGRESS"
        ).sum()
    )

    no_direction = int(
        (
            hindsight["EvaluationStatus"]
            == "NO_DIRECTION"
        ).sum()
    )

    awaiting_market_data = int(
        hindsight["EvaluationStatus"].isin(
            [
                "AWAITING_MARKET_DATA",
                "MISSING_FINAL_MARKET_DATA",
            ]
        ).sum()
    )

    currently_correct = int(
        (
            hindsight["CurrentThesisResult"]
            == "CORRECT"
        ).sum()
    )

    currently_incorrect = int(
        (
            hindsight["CurrentThesisResult"]
            == "INCORRECT"
        ).sum()
    )

    final_correct = int(
        (
            hindsight["FinalThesisResult"]
            == "CORRECT"
        ).sum()
    )

    final_incorrect = int(
        (
            hindsight["FinalThesisResult"]
            == "INCORRECT"
        ).sum()
    )

    print("\n========================================")
    print("Project Stonks Research Monitor")
    print("========================================")
    print(f"Recommendations evaluated: {len(hindsight)}")
    print(f"In progress: {in_progress}")
    print(f"Complete: {complete}")
    print(f"No directional thesis: {no_direction}")
    print(f"Awaiting market data: {awaiting_market_data}")
    print(f"Currently correct: {currently_correct}")
    print(f"Currently incorrect: {currently_incorrect}")
    print(f"Final correct theses: {final_correct}")
    print(f"Final incorrect theses: {final_incorrect}")
    print(f"Output: {output_path}")

    return {
        "total": len(hindsight),
        "in_progress": in_progress,
        "complete": complete,
        "no_direction": no_direction,
        "awaiting_market_data": awaiting_market_data,
        "currently_correct": currently_correct,
        "currently_incorrect": currently_incorrect,
        "final_correct": final_correct,
        "final_incorrect": final_incorrect,
        "output_path": str(output_path),
    }


if __name__ == "__main__":
    generate_research_hindsight()
