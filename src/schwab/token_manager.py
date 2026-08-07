"""
Project Stonks
Schwab Token Manager

Persists Schwab OAuth tokens locally and provides
automatic access-token refresh.

Token files must never be committed to source control.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

TOKEN_PATH = (
    PROJECT_ROOT
    / "data"
    / "schwab_tokens.json"
)

TOKEN_URL = (
    "https://api.schwabapi.com/v1/oauth/token"
)

ACCESS_TOKEN_REFRESH_BUFFER_SECONDS = 60


def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _parse_timestamp(
    value: str,
) -> datetime:
    return datetime.fromisoformat(
        value
    )


def _get_credentials():
    """
    Load Schwab credentials from environment variables.
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


def _build_basic_auth_header(
    client_id: str,
    client_secret: str,
) -> str:
    """
    Build Schwab HTTP Basic authentication header.
    """

    credentials = (
        f"{client_id}:{client_secret}"
    ).encode("utf-8")

    encoded_credentials = base64.b64encode(
        credentials
    ).decode("utf-8")

    return f"Basic {encoded_credentials}"


def _load_tokens() -> dict:
    """
    Load persisted Schwab tokens.
    """

    if not TOKEN_PATH.exists():
        raise RuntimeError(
            "No Schwab token file exists. "
            "Complete OAuth authorization first."
        )

    with TOKEN_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_tokens(
    tokens: dict,
    existing_refresh_expires_at: str | None = None,
) -> None:
    """
    Persist Schwab tokens locally.

    Access-token expiration is calculated from the
    expires_in value returned by Schwab.

    The refresh-token expiration timestamp is preserved
    during normal access-token refreshes unless this is
    a new OAuth authorization.
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

    token_data["saved_at"] = (
        now.isoformat()
    )

    token_data["access_token_expires_at"] = (
        now
        + timedelta(
            seconds=expires_in
        )
    ).isoformat()

    if existing_refresh_expires_at:

        token_data[
            "refresh_token_expires_at"
        ] = existing_refresh_expires_at

    else:

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


def _access_token_is_valid(
    token_data: dict,
) -> bool:
    """
    Return True when the current access token has
    more than the safety buffer remaining.
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
    Return True when the refresh token is still
    within its locally tracked seven-day lifetime.
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
    Request a new access token directly from Schwab.
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

    if not response.ok:

        print(
            f"Schwab refresh error: "
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
            "Schwab access-token refresh failed."
        )

    return response.json()


def get_access_token() -> str:
    """
    Return a valid Schwab access token.

    Automatically refresh the access token when
    it is expired or within 60 seconds of expiration.
    """

    token_data = _load_tokens()

    if _access_token_is_valid(
        token_data
    ):

        access_token = token_data.get(
            "access_token"
        )

        if not access_token:
            raise RuntimeError(
                "Schwab token file does not contain "
                "an access token."
            )

        return access_token

    if not _refresh_token_is_valid(
        token_data
    ):

        raise RuntimeError(
            "Schwab refresh token has expired. "
            "Complete OAuth authorization again."
        )

    refresh_token = token_data.get(
        "refresh_token"
    )

    if not refresh_token:
        raise RuntimeError(
            "Schwab token file does not contain "
            "a refresh token."
        )

    print(
        "Refreshing Schwab access token..."
    )

    new_tokens = _refresh_access_token(
        refresh_token
    )

    #
    # Schwab may return a refresh token in the response.
    # If it does not, retain the existing one.
    #

    if not new_tokens.get(
        "refresh_token"
    ):
        new_tokens[
            "refresh_token"
        ] = refresh_token

    #
    # An access-token refresh does NOT restart our
    # locally tracked seven-day OAuth authorization
    # window.
    #

    save_tokens(
        new_tokens,
        existing_refresh_expires_at=(
            token_data.get(
                "refresh_token_expires_at"
            )
        ),
    )

    print(
        "Schwab access token refreshed."
    )

    return new_tokens[
        "access_token"
    ]


def get_token_status() -> dict:
    """
    Return non-sensitive token status information.
    """

    token_data = _load_tokens()

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