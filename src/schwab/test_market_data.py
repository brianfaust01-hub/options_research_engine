"""
Project Stonks
Schwab Market Data Smoke Test

Tests read-only Schwab Market Data access.

Current validation target:
IFF stock quote and option chain.

This script does not place, modify, or cancel orders.
"""

import json
from pathlib import Path

import requests


PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
)

TOKEN_PATH = (
    PROJECT_ROOT
    / "data"
    / "schwab_market_tokens.json"
)

BASE_URL = (
    "https://api.schwabapi.com/marketdata/v1"
)


def load_access_token():
    """
    Load the currently persisted Market Data
    access token.
    """

    if not TOKEN_PATH.exists():
        raise RuntimeError(
            "Market Data token file not found. "
            "Run market_auth.py first."
        )

    with TOKEN_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        token_data = json.load(file)

    access_token = token_data.get(
        "access_token"
    )

    if not access_token:
        raise RuntimeError(
            "Market Data token file does not "
            "contain an access token."
        )

    return access_token


def build_headers():
    """
    Build authenticated Market Data headers.
    """

    return {
        "Authorization": (
            f"Bearer {load_access_token()}"
        ),
        "Accept": "application/json",
    }


def get_quote(
    ticker: str,
):
    """
    Retrieve a stock quote from Schwab.
    """

    url = (
        f"{BASE_URL}/{ticker}/quotes"
    )

    response = requests.get(
        url,
        headers=build_headers(),
        timeout=30,
    )

    if not response.ok:

        print(
            f"Quote request failed: "
            f"HTTP {response.status_code}"
        )

        print(
            response.text
        )

        response.raise_for_status()

    return response.json()


def get_option_chain(
    ticker: str,
):
    """
    Retrieve an option chain from Schwab.

    Initial test intentionally requests the chain
    broadly so we can inspect Schwab's response
    structure before adding production filters.
    """

    url = (
        f"{BASE_URL}/chains"
    )

    params = {
        "symbol": ticker,
        "contractType": "CALL",
        "includeUnderlyingQuote": "true",
        "strategy": "SINGLE",
    }

    response = requests.get(
        url,
        headers=build_headers(),
        params=params,
        timeout=30,
    )

    if not response.ok:

        print(
            f"Option-chain request failed: "
            f"HTTP {response.status_code}"
        )

        print(
            response.text
        )

        response.raise_for_status()

    return response.json()


def print_iff_target_contract(
    chain: dict,
):
    """
    Search the Schwab option chain for the
    September 18, 2026 $55 IFF call.

    This is the contract currently showing the
    suspicious premium in Project Stonks.
    """

    target_date = "2026-09-18"
    target_strike = 55.0

    call_map = chain.get(
        "callExpDateMap",
        {}
    )

    found = False

    for expiration_key, strikes in (
        call_map.items()
    ):

        expiration_date = (
            expiration_key.split(":")[0]
        )

        if expiration_date != target_date:
            continue

        for strike_key, contracts in (
            strikes.items()
        ):

            try:
                strike = float(
                    strike_key
                )

            except ValueError:
                continue

            if strike != target_strike:
                continue

            for contract in contracts:

                found = True

                print(
                    "\nIFF TARGET CONTRACT"
                )

                print(
                    "------------------------------"
                )

                print(
                    f"Symbol: "
                    f"{contract.get('symbol')}"
                )

                print(
                    f"Description: "
                    f"{contract.get('description')}"
                )

                print(
                    f"Bid: "
                    f"{contract.get('bid')}"
                )

                print(
                    f"Ask: "
                    f"{contract.get('ask')}"
                )

                print(
                    f"Last: "
                    f"{contract.get('last')}"
                )

                print(
                    f"Mark: "
                    f"{contract.get('mark')}"
                )

                print(
                    f"Close: "
                    f"{contract.get('closePrice')}"
                )

                print(
                    f"Volume: "
                    f"{contract.get('totalVolume')}"
                )

                print(
                    f"Open Interest: "
                    f"{contract.get('openInterest')}"
                )

                print(
                    f"Delta: "
                    f"{contract.get('delta')}"
                )

                print(
                    f"Gamma: "
                    f"{contract.get('gamma')}"
                )

                print(
                    f"Theta: "
                    f"{contract.get('theta')}"
                )

                print(
                    f"Vega: "
                    f"{contract.get('vega')}"
                )

                print(
                    f"IV: "
                    f"{contract.get('volatility')}"
                )

                print(
                    f"In The Money: "
                    f"{contract.get('inTheMoney')}"
                )

    if not found:

        print(
            "\nIFF September 18, 2026 "
            "$55 call was not found "
            "in the returned chain."
        )


if __name__ == "__main__":

    ticker = "IFF"

    print(
        "\nSchwab Market Data Test\n"
    )

    print(
        "Requesting IFF quote..."
    )

    quote = get_quote(
        ticker
    )

    print(
        "IFF quote received successfully."
    )

    quote_data = quote.get(
        ticker,
        {}
    )

    underlying_quote = (
        quote_data.get(
            "quote",
            {}
        )
    )

    print(
        f"IFF Last: "
        f"{underlying_quote.get('lastPrice')}"
    )

    print(
        f"IFF Bid: "
        f"{underlying_quote.get('bidPrice')}"
    )

    print(
        f"IFF Ask: "
        f"{underlying_quote.get('askPrice')}"
    )

    print(
        "\nRequesting IFF option chain..."
    )

    chain = get_option_chain(
        ticker
    )

    print(
        "IFF option chain received successfully."
    )

    print_iff_target_contract(
        chain
    )