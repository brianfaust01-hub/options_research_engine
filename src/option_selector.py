"""
Project Stonks
Option Selector

Sprint 32D

Production-ready Research Mode selector with:
- Horizon-aware contract ranking
- Separate quote-executability and affordability fields
- Complete candidate-contract audit output

The audit is diagnostic only and does not change contract selection.
"""

from __future__ import annotations

from time import perf_counter

import pandas as pd

from schwab.market_data_client import (
    get_normalized_quote,
)

from config import (
    DEBUG_OPTION_SELECTOR,
    MAX_POSITION_SIZE_PCT,
    MIN_EXECUTABLE_CONTRACT_SCORE,
    PAPER_PORTFOLIO_VALUE,
)


from options_engine import (
    get_target_expirations,
    get_option_chain,
    get_option_chain_snapshot,
    score_contracts,
)
from pipeline_metrics import record_count, record_duration



def _debug(
    message: str,
) -> None:
    if DEBUG_OPTION_SELECTOR:
        print(message)



def get_preferred_dte_range(
    expected_holding_days,
):
    """
    Convert expected holding period into preferred option DTE.
    """

    if expected_holding_days is None:
        return (45, 75)

    try:
        expected_holding_days = int(
            expected_holding_days
        )
    except (TypeError, ValueError):
        return (45, 75)

    if expected_holding_days <= 21:
        return (30, 45)

    if expected_holding_days <= 45:
        return (45, 75)

    return (60, 120)


def _score_horizon_fit(
    dte,
    preferred_min_dte,
    preferred_max_dte,
):
    if (
        preferred_min_dte
        <= dte
        <= preferred_max_dte
    ):
        return 25

    if (
        preferred_min_dte - 15
        <= dte
        <= preferred_max_dte + 15
    ):
        return 10

    return -20


def _is_contract_affordable(
    contract,
) -> bool:
    """
    Determines whether a single option contract fits within the
    configured maximum portfolio allocation.

    This is intentionally separate from quote executability.

    QuoteExecutable answers:

        "Can this option reasonably be traded?"

    Affordable answers:

        "Does this option fit within our current portfolio risk budget?"
    """

    try:
        premium = float(
            contract["mid"]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return False

    if premium <= 0:
        return False

    contract_cost = premium * 100

    max_position_value = (
        PAPER_PORTFOLIO_VALUE
        * MAX_POSITION_SIZE_PCT
    )

    return (
        contract_cost
        <= max_position_value
    )


def _get_stock_price(
    ticker: str,
):
    """
    Retrieve the current underlying price from
    Schwab Market Data.

    Pricing preference:

    1. Mark
    2. Last
    3. Bid/ask midpoint

    Returns None when no usable price is available.
    """

    try:

        quote = get_normalized_quote(
            ticker
        )

        mark = pd.to_numeric(
            quote.get("Mark"),
            errors="coerce",
        )

        if (
            pd.notna(mark)
            and float(mark) > 0
        ):
            return float(mark)

        last_price = pd.to_numeric(
            quote.get("Last"),
            errors="coerce",
        )

        if (
            pd.notna(last_price)
            and float(last_price) > 0
        ):
            return float(last_price)

        bid = pd.to_numeric(
            quote.get("Bid"),
            errors="coerce",
        )

        ask = pd.to_numeric(
            quote.get("Ask"),
            errors="coerce",
        )

        if (
            pd.notna(bid)
            and pd.notna(ask)
            and float(bid) > 0
            and float(ask) > 0
        ):
            return (
                float(bid)
                + float(ask)
            ) / 2

        return None

    except Exception as error:

        _debug(
            f"Failed to retrieve Schwab stock price "
            f"for {ticker}: {error}"
        )

        return None
   


def _build_rejection_reason(
    row: pd.Series,
) -> str:
    reasons = []

    if not bool(
        row.get(
            "QuoteExecutable",
            False,
        )
    ):
        reasons.append(
            "INVALID_QUOTE"
        )

    if not bool(
        row.get(
            "Affordable",
            False,
        )
    ):
        reasons.append(
            "ABOVE_CONTRACT_BUDGET"
        )

    final_score = pd.to_numeric(
        row.get(
            "FinalContractScore"
        ),
        errors="coerce",
    )

    if (
        pd.isna(final_score)
        or final_score
        < MIN_EXECUTABLE_CONTRACT_SCORE
    ):
        reasons.append(
            "BELOW_MIN_FINAL_SCORE"
        )

    if not reasons:
        return "LOWER_RANKED_ELIGIBLE_CONTRACT"

    return ";".join(
        reasons
    )


def _print_contract_sample(
    label: str,
    contracts: pd.DataFrame,
) -> None:
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
        "SpreadDollars",
        "spread_pct",
        "QuoteQuality",
        "QuoteExecutable",
        "Affordable",
        "SelectorEligible",
        "moneyness",
        "delta",
        "theta",
        "openInterest",
        "volume",
        "ContractScore",
        "HorizonFitScore",
        "FinalContractScore",
        "ExecutionScore",
        "ExecutionGrade",
        "SelectionTier",
    ]

    available_columns = [
        column
        for column in columns
        if column in contracts.columns
    ]

    print(
        contracts[
            available_columns
        ]
        .head(10)
        .to_string(
            index=False
        )
    )


def _select_best_contract(
    ticker: str,
    opportunity_type: str,
    expected_holding_days=None,
):
    ticker = str(
        ticker
    ).upper().strip()

    _debug(
        f"\n========== OPTION SELECTOR DEBUG: "
        f"{ticker} =========="
    )

    record_count("equity_quote_requests")
    stock_price = _get_stock_price(
        ticker
    )

    if stock_price is None:
        _debug(
            "No stock price found."
        )
        return None

    _debug(
        f"Stock price: "
        f"{stock_price:.2f}"
    )

    option_type = (
        "put"
        if "Put" in opportunity_type
        else "call"
    )

    preferred_min_dte, preferred_max_dte = (
        get_preferred_dte_range(
            expected_holding_days
        )
    )

    try:
        normalized_contracts = get_option_chain_snapshot(
            ticker=ticker,
            option_type=option_type.upper(),
        )
    except Exception as error:
        _debug(
            f"Failed to retrieve option-chain snapshot "
            f"for {ticker}: {error}"
        )
        return None

    expirations = get_target_expirations(
        ticker,
        normalized_contracts=normalized_contracts,
    )

    if not expirations:
        _debug(
            "No expirations found in configured "
            "DTE window."
        )
        return None

    all_candidate_contracts = []
    all_eligible_contracts = []

    for expiration in expirations:
        try:
            chain = get_option_chain(
                ticker=ticker,
                expiration=expiration,
                option_type=option_type,
                normalized_contracts=normalized_contracts,
            )
            
            if chain.empty:
                continue

            ranked = score_contracts(
                chain=chain,
                stock_price=stock_price,
                option_type=option_type,
                expiration=expiration,
            )

            if ranked.empty:
                continue

            ranked = ranked.copy()

            # Preserve the quote-level executable status produced
            # by options_engine.py.
            ranked["QuoteExecutable"] = (
                ranked["Executable"]
                .fillna(False)
                .astype(bool)
            )

            # Account-size affordability is a separate concept.
            ranked["Affordable"] = (
                ranked.apply(
                    _is_contract_affordable,
                    axis=1,
                )
            )

            ranked["PreferredMinDTE"] = (
                preferred_min_dte
            )

            ranked["PreferredMaxDTE"] = (
                preferred_max_dte
            )

            ranked["HorizonFitScore"] = (
                ranked["DTE"].apply(
                    lambda dte: _score_horizon_fit(
                        dte=dte,
                        preferred_min_dte=(
                            preferred_min_dte
                        ),
                        preferred_max_dte=(
                            preferred_max_dte
                        ),
                    )
                )
            )

            ranked["FinalContractScore"] = (
                ranked["ContractScore"]
                + ranked["HorizonFitScore"]
            )

            ranked["SelectorEligible"] = (
                ranked["QuoteExecutable"]
                & ranked["Affordable"]
                & (
                    ranked[
                        "FinalContractScore"
                    ]
                    >= MIN_EXECUTABLE_CONTRACT_SCORE
                )
            )

            ranked["RejectionReason"] = (
                ranked.apply(
                    _build_rejection_reason,
                    axis=1,
                )
            )

            all_candidate_contracts.append(
                ranked
            )

            eligible = ranked[
                ranked["SelectorEligible"]
            ].copy()

            if not eligible.empty:
                all_eligible_contracts.append(
                    eligible
                )

        except Exception as error:
            _debug(
                f"{ticker} {expiration}: "
                f"selector error = {error}"
            )
            continue

    if not all_candidate_contracts:
        _debug(
            "No scored contracts found."
        )
        return None

    candidate_universe = pd.concat(
        all_candidate_contracts,
        axis=0,
        ignore_index=True,
    )

    if not all_eligible_contracts:
        _debug(
            "No executable contracts found after "
            "all selector filters."
        )
        return None

    executable_contracts = pd.concat(
        all_eligible_contracts,
        axis=0,
        ignore_index=True,
    )

    executable_contracts = (
        executable_contracts.sort_values(
            [
                "FinalContractScore",
                "HorizonFitScore",
                "ContractScore",
                "DTE",
                "PremiumPctOfStock",
            ],
            ascending=[
                False,
                False,
                False,
                True,
                True,
            ],
            na_position="last",
        )
    )

    selected = (
        executable_contracts.iloc[0]
    )

    selected_symbol = str(
        selected["contractSymbol"]
    )

    candidate_universe.loc[
        candidate_universe[
            "contractSymbol"
        ].astype(str) == selected_symbol,
        "RejectionReason",
    ] = "SELECTED"

    

    _print_contract_sample(
        "Final selected contract universe:",
        executable_contracts,
    )

    return selected


def select_best_contract(
    ticker: str,
    opportunity_type: str,
    expected_holding_days=None,
):
    """Select a contract and record non-persistent runtime diagnostics."""

    started = perf_counter()
    record_count("contract_selection_candidates")

    try:
        return _select_best_contract(
            ticker=ticker,
            opportunity_type=opportunity_type,
            expected_holding_days=expected_holding_days,
        )
    finally:
        record_duration(
            "contract_selection",
            perf_counter() - started,
        )
