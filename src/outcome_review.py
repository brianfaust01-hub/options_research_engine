"""
Project Stonks
Outcome Review Engine

Sprint 30B:
Reviews actual paper portfolio positions rather than recommendation-journal
rows.

The research journal remains untouched. Mutable position state is written only
to data/paper_portfolio.csv.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from paper_portfolio import (
    get_open_positions,
    load_portfolio,
    save_portfolio,
)
from schwab.market_data_client import (
    get_normalized_price_history,
)

from paper_portfolio import get_open_positions, load_portfolio, save_portfolio


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"


def _prepare_portfolio_columns(portfolio: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure review fields exist and support text/date assignments.
    """

    default_columns = {
        "CurrentUnderlying": None,
        "CurrentPremium": None,
        "CurrentDTE": None,
        "UnderlyingReturnPct": None,
        "SPYReturnPct": None,
        "PnLPct": None,
        "AlphaVsSPY": None,
        "LastReviewed": None,
        "ExitDate": None,
        "ExitReason": None,
        "ExitPremium": None,
    }

    for column, default_value in default_columns.items():
        if column not in portfolio.columns:
            portfolio[column] = default_value

    string_columns = [
        "Status",
        "LastReviewed",
        "ExitDate",
        "ExitReason",
    ]

    for column in string_columns:
        if column in portfolio.columns:
            portfolio[column] = portfolio[column].astype("object")

    return portfolio


def _download_market_data(
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

    frames = {}

    start_timestamp = pd.Timestamp(
        start_date
    )

    end_timestamp = pd.Timestamp(
        end_date
    )

    for ticker in symbols:

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
                    period=1,
                    frequency_type="daily",
                    frequency=1,
                    need_extended_hours_data=False,
                )
            )

            if not candles:
                print(
                    "Outcome market-data warning: "
                    f"no history returned for {ticker}"
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
                    "Outcome market-data warning: "
                    f"invalid history returned for {ticker}"
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
                    "Outcome market-data warning: "
                    "no observations in requested "
                    f"range for {ticker}"
                )
                continue

            frames[ticker] = (
                frame.sort_index()
            )

        except Exception as error:

            print(
                "Outcome market-data download "
                f"failed for {ticker}: {error}"
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
    """
    Extract a ticker's closing-price series from either single-level or
    MultiIndex historical-price output.
    """

    if market_data.empty:
        return pd.Series(dtype="float64")

    try:
        if isinstance(market_data.columns, pd.MultiIndex):
            if ("Close", ticker) in market_data.columns:
                return market_data[("Close", ticker)].dropna()

            if (ticker, "Close") in market_data.columns:
                return market_data[(ticker, "Close")].dropna()

        if "Close" in market_data.columns:
            close_data = market_data["Close"]

            if isinstance(close_data, pd.DataFrame):
                if ticker in close_data.columns:
                    return close_data[ticker].dropna()
            else:
                return close_data.dropna()

    except (KeyError, TypeError):
        return pd.Series(dtype="float64")

    return pd.Series(dtype="float64")


def _parse_entry_date(value):
    if value is None or pd.isna(value):
        return None

    parsed = pd.to_datetime(value, errors="coerce")

    if pd.isna(parsed):
        return None

    return parsed


def _calculate_current_dte(expiration):
    if expiration is None or pd.isna(expiration):
        return None

    expiration_date = pd.to_datetime(
        expiration,
        errors="coerce",
    )

    if pd.isna(expiration_date):
        return None

    return (expiration_date.date() - datetime.now().date()).days


def _calculate_directional_return(
    option_strategy,
    entry_underlying,
    current_underlying,
):
    if entry_underlying is None or pd.isna(entry_underlying):
        return None

    entry_underlying = float(entry_underlying)

    if entry_underlying <= 0:
        return None

    raw_return = (
        float(current_underlying) - entry_underlying
    ) / entry_underlying

    if option_strategy == "Long Put":
        return -raw_return

    return raw_return


def _calculate_period_return(
    prices: pd.Series,
    entry_date,
):
    if prices.empty or entry_date is None:
        return None

    eligible_prices = prices[
        prices.index.date >= entry_date.date()
    ]

    if len(eligible_prices) < 2:
        return None

    start_price = float(eligible_prices.iloc[0])
    end_price = float(eligible_prices.iloc[-1])

    if start_price <= 0:
        return None

    return (end_price - start_price) / start_price


def _build_position_review(
    portfolio: pd.DataFrame,
) -> pd.DataFrame:
    review_columns = [
        "PositionID",
        "RecommendationID",
        "Ticker",
        "OptionStrategy",
        "Expiration",
        "Strike",
        "Contracts",
        "EntryPremium",
        "CurrentPremium",
        "CurrentUnderlying",
        "CurrentDTE",
        "UnderlyingReturnPct",
        "SPYReturnPct",
        "PnLPct",
        "AlphaVsSPY",
        "Status",
        "LastReviewed",
    ]

    existing_columns = [
        column
        for column in review_columns
        if column in portfolio.columns
    ]

    return portfolio[existing_columns].copy()


def _write_position_review(
    portfolio: pd.DataFrame,
) -> Path:
    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_path = (
        PROCESSED_DATA_DIR
        / f"position_review_{timestamp}.csv"
    )

    review = _build_position_review(portfolio)
    review.to_csv(output_path, index=False)

    return output_path


def review_open_trades():
    """
    Review every open row in paper_portfolio.csv.

    Current underlying prices and directional benchmark results are updated.
    Option P/L remains blank unless CurrentPremium has been populated through
    broker reconciliation or another trusted option-pricing source.
    """

    portfolio = load_portfolio()
    portfolio = _prepare_portfolio_columns(portfolio)

    open_positions = get_open_positions()

    if open_positions.empty:
        review_path = _write_position_review(portfolio)

        return {
            "reviewed": 0,
            "closed": 0,
            "review_path": str(review_path),
            "message": "No open paper positions to review.",
        }

    tickers = (
        open_positions["Ticker"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    parsed_entry_dates = open_positions["EntryDate"].apply(
        _parse_entry_date
    )

    valid_entry_dates = [
        value
        for value in parsed_entry_dates
        if value is not None
    ]

    if valid_entry_dates:
        start_date = min(valid_entry_dates).date()
    else:
        start_date = datetime.now().date() - timedelta(days=10)

    end_date = datetime.now().date() + timedelta(days=1)

    market_data = _download_market_data(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
    )

    if market_data.empty:
        review_path = _write_position_review(portfolio)

        return {
            "reviewed": 0,
            "closed": 0,
            "review_path": str(review_path),
            "message": (
                "Open paper positions found, but market data "
                "could not be downloaded."
            ),
        }

    spy_prices = _get_close_series(
        market_data,
        "SPY",
    )

    reviewed = 0
    current_timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    open_mask = portfolio["Status"] == "OPEN"

    for index, position in portfolio[open_mask].iterrows():
        ticker = str(position["Ticker"])

        ticker_prices = _get_close_series(
            market_data,
            ticker,
        )

        if ticker_prices.empty:
            continue

        current_underlying = float(
            ticker_prices.iloc[-1]
        )

        entry_date = _parse_entry_date(
            position.get("EntryDate")
        )

        entry_underlying = position.get(
            "EntryUnderlying"
        )

        directional_return = _calculate_directional_return(
            option_strategy=position.get("OptionStrategy"),
            entry_underlying=entry_underlying,
            current_underlying=current_underlying,
        )

        spy_return = _calculate_period_return(
            prices=spy_prices,
            entry_date=entry_date,
        )

        alpha_vs_spy = None

        if (
            directional_return is not None
            and spy_return is not None
        ):
            alpha_vs_spy = directional_return - spy_return

        current_premium = position.get(
            "CurrentPremium"
        )

        entry_premium = position.get(
            "EntryPremium"
        )

        option_pnl_pct = None

        if (
            current_premium is not None
            and not pd.isna(current_premium)
            and entry_premium is not None
            and not pd.isna(entry_premium)
            and float(entry_premium) > 0
        ):
            option_pnl_pct = (
                float(current_premium)
                - float(entry_premium)
            ) / float(entry_premium)

        portfolio.loc[
            index,
            "CurrentUnderlying",
        ] = current_underlying

        portfolio.loc[
            index,
            "CurrentDTE",
        ] = _calculate_current_dte(
            position.get("Expiration")
        )

        portfolio.loc[
            index,
            "UnderlyingReturnPct",
        ] = directional_return

        portfolio.loc[
            index,
            "SPYReturnPct",
        ] = spy_return

        portfolio.loc[
            index,
            "PnLPct",
        ] = option_pnl_pct

        portfolio.loc[
            index,
            "AlphaVsSPY",
        ] = alpha_vs_spy

        portfolio.loc[
            index,
            "LastReviewed",
        ] = current_timestamp

        reviewed += 1

    save_portfolio(portfolio)

    review_path = _write_position_review(
        portfolio,
    )

    return {
        "reviewed": reviewed,
        "closed": 0,
        "review_path": str(review_path),
        "message": (
            f"Reviewed {reviewed} open paper positions; "
            f"position review saved to {review_path}."
        ),
    }