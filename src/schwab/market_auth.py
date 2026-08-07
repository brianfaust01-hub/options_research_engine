"""
Project Stonks
Schwab Market Data Authentication

Handles the OAuth 2.0 authorization flow for the
Charles Schwab Market Data API.

Market Data authentication is intentionally isolated
from Accounts & Trading authentication.
"""

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import requests


AUTHORIZE_URL = (
    "https://api.schwabapi.com/v1/oauth/authorize"
)

TOKEN_URL = (
    "https://api.schwabapi.com/v1/oauth/token"
)

REDIRECT_URI = "https://127.0.0.1"

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent.parent
)

TOKEN_PATH = (
    PROJECT_ROOT
    / "data"
    / "schwab_market_tokens.json"
)


def _get_credentials():
    """
    Load Market Data application credentials.

    Supports the dedicated Market Data environment
    variable names first.

    Falls back to the original Schwab variable names
    so the current PowerShell session can still be used.
    """

    client_id = (
        os.getenv("SCHWAB_MARKET_CLIENT_ID")
        or os.getenv("SCHWAB_CLIENT_ID")
    )

    client_secret = (
        os.getenv("SCHWAB_MARKET_CLIENT_SECRET")
        or os.getenv("SCHWAB_CLIENT_SECRET")
    )

    if not client_id:
        raise RuntimeError(
            "Schwab Market Data client ID "
            "environment variable is not set."
        )

    if not client_secret:
        raise RuntimeError(
            "Schwab Market Data client secret "
            "environment variable is not set."
        )

    return client_id, client_secret


def _build_basic_auth_header(
    client_id: str,
    client_secret: str,
) -> str:
    """
    Build the HTTP Basic authorization value required
    by Schwab's token endpoint.
    """

    credentials = (
        f"{client_id}:{client_secret}"
    ).encode("utf-8")

    encoded_credentials = (
        base64.b64encode(
            credentials
        ).decode("utf-8")
    )

    return (
        f"Basic {encoded_credentials}"
    )


def get_authorization_url():
    """
    Build the Market Data OAuth authorization URL.
    """

    client_id, _ = _get_credentials()

    return (
        f"{AUTHORIZE_URL}"
        f"?client_id={quote(client_id)}"
        f"&redirect_uri="
        f"{quote(REDIRECT_URI, safe='')}"
    )


def extract_authorization_code(
    callback_url: str,
) -> str:
    """
    Extract the authorization code from Schwab's
    callback URL.
    """

    parsed_url = urlparse(
        callback_url.strip()
    )

    query = parse_qs(
        parsed_url.query
    )

    codes = query.get(
        "code"
    )

    if not codes:
        raise RuntimeError(
            "No authorization code was found "
            "in the callback URL."
        )

    return codes[0]


def exchange_authorization_code(
    authorization_code: str,
) -> dict:
    """
    Exchange a fresh authorization code for
    Market Data OAuth tokens.
    """

    client_id, client_secret = (
        _get_credentials()
    )

    headers = {
        "Authorization": (
            _build_basic_auth_header(
                client_id,
                client_secret,
            )
        ),
        "Content-Type": (
            "application/x-www-form-urlencoded"
        ),
    }

    data = {
        "grant_type": (
            "authorization_code"
        ),
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI,
    }

    response = requests.post(
        TOKEN_URL,
        headers=headers,
        data=data,
        timeout=30,
    )

    if not response.ok:

        print(
            f"Schwab Market Data token error: "
            f"HTTP {response.status_code}"
        )

        try:

            error_data = (
                response.json()
            )

            print(
                f"Error: "
                f"{error_data.get('error')}"
            )

            print(
                f"Description: "
                f"{error_data.get('error_description')}"
            )

        except Exception:

            print(
                "Schwab returned a non-JSON "
                "error response."
            )

        raise RuntimeError(
            "Schwab Market Data token "
            "exchange failed."
        )

    return response.json()


def save_tokens(
    tokens: dict,
) -> None:
    """
    Persist Market Data tokens separately from
    Accounts & Trading tokens.
    """

    now = datetime.now(
        timezone.utc
    )

    expires_in = int(
        tokens.get(
            "expires_in",
            1800,
        )
    )

    token_data = dict(
        tokens
    )

    token_data["saved_at"] = (
        now.isoformat()
    )

    token_data[
        "access_token_expires_at"
    ] = (
        now
        + timedelta(
            seconds=expires_in
        )
    ).isoformat()

    token_data[
        "refresh_token_expires_at"
    ] = (
        now
        + timedelta(
            days=7
        )
    ).isoformat()

    TOKEN_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        TOKEN_PATH.with_suffix(
            ".writing.json"
        )
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            token_data,
            file,
            indent=2,
        )

    temporary_path.replace(
        TOKEN_PATH
    )


if __name__ == "__main__":

    print(
        "\nSchwab Market Data OAuth\n"
    )

    print(
        "Open the following URL "
        "in your browser:\n"
    )

    print(
        get_authorization_url()
    )

    print()

    callback_url = input(
        "After authorization, paste the "
        "complete callback URL here:\n\n"
    )

    authorization_code = (
        extract_authorization_code(
            callback_url
        )
    )

    print(
        "\nAuthorization code "
        "extracted successfully."
    )

    tokens = (
        exchange_authorization_code(
            authorization_code
        )
    )

    save_tokens(
        tokens
    )

    print(
        "\nMarket Data token "
        "exchange successful."
    )

    print(
        "Market Data tokens saved "
        "to local storage."
    )

    print(
        f"Access token received: "
        f"{bool(tokens.get('access_token'))}"
    )

    print(
        f"Refresh token received: "
        f"{bool(tokens.get('refresh_token'))}"
    )

    print(
        f"Expires in: "
        f"{tokens.get('expires_in')} seconds"
    )