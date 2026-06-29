"""
Project Stonks
Options Engine
"""

from datetime import datetime

import yfinance as yf


def get_option_expirations(ticker: str) -> list[str]:
    stock = yf.Ticker(ticker)
    return list(stock.options)


def get_target_expirations(ticker: str, min_dte: int = 30, max_dte: int = 75) -> list[str]:
    today = datetime.today().date()
    expirations = get_option_expirations(ticker)

    results = []

    for expiration in expirations:
        expiration_date = datetime.strptime(expiration, "%Y-%m-%d").date()
        dte = (expiration_date - today).days

        if min_dte <= dte <= max_dte:
            results.append(expiration)

    return results


def get_option_chain(ticker: str, expiration: str, option_type: str):
    stock = yf.Ticker(ticker)
    chain = stock.option_chain(expiration)

    if option_type.lower() == "call":
        return chain.calls

    if option_type.lower() == "put":
        return chain.puts

    raise ValueError("option_type must be 'call' or 'put'")


def score_contracts(chain, stock_price: float, option_type: str):
    contracts = chain.copy()

    contracts["mid"] = (contracts["bid"] + contracts["ask"]) / 2
    contracts["spread_pct"] = (contracts["ask"] - contracts["bid"]) / contracts["mid"]

    if option_type.lower() == "call":
        contracts["moneyness"] = contracts["strike"] / stock_price
        contracts = contracts[
            (contracts["moneyness"] >= 0.95)
            & (contracts["moneyness"] <= 1.10)
        ]

    elif option_type.lower() == "put":
        contracts["moneyness"] = stock_price / contracts["strike"]
        contracts = contracts[
            (contracts["moneyness"] >= 0.95)
            & (contracts["moneyness"] <= 1.10)
        ]

    contracts = contracts[
        (contracts["bid"] > 0)
        & (contracts["ask"] > 0)
        & (contracts["mid"] > 0)
        & (contracts["spread_pct"] <= 0.25)
        & (contracts["openInterest"] >= 100)
    ]

    contracts["ContractScore"] = 0

    contracts.loc[contracts["openInterest"] >= 500, "ContractScore"] += 25
    contracts.loc[contracts["volume"] >= 100, "ContractScore"] += 25
    contracts.loc[contracts["spread_pct"] <= 0.10, "ContractScore"] += 25
    contracts.loc[
        (contracts["moneyness"] >= 0.98)
        & (contracts["moneyness"] <= 1.05),
        "ContractScore",
    ] += 25

    return contracts.sort_values("ContractScore", ascending=False)