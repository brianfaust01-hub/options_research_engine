"""
Project Stonks
Data Loader

Loads the S&P 500 universe and historical daily
price data.

Historical market data is sourced from the
Schwab Market Data API.
"""

from __future__ import annotations

import time

import pandas as pd

from schwab.market_data_client import (
    get_normalized_price_history,
)


def get_sp500_tickers() -> list[str]:
    """
    Retrieve the current S&P 500 ticker universe.

    Tickers remain in the canonical Project Stonks
    format. Provider-specific symbol translation
    happens only at the Schwab API boundary.
    """

    url = (
        "https://en.wikipedia.org/wiki/"
        "List_of_S%26P_500_companies"
    )

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    tables = pd.read_html(
        url,
        storage_options=headers,
    )

    sp500_table = tables[0]

    tickers = (
        sp500_table["Symbol"]
        .astype(str)
        .tolist()
    )

    #
    # Preserve the existing Project Stonks ticker
    # convention used throughout the codebase.
    #

    return [
        ticker.replace(".", "-")
        for ticker in tickers
    ]


def _to_schwab_symbol(
    ticker: str,
) -> str:
    """
    Convert a Project Stonks ticker into the symbol
    format expected by Schwab.

    Examples:

        BRK-B -> BRK/B
        BF-B  -> BF/B
        AAPL  -> AAPL
    """

    ticker = str(
        ticker
    ).upper().strip()

    return ticker.replace(
        "-",
        "/",
    )


def _validate_history_request(
    period: str,
    interval: str,
) -> None:
    """
    Validate the historical-data request supported
    by the current Project Stonks scan.

    The production weekly scan currently uses:

        period   = 1y
        interval = 1d

    Additional mappings can be added deliberately
    if the research system requires them later.
    """

    if period != "1y":
        raise ValueError(
            "Schwab historical loader currently "
            f"supports period='1y'. Received: {period}"
        )

    if interval != "1d":
        raise ValueError(
            "Schwab historical loader currently "
            f"supports interval='1d'. Received: {interval}"
        )


def _download_ticker_history(
    ticker: str,
) -> pd.DataFrame:
    """
    Retrieve one year of daily Schwab price history
    for one ticker.

    Returns a standard OHLCV DataFrame indexed by
    trading date.
    """

    schwab_symbol = (
        _to_schwab_symbol(
            ticker
        )
    )

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
        return pd.DataFrame()

    frame = pd.DataFrame(
        candles
    )

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Datetime",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in frame.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Schwab history for {ticker} is "
            "missing required columns: "
            f"{missing_columns}"
        )

    #
    # Schwab returns Unix timestamps in milliseconds.
    #
    # Convert them to normalized trading dates so
    # downstream indicator logic receives the same
    # kind of DatetimeIndex it previously received.
    #

    frame["Date"] = pd.to_datetime(
        frame["Datetime"],
        unit="ms",
        utc=True,
    ).dt.tz_convert(
        "America/New_York"
    ).dt.tz_localize(None).dt.normalize()

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

    frame = frame.sort_index()

    return frame


def download_price_data(
    tickers: list[str],
    period: str,
    interval: str,
) -> pd.DataFrame:
    """
    Download historical price data from Schwab.

    The returned DataFrame preserves the ticker-first
    MultiIndex interface previously provided by
    yfinance:

        data["AAPL"]
        data["NVDA"]

    each returns an OHLCV DataFrame.

    Individual ticker failures are isolated so one
    unavailable symbol cannot terminate the entire
    weekly scan.

    Requests are intentionally sequential during
    initial Schwab migration. Concurrency can be
    introduced after full-scan behavior and API
    limits are validated.
    """

    _validate_history_request(
        period=period,
        interval=interval,
    )

    ticker_frames: dict[
        str,
        pd.DataFrame,
    ] = {}

    total = len(
        tickers
    )

    for index, ticker in enumerate(
        tickers,
        start=1,
    ):

        ticker = str(
            ticker
        ).upper().strip()

        print(
            f"[historical_data] "
            f"{index}/{total} {ticker}"
        )

        try:

            frame = (
                _download_ticker_history(
                    ticker
                )
            )

            if frame.empty:

                print(
                    "[historical_data] WARNING: "
                    f"no history returned for {ticker}"
                )

                continue

            ticker_frames[
                ticker
            ] = frame

        except Exception as error:

            print(
                "[historical_data] WARNING: "
                f"failed to retrieve {ticker}: "
                f"{type(error).__name__}: {error}"
            )

            continue

        #
        # Tiny delay keeps the initial implementation
        # deliberately conservative while Schwab API
        # behavior is being validated.
        #

        time.sleep(
            0.05
        )

    if not ticker_frames:

        return pd.DataFrame()

    #
    # pd.concat with a dictionary produces:
    #
    #   Level 0 = ticker
    #   Level 1 = OHLCV field
    #
    # This preserves weekly_scan.py's existing:
    #
    #   data[ticker]
    #

    combined = pd.concat(
        ticker_frames,
        axis=1,
    )

    return combined