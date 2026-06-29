"""
Project Stonks
Option Selector

Chooses the best option contract for a trade recommendation.
"""

import yfinance as yf

from options_engine import (
    get_target_expirations,
    get_option_chain,
    score_contracts,
)


def select_best_contract(ticker: str, opportunity_type: str):

    stock = yf.Ticker(ticker)
    stock_price = stock.history(period="1d")["Close"].iloc[-1]

    option_type = "call"

    if "Put" in opportunity_type:
        option_type = "put"

    expirations = get_target_expirations(ticker)

    if len(expirations) == 0:
        return None

    expiration = expirations[0]

    chain = get_option_chain(
        ticker=ticker,
        expiration=expiration,
        option_type=option_type,
    )

    ranked = score_contracts(
        chain=chain,
        stock_price=stock_price,
        option_type=option_type,
        expiration=expiration,
    )

    if ranked.empty:
        return None

    return ranked.iloc[0]