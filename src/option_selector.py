"""
Project Stonks
Option Selector

Chooses the best executable option contract for a trade recommendation.
"""

import pandas as pd
import yfinance as yf

from config import (
    PAPER_PORTFOLIO_VALUE,
    MAX_SINGLE_CONTRACT_COST_PCT,
)

from options_engine import (
    get_target_expirations,
    get_option_chain,
    score_contracts,
)


def _is_contract_executable(contract) -> bool:
    premium = float(contract["mid"])
    contract_cost = premium * 100

    max_single_contract_cost = (
        PAPER_PORTFOLIO_VALUE * MAX_SINGLE_CONTRACT_COST_PCT
    )

    return contract_cost <= max_single_contract_cost


def select_best_contract(ticker: str, opportunity_type: str):

    stock = yf.Ticker(ticker)
    stock_price = stock.history(period="1d")["Close"].iloc[-1]

    option_type = "call"

    if "Put" in opportunity_type:
        option_type = "put"

    expirations = get_target_expirations(ticker)

    if len(expirations) == 0:
        return None

    all_ranked_contracts = []

    for expiration in expirations:
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
            continue

        ranked = ranked.copy()
        ranked["Executable"] = ranked.apply(
            _is_contract_executable,
            axis=1,
        )

        ranked = ranked[ranked["Executable"]].copy()

        if ranked.empty:
            continue

        all_ranked_contracts.append(ranked)

    if len(all_ranked_contracts) == 0:
        return None

    executable_contracts = pd.concat(
        all_ranked_contracts,
        axis=0,
    )

    executable_contracts = executable_contracts.sort_values(
        ["ContractScore", "DTE", "spread_pct"],
        ascending=[False, True, True],
    )

    return executable_contracts.iloc[0]