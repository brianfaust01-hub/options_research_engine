"""
Project Stonks
Schwab Accounts API Smoke Test

Tests authenticated access to Schwab account-number data.

This script is intentionally read-only.
It does not place, modify, or cancel orders.
"""

import requests

from token_manager import get_access_token


ACCOUNTS_URL = (
    "https://api.schwabapi.com/trader/v1/accounts/"
    "accountNumbers"
)


def get_account_numbers():
    """
    Retrieve account identifiers available to the
    authenticated Schwab user.
    """

    access_token = get_access_token()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    response = requests.get(
        ACCOUNTS_URL,
        headers=headers,
        timeout=30,
    )

    if not response.ok:

        print(
            f"Schwab Accounts API error: "
            f"HTTP {response.status_code}"
        )

        print(
            response.text
        )

        response.raise_for_status()

    return response.json()


if __name__ == "__main__":

    print(
        "\nSchwab Accounts API Test\n"
    )

    accounts = get_account_numbers()

    print(
        f"Accounts returned: {len(accounts)}\n"
    )

    for index, account in enumerate(
        accounts,
        start=1,
    ):

        print(
            f"Account {index}"
        )

        print(
            f"  Account Number: "
            f"{account.get('accountNumber')}"
        )

        print(
            f"  Hash Value: "
            f"{account.get('hashValue')}"
        )

        print()