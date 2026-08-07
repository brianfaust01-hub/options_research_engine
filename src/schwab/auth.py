"""
Project Stonks
Schwab Authentication

Handles the OAuth 2.0 authorization flow for the
Charles Schwab Trader API.

This module is intentionally isolated from the rest
of Project Stonks.
"""

import base64
import os
from urllib.parse import parse_qs, quote, urlparse

import requests

from token_manager import save_tokens


AUTHORIZE_URL = (
    "https://api.schwabapi.com/v1/oauth/authorize"
)

TOKEN_URL = (
    "https://api.schwabapi.com/v1/oauth/token"
)

REDIRECT_URI = "https://127.0.0.1"


def _get_credentials():
    """
    Load Schwab credentials from environment variables.

    Credentials must never be stored directly in source code.
    """

    client_id = os.getenv("SCHWAB_CLIENT_ID")
    client_secret = os.getenv("SCHWAB_CLIENT_SECRET")

    if not client_id:
        raise RuntimeError(
            "SCHWAB_CLIENT_ID environment variable is not set."
        )

    if not client_secret:
        raise RuntimeError(
            "SCHWAB_CLIENT_SECRET environment variable is not set."
        )

    return client_id, client_secret


def get_authorization_url():
    """
    Build the Schwab OAuth authorization URL.

    Open this URL in a browser to authorize the application.
    """

    client_id, _ = _get_credentials()

    return (
        f"{AUTHORIZE_URL}"
        f"?client_id={quote(client_id)}"
        f"&redirect_uri={quote(REDIRECT_URI, safe='')}"
    )


def extract_authorization_code(
    callback_url: str,
) -> str:
    """
    Extract the authorization code from the Schwab callback URL.

    parse_qs already URL-decodes query-string values,
    so the code must not be decoded a second time.
    """

    parsed_url = urlparse(
        callback_url.strip()
    )

    query = parse_qs(
        parsed_url.query
    )

    codes = query.get("code")

    if not codes:
        raise RuntimeError(
            "No authorization code was found "
            "in the callback URL."
        )

    return codes[0]


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

    encoded_credentials = base64.b64encode(
        credentials
    ).decode("utf-8")

    return f"Basic {encoded_credentials}"


def _handle_token_response(
    response: requests.Response,
) -> dict:
    """
    Validate a Schwab token response without printing
    sensitive token values.
    """

    if not response.ok:

        print(
            f"Schwab token error: "
            f"HTTP {response.status_code}"
        )

        try:
            error_data = response.json()

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
            "Schwab token exchange failed."
        )

    return response.json()


def exchange_authorization_code(
    authorization_code: str,
) -> dict:
    """
    Exchange a Schwab authorization code for the
    initial access and refresh tokens.
    """

    client_id, client_secret = _get_credentials()

    headers = {
        "Authorization": _build_basic_auth_header(
            client_id,
            client_secret,
        ),
        "Content-Type": (
            "application/x-www-form-urlencoded"
        ),
    }

    data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI,
    }

    response = requests.post(
        TOKEN_URL,
        headers=headers,
        data=data,
        timeout=30,
    )

    return _handle_token_response(
        response
    )


def refresh_access_token(
    refresh_token: str,
) -> dict:
    """
    Use an existing Schwab refresh token to obtain
    a new access token.
    """

    client_id, client_secret = _get_credentials()

    headers = {
        "Authorization": _build_basic_auth_header(
            client_id,
            client_secret,
        ),
        "Content-Type": (
            "application/x-www-form-urlencoded"
        ),
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    response = requests.post(
        TOKEN_URL,
        headers=headers,
        data=data,
        timeout=30,
    )

    return _handle_token_response(
        response
    )


if __name__ == "__main__":

    print(
        "\nSchwab OAuth Token Exchange\n"
    )

    callback_url = input(
        "Paste the complete callback URL here:\n\n"
    )

    authorization_code = (
        extract_authorization_code(
            callback_url
        )
    )

    print(
        "\nAuthorization code extracted successfully."
    )

    tokens = exchange_authorization_code(
        authorization_code
    )

    save_tokens(
        tokens
    )

    print(
        "\nToken exchange successful."
    )

    print(
        "Tokens saved securely to local storage."
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