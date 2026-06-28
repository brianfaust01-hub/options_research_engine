"""
Project Stonks
Data Loader
"""

import pandas as pd
import yfinance as yf


def get_sp500_tickers() -> list[str]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    tables = pd.read_html(url, storage_options=headers)

    sp500_table = tables[0]
    tickers = sp500_table["Symbol"].tolist()

    return [ticker.replace(".", "-") for ticker in tickers]


def download_price_data(
    tickers: list[str],
    period: str,
    interval: str
) -> pd.DataFrame:
    data = yf.download(
        tickers=tickers,
        period=period,
        interval=interval,
        auto_adjust=True,
        group_by="ticker",
        threads=True,
        progress=True
    )

    return data