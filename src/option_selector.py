"""
Project Stonks
Option Selector

Sprint 28A:
Production-ready Research Mode selector with horizon-aware contract ranking.

Clean by default.
Diagnostics can be enabled with DEBUG_OPTION_SELECTOR=True in config.py.
"""

import pandas as pd
import yfinance as yf

from config import (
    DEBUG_OPTION_SELECTOR,
    MAX_SINGLE_CONTRACT_COST_PCT,
    MIN_EXECUTABLE_CONTRACT_SCORE,
    PAPER_PORTFOLIO_VALUE,
)

from options_engine import (
    get_target_expirations,
    get_option_chain,
    score_contracts,
)


def _debug(message: str):
    if DEBUG_OPTION_SELECTOR:
        print(message)


def get_preferred_dte_range(expected_holding_days):
    """
    Converts expected holding period into preferred option DTE.

    The goal is not to hold to expiration.
    The goal is to give the thesis enough time to work while avoiding
    excessive theta acceleration.
    """

    if expected_holding_days is None:
        return (45, 75)

    try:
        expected_holding_days = int(expected_holding_days)
    except (TypeError, ValueError):
        return (45, 75)

    if expected_holding_days <= 21:
        return (30, 45)

    if expected_holding_days <= 45:
        return (45, 75)

    return (60, 120)


def _score_horizon_fit(dte, preferred_min_dte, preferred_max_dte):
    """
    Rewards contracts whose DTE matches the expected trade horizon.
    Penalizes contracts that are too short or too long for the thesis.
    """

    if preferred_min_dte <= dte <= preferred_max_dte:
        return 25

    if preferred_min_dte - 15 <= dte <= preferred_max_dte + 15:
        return 10

    return -20


def _is_contract_affordable(contract) -> bool:
    premium = float(contract["mid"])
    contract_cost = premium * 100

    max_single_contract_cost = (
        PAPER_PORTFOLIO_VALUE * MAX_SINGLE_CONTRACT_COST_PCT
    )

    return contract_cost <= max_single_contract_cost


def _get_stock_price(ticker: str):
    stock = yf.Ticker(ticker)
    history = stock.history(period="5d")

    if history.empty:
        return None

    return float(history["Close"].iloc[-1])


def _print_contract_sample(label: str, contracts):
    if not DEBUG_OPTION_SELECTOR:
        return

    print(f"\n{label}")
    print(f"Count: {len(contracts)}")

    if contracts.empty:
        return

    columns = [
        "contractSymbol",
        "strike",
        "Expiration",
        "DTE",
        "bid",
        "ask",
        "lastPrice",
        "mid",
        "spread_pct",
        "QuoteQuality",
        "Executable",
        "moneyness",
        "delta",
        "theta",
        "ContractScore",
        "HorizonFitScore",
        "FinalContractScore",
        "SelectionTier",
    ]

    available_columns = [
        column for column in columns
        if column in contracts.columns
    ]

    print(
        contracts[available_columns]
        .head(10)
        .to_string(index=False)
    )


def select_best_contract(
    ticker: str,
    opportunity_type: str,
    expected_holding_days=None,
):

    _debug(f"\n========== OPTION SELECTOR DEBUG: {ticker} ==========")

    stock_price = _get_stock_price(ticker)

    if stock_price is None:
        _debug("No stock price found.")
        return None

    _debug(f"Stock price: {stock_price:.2f}")

    option_type = "call"

    if "Put" in opportunity_type:
        option_type = "put"

    _debug(f"Option type: {option_type}")

    preferred_min_dte, preferred_max_dte = get_preferred_dte_range(
        expected_holding_days
    )

    _debug(f"Expected holding days: {expected_holding_days}")
    _debug(
        "Preferred DTE range: "
        f"{preferred_min_dte}-{preferred_max_dte}"
    )

    expirations = get_target_expirations(ticker)

    _debug(f"Expirations found: {len(expirations)}")
    _debug(f"Expirations: {expirations}")

    if len(expirations) == 0:
        _debug("No expirations found in configured DTE window.")
        return None

    all_ranked_contracts = []

    for expiration in expirations:
        try:
            _debug(f"\n----- {ticker} {expiration} -----")

            chain = get_option_chain(
                ticker=ticker,
                expiration=expiration,
                option_type=option_type,
            )

            _debug(f"Raw chain count: {len(chain)}")

            if chain.empty:
                _debug("No contracts returned from option chain.")
                continue

            ranked = score_contracts(
                chain=chain,
                stock_price=stock_price,
                option_type=option_type,
                expiration=expiration,
            )

            _debug(f"After score_contracts count: {len(ranked)}")

            if ranked.empty:
                _debug("All contracts removed inside score_contracts().")
                continue

            ranked = ranked.copy()

            ranked["Executable"] = ranked.apply(
                _is_contract_affordable,
                axis=1,
            )

            ranked["PreferredMinDTE"] = preferred_min_dte
            ranked["PreferredMaxDTE"] = preferred_max_dte

            ranked["HorizonFitScore"] = ranked["DTE"].apply(
                lambda dte: _score_horizon_fit(
                    dte=dte,
                    preferred_min_dte=preferred_min_dte,
                    preferred_max_dte=preferred_max_dte,
                )
            )

            ranked["FinalContractScore"] = (
                ranked["ContractScore"]
                + ranked["HorizonFitScore"]
            )

            _print_contract_sample(
                "Top contracts after scoring, before selector filter:",
                ranked,
            )

            filtered = ranked[
                (ranked["Executable"])
                &
                (
                    ranked["FinalContractScore"]
                    >= MIN_EXECUTABLE_CONTRACT_SCORE
                )
            ].copy()

            _debug(
                "Affordable + min final contract score count: "
                f"{len(filtered)}"
            )

            if filtered.empty:
                continue

            _print_contract_sample(
                "Contracts accepted by selector:",
                filtered,
            )

            all_ranked_contracts.append(filtered)

        except Exception as error:
            _debug(f"{ticker} {expiration}: selector error = {error}")
            continue

    if len(all_ranked_contracts) == 0:
        _debug("No executable contracts found after all selector filters.")
        return None

    executable_contracts = pd.concat(
        all_ranked_contracts,
        axis=0,
    )

    executable_contracts = executable_contracts.sort_values(
        [
            "FinalContractScore",
            "HorizonFitScore",
            "ContractScore",
            "DTE",
            "PremiumPctOfStock",
        ],
        ascending=[False, False, False, True, True],
    )

    _print_contract_sample(
        "Final selected contract universe:",
        executable_contracts,
    )

    selected = executable_contracts.iloc[0]

    _debug("\nSELECTED CONTRACT")
    _debug(f"Symbol: {selected['contractSymbol']}")
    _debug(f"Strike: {selected['strike']}")
    _debug(f"Expiration: {selected['Expiration']}")
    _debug(f"Premium: {selected['mid']}")
    _debug(f"Contract Score: {selected['ContractScore']}")
    _debug(f"Horizon Fit Score: {selected['HorizonFitScore']}")
    _debug(f"Final Contract Score: {selected['FinalContractScore']}")
    _debug(f"Quote Quality: {selected.get('QuoteQuality')}")
    _debug(f"Selection Tier: {selected.get('SelectionTier')}")
    _debug(f"Executable: {selected.get('Executable')}")

    return selected