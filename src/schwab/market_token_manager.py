"""
Project Stonks
Schwab Market Data Token Manager

Manages persisted OAuth tokens for the Schwab
Market Data API.

Responsibilities:
- Load persisted Market Data tokens
- Return a valid access token
- Automatically refresh expired access tokens
- Preserve refresh-token lifetime
- Keep Market Data authentication isolated from
  Accounts & Trading authentication
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone
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

TOKEN_URL = (
    "https://api.schwabapi.com/v1/oauth/token"
)

ACCESS_TOKEN_REFRESH_BUFFER_SECONDS = 60


def _utc_now() -> datetime:
    """
    Return the current UTC time.
    """

    return datetime.now(
        timezone.utc
    )


def _parse_timestamp(
    value: str,
) -> datetime:
    """
    Parse an ISO timestamp stored in the token file.
    """

    return datetime.fromisoformat(
        value
    )


def _get_credentials():
    """
    Load Schwab Market Data application credentials.

    Dedicated Market Data environment variables are
    preferred.

    The original Schwab variables remain supported
    temporarily for the current development setup.
    """

    client_id = (
        os.getenv(
            "SCHWAB_MARKET_CLIENT_ID"
        )
        or os.getenv(
            "SCHWAB_CLIENT_ID"
        )
    )

    client_secret = (
        os.getenv(
            "SCHWAB_MARKET_CLIENT_SECRET"
        )
        or os.getenv(
            "SCHWAB_CLIENT_SECRET"
        )
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

    return (
        client_id,
        client_secret,
    )


def _build_basic_auth_header(
    client_id: str,
    client_secret: str,
) -> str:
    """
    Build the HTTP Basic authentication value
    required by Schwab's OAuth token endpoint.
    """

    credentials = (
        f"{client_id}:{client_secret}"
    ).encode(
        "utf-8"
    )

    encoded_credentials = (
        base64.b64encode(
            credentials
        ).decode(
            "utf-8"
        )
    )

    return (
        f"Basic {encoded_credentials}"
    )


def _load_tokens() -> dict:
    """
    Load persisted Schwab Market Data tokens.
    """

    if not TOKEN_PATH.exists():
        raise RuntimeError(
            "No Schwab Market Data token file exists. "
            "Run market_auth.py first."
        )

    with TOKEN_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(
            file
        )


def _save_tokens(
    tokens: dict,
    existing_refresh_expires_at: str | None,
) -> None:
    """
    Persist refreshed Market Data tokens.

    Access-token expiration is recalculated after
    every refresh.

    Refresh-token expiration is preserved so a
    normal 30-minute access-token refresh does not
    incorrectly restart the longer authorization
    lifetime.
    """

    now = _utc_now()

    expires_in = int(
        tokens.get(
            "expires_in",
            1800,
        )
    )

    token_data = dict(
        tokens
    )

    token_data[
        "saved_at"
    ] = now.isoformat()

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
    ] = existing_refresh_expires_at

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


def _access_token_is_valid(
    token_data: dict,
) -> bool:
    """
    Determine whether the stored access token
    can still safely be used.
    """

    expiration = token_data.get(
        "access_token_expires_at"
    )

    if not expiration:
        return False

    expires_at = _parse_timestamp(
        expiration
    )

    refresh_threshold = (
        expires_at
        - timedelta(
            seconds=(
                ACCESS_TOKEN_REFRESH_BUFFER_SECONDS
            )
        )
    )

    return (
        _utc_now()
        < refresh_threshold
    )


def _refresh_token_is_valid(
    token_data: dict,
) -> bool:
    """
    Determine whether the stored refresh token
    is still within its tracked lifetime.
    """

    expiration = token_data.get(
        "refresh_token_expires_at"
    )

    if not expiration:
        return False

    expires_at = _parse_timestamp(
        expiration
    )

    return (
        _utc_now()
        < expires_at
    )


def _refresh_access_token(
    refresh_token: str,
) -> dict:
    """
    Request a new Market Data access token
    from Schwab.
    """

    (
        client_id,
        client_secret,
    ) = _get_credentials()

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
            "refresh_token"
        ),
        "refresh_token": (
            refresh_token
        ),
    }

    response = requests.post(
        TOKEN_URL,
        headers=headers,
        data=data,
        timeout=30,
    )

    if not response.ok:

        print(
            "Schwab Market Data refresh error: "
            f"HTTP {response.status_code}"
        )

        try:

            error_data = (
                response.json()
            )

            print(
                "Error: "
                f"{error_data.get('error')}"
            )

            print(
                "Description: "
                f"{error_data.get('error_description')}"
            )

        except Exception:

            print(
                "Schwab returned a non-JSON "
                "refresh error response."
            )

        raise RuntimeError(
            "Schwab Market Data "
            "access-token refresh failed."
        )

    return response.json()


def get_access_token() -> str:
    """
    Return a valid Schwab Market Data access token.

    If the stored access token is expired or within
    60 seconds of expiration, automatically refresh
    it before returning.
    """

    token_data = (
        _load_tokens()
    )

    if _access_token_is_valid(
        token_data
    ):

        access_token = (
            token_data.get(
                "access_token"
            )
        )

        if not access_token:
            raise RuntimeError(
                "Schwab Market Data token file "
                "does not contain an access token."
            )

        return access_token

    if not _refresh_token_is_valid(
        token_data
    ):

        raise RuntimeError(
            "Schwab Market Data refresh token "
            "has expired. Complete OAuth "
            "authorization again."
        )

    refresh_token = (
        token_data.get(
            "refresh_token"
        )
    )

    if not refresh_token:
        raise RuntimeError(
            "Schwab Market Data token file "
            "does not contain a refresh token."
        )

    print(
        "Refreshing Schwab Market Data "
        "access token..."
    )

    new_tokens = (
        _refresh_access_token(
            refresh_token
        )
    )

    #
    # Preserve the existing refresh token if
    # Schwab does not return a replacement.
    #

    if not new_tokens.get(
        "refresh_token"
    ):

        new_tokens[
            "refresh_token"
        ] = refresh_token

    _save_tokens(
        new_tokens,
        existing_refresh_expires_at=(
            token_data.get(
                "refresh_token_expires_at"
            )
        ),
    )

    print(
        "Schwab Market Data "
        "access token refreshed."
    )

    return new_tokens[
        "access_token"
    ]


def get_token_status() -> dict:
    """
    Return non-sensitive Market Data token status.

    Token values themselves are never returned.
    """

    token_data = (
        _load_tokens()
    )

    return {
        "AccessTokenValid": (
            _access_token_is_valid(
                token_data
            )
        ),
        "RefreshTokenValid": (
            _refresh_token_is_valid(
                token_data
            )
        ),
        "AccessTokenExpiresAt": (
            token_data.get(
                "access_token_expires_at"
            )
        ),
        "RefreshTokenExpiresAt": (
            token_data.get(
                "refresh_token_expires_at"
            )
        ),
    }


if __name__ == "__main__":

    print(
        "\nSchwab Market Data Token Manager\n"
    )

    status = (
        get_token_status()
    )

    print(
        f"Access Token Valid: "
        f"{status['AccessTokenValid']}"
    )

    print(
        f"Refresh Token Valid: "
        f"{status['RefreshTokenValid']}"
    )

    print(
        f"Access Token Expires: "
        f"{status['AccessTokenExpiresAt']}"
    )

    print(
        f"Refresh Token Expires: "
        f"{status['RefreshTokenExpiresAt']}"
    )

    print(
        "\nRequesting valid access token..."
    )

    token = (
        get_access_token()
    )

    print(
        f"Valid access token available: "
        f"{bool(token)}"
    )