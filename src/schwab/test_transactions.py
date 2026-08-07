"""
Project Stonks
Schwab Accounts & Trading - PaperMoney Probe

Read-only diagnostic.

Purpose:
- Retrieve linked Schwab accounts
- Retrieve recent orders from the exposed account
- Search those orders for known paperMoney tickers
- Determine whether paperMoney activity may be exposed
  through the production Accounts & Trading API

This file does NOT place, modify, or cancel orders.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import requests

from token_manager import get_access_token


BASE_URL = "https://api.schwabapi.com/trader/v1"

PAPER_TICKERS = {
    "A",
    "IR",
    "NVDA",
    "PCG",
    "TFC",
    "TSN",
}


def _headers():
    """
    Build authenticated Trader API headers.
    """

    return {
        "Authorization": (
            f"Bearer {get_access_token()}"
        ),
        "Accept": "application/json",
    }


def get_linked_accounts():
    """
    Retrieve accounts authorized through OAuth.
    """

    response = requests.get(
        f"{BASE_URL}/accounts/accountNumbers",
        headers=_headers(),
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def get_recent_orders(
    account_hash: str,
):
    """
    Retrieve recent orders for one Schwab account.

    Uses a 60-day window to give us plenty of room
    to detect the known paperMoney activity.
    """

    now = datetime.now(
        timezone.utc
    )

    start = (
        now
        - timedelta(days=60)
    )

    params = {
        "fromEnteredTime": (
            start.strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            )
        ),
        "toEnteredTime": (
            now.strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            )
        ),
        "maxResults": 3000,
    }

    response = requests.get(
        (
            f"{BASE_URL}/accounts/"
            f"{account_hash}/orders"
        ),
        headers=_headers(),
        params=params,
        timeout=30,
    )

    if not response.ok:

        print(
            "Schwab order-history error: "
            f"HTTP {response.status_code}"
        )

        print(
            response.text
        )

        response.raise_for_status()

    return response.json()


def extract_symbols(
    order: dict,
):
    """
    Extract instrument symbols from an order.
    """

    symbols = []

    legs = order.get(
        "orderLegCollection",
        [],
    )

    for leg in legs:

        instrument = leg.get(
            "instrument",
            {},
        )

        symbol = instrument.get(
            "symbol"
        )

        if symbol:

            symbols.append(
                symbol
            )

    return symbols


def underlying_from_symbol(
    symbol: str,
):
    """
    Extract an underlying ticker from either
    an equity symbol or Schwab option symbol.

    Schwab option symbols begin with the underlying
    padded to six characters.
    """

    if not symbol:
        return None

    return (
        symbol[:6]
        .strip()
        .upper()
    )


def main():

    print(
        "\nSchwab PaperMoney Order Probe\n"
    )

    print(
        "Retrieving authorized accounts..."
    )

    accounts = (
        get_linked_accounts()
    )

    print(
        f"Authorized accounts found: "
        f"{len(accounts)}"
    )

    if not accounts:

        print(
            "No authorized Schwab accounts found."
        )

        return

    #
    # We intentionally do not print the account
    # number or hash.
    #

    account = accounts[0]

    account_hash = account.get(
        "hashValue"
    )

    if not account_hash:

        raise RuntimeError(
            "Authorized account did not "
            "contain hashValue."
        )

    print(
        "Requesting recent orders..."
    )

    orders = (
        get_recent_orders(
            account_hash
        )
    )

    print(
        f"Orders returned: "
        f"{len(orders)}"
    )

    print(
        "\nSearching for current "
        "paperMoney tickers...\n"
    )

    matches = []

    for order in orders:

        symbols = extract_symbols(
            order
        )

        underlyings = {
            underlying_from_symbol(
                symbol
            )
            for symbol in symbols
        }

        matched_tickers = (
            underlyings
            & PAPER_TICKERS
        )

        if not matched_tickers:
            continue

        matches.append(
            {
                "Tickers": sorted(
                    matched_tickers
                ),
                "Symbols": symbols,
                "Status": order.get(
                    "status"
                ),
                "EnteredTime": order.get(
                    "enteredTime"
                ),
                "OrderType": order.get(
                    "orderType"
                ),
                "Price": order.get(
                    "price"
                ),
                "Quantity": order.get(
                    "quantity"
                ),
                "FilledQuantity": order.get(
                    "filledQuantity"
                ),
                "OrderStrategyType": (
                    order.get(
                        "orderStrategyType"
                    )
                ),
            }
        )

    if not matches:

        print(
            "RESULT: No matching orders found."
        )

        print(
            "\nNone of A, IR, NVDA, PCG, "
            "TFC, or TSN appeared in the "
            "exposed account's recent orders."
        )

        return

    print(
        f"RESULT: {len(matches)} matching "
        f"order(s) found!\n"
    )

    for match in matches:

        print(
            json.dumps(
                match,
                indent=2,
            )
        )

        print(
            "-" * 50
        )


if __name__ == "__main__":
    main()