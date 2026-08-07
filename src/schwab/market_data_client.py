"""
Project Stonks
Schwab Market Data Client

Provides a centralized interface to the Schwab
Market Data API.

Responsibilities:
- Obtain valid OAuth access tokens automatically
- Execute authenticated Market Data requests
- Retrieve equity quotes
- Retrieve option chains
- Retrieve specific option contracts
- Normalize commonly used market-data fields

This module does NOT make trading decisions.
"""

from __future__ import annotations

from typing import Any

import requests

from schwab.market_token_manager import get_access_token


BASE_URL = (
    "https://api.schwabapi.com/marketdata/v1"
)

REQUEST_TIMEOUT_SECONDS = 30


def _get(
    endpoint: str,
    params: dict | None = None,
) -> dict:
    """
    Execute an authenticated GET request against
    the Schwab Market Data API.
    """

    access_token = (
        get_access_token()
    )

    headers = {
        "Authorization": (
            f"Bearer {access_token}"
        ),
        "Accept": "application/json",
    }

    url = (
        f"{BASE_URL}{endpoint}"
    )

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if not response.ok:

        print(
            "Schwab Market Data API error: "
            f"HTTP {response.status_code}"
        )

        print(
            f"Endpoint: {endpoint}"
        )

        try:

            error_data = (
                response.json()
            )

            print(
                f"Response: {error_data}"
            )

        except Exception:

            print(
                f"Response: {response.text}"
            )

        response.raise_for_status()

    return response.json()


def get_quote(
    ticker: str,
) -> dict:
    """
    Retrieve the raw Schwab quote response
    for one security.
    """

    ticker = (
        ticker.upper().strip()
    )

    return _get(
        f"/{ticker}/quotes"
    )


def get_normalized_quote(
    ticker: str,
) -> dict:
    """
    Retrieve commonly used quote fields in a
    stable Project Stonks structure.
    """

    ticker = (
        ticker.upper().strip()
    )

    response = (
        get_quote(
            ticker
        )
    )

    security = response.get(
        ticker,
        {}
    )

    quote = security.get(
        "quote",
        {}
    )

    reference = security.get(
        "reference",
        {}
    )

    return {
        "Ticker": ticker,
        "Description": (
            reference.get(
                "description"
            )
        ),
        "Bid": (
            quote.get(
                "bidPrice"
            )
        ),
        "Ask": (
            quote.get(
                "askPrice"
            )
        ),
        "Last": (
            quote.get(
                "lastPrice"
            )
        ),
        "Mark": (
            quote.get(
                "mark"
            )
        ),
        "Open": (
            quote.get(
                "openPrice"
            )
        ),
        "High": (
            quote.get(
                "highPrice"
            )
        ),
        "Low": (
            quote.get(
                "lowPrice"
            )
        ),
        "Close": (
            quote.get(
                "closePrice"
            )
        ),
        "Volume": (
            quote.get(
                "totalVolume"
            )
        ),
        "NetChange": (
            quote.get(
                "netChange"
            )
        ),
        "NetPercentChange": (
            quote.get(
                "netPercentChange"
            )
        ),
    }


    """
    Retrieve historical price data from Schwab.

    Returns the raw Schwab price-history response.
    """

    ticker = (
        ticker.upper().strip()
    )

    params = {
        "periodType": period_type,
        "period": period,
        "frequencyType": frequency_type,
        "frequency": frequency,
        "needExtendedHoursData": str(
            need_extended_hours_data
        ).lower(),
    }

    return _get(
        f"/pricehistory/{ticker}",
        params=params,
    )




    response = get_price_history(
        ticker=ticker,
        period_type=period_type,
        period=period,
        frequency_type=frequency_type,
        frequency=frequency,
        need_extended_hours_data=(
            need_extended_hours_data
        ),
    )

    candles = response.get(
        "candles",
        [],
    )

    normalized = []

    for candle in candles:

        normalized.append(
            {
                "Open": candle.get(
                    "open"
                ),
                "High": candle.get(
                    "high"
                ),
                "Low": candle.get(
                    "low"
                ),
                "Close": candle.get(
                    "close"
                ),
                "Volume": candle.get(
                    "volume"
                ),
                "Datetime": candle.get(
                    "datetime"
                ),
            }
        )

    return normalized
def get_option_chain(
    ticker: str,
    contract_type: str = "ALL",
    strategy: str = "SINGLE",
    include_underlying_quote: bool = True,
) -> dict:
    """
    Retrieve a Schwab option chain.

    Parameters remain intentionally conservative
    during initial integration. Additional filters
    can be added after validation.
    """

    ticker = (
        ticker.upper().strip()
    )

    params = {
        "symbol": ticker,
        "contractType": (
            contract_type.upper()
        ),
        "strategy": (
            strategy.upper()
        ),
        "includeUnderlyingQuote": (
            str(
                include_underlying_quote
            ).lower()
        ),
    }

    return _get(
        "/chains",
        params=params,
    )


def find_option_contract(
    ticker: str,
    expiration: str,
    strike: float,
    option_type: str,
) -> dict | None:
    """
    Find one specific option contract.

    expiration:
        YYYY-MM-DD

    option_type:
        CALL or PUT

    Returns the raw Schwab contract dictionary,
    or None if the contract is not found.
    """

    ticker = (
        ticker.upper().strip()
    )

    option_type = (
        option_type.upper().strip()
    )

    if option_type not in (
        "CALL",
        "PUT",
    ):
        raise ValueError(
            "option_type must be CALL or PUT."
        )

    chain = (
        get_option_chain(
            ticker=ticker,
            contract_type=option_type,
        )
    )

    if option_type == "CALL":

        option_map = chain.get(
            "callExpDateMap",
            {},
        )

    else:

        option_map = chain.get(
            "putExpDateMap",
            {},
        )

    target_strike = float(
        strike
    )

    for (
        expiration_key,
        strikes,
    ) in option_map.items():

        expiration_date = (
            expiration_key.split(
                ":"
            )[0]
        )

        if (
            expiration_date
            != expiration
        ):
            continue

        for (
            strike_key,
            contracts,
        ) in strikes.items():

            try:

                contract_strike = (
                    float(
                        strike_key
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

            if (
                contract_strike
                != target_strike
            ):
                continue

            if contracts:

                return contracts[0]

    return None


def get_normalized_option(
    ticker: str,
    expiration: str,
    strike: float,
    option_type: str,
) -> dict | None:
    """
    Retrieve one option contract and normalize the
    fields most useful to Project Stonks.
    """

    contract = (
        find_option_contract(
            ticker=ticker,
            expiration=expiration,
            strike=strike,
            option_type=option_type,
        )
    )

    if contract is None:
        return None

    bid = contract.get(
        "bid"
    )

    ask = contract.get(
        "ask"
    )

    mark = contract.get(
        "mark"
    )

    #
    # Schwab normally provides mark directly.
    # If it does not, calculate midpoint when
    # both sides of the market are available.
    #

    if (
        mark is None
        and bid is not None
        and ask is not None
    ):

        mark = (
            bid + ask
        ) / 2

    return {
        "Ticker": (
            ticker.upper().strip()
        ),
        "Symbol": (
            contract.get(
                "symbol"
            )
        ),
        "Description": (
            contract.get(
                "description"
            )
        ),
        "OptionType": (
            option_type.upper().strip()
        ),
        "Expiration": expiration,
        "Strike": float(
            strike
        ),
        "Bid": bid,
        "Ask": ask,
        "Last": (
            contract.get(
                "last"
            )
        ),
        "Mark": mark,
        "Close": (
            contract.get(
                "closePrice"
            )
        ),
        "Volume": (
            contract.get(
                "totalVolume"
            )
        ),
        "OpenInterest": (
            contract.get(
                "openInterest"
            )
        ),
        "Delta": (
            contract.get(
                "delta"
            )
        ),
        "Gamma": (
            contract.get(
                "gamma"
            )
        ),
        "Theta": (
            contract.get(
                "theta"
            )
        ),
        "Vega": (
            contract.get(
                "vega"
            )
        ),
        "Rho": (
            contract.get(
                "rho"
            )
        ),
        "IV": (
            contract.get(
                "volatility"
            )
        ),
        "InTheMoney": (
            contract.get(
                "inTheMoney"
            )
        ),
        "DaysToExpiration": (
            contract.get(
                "daysToExpiration"
            )
        ),
    }
def get_normalized_option_chain(
    ticker: str,
    option_type: str,
) -> list[dict]:
    """
    Retrieve an option chain from Schwab and normalize
    every contract into a stable Project Stonks structure.

    option_type:
        CALL or PUT

    Returns:
        List of normalized contract dictionaries.
    """

    ticker = (
        ticker.upper().strip()
    )

    option_type = (
        option_type.upper().strip()
    )

    if option_type not in (
        "CALL",
        "PUT",
    ):
        raise ValueError(
            "option_type must be CALL or PUT."
        )

    chain = get_option_chain(
        ticker=ticker,
        contract_type=option_type,
    )

    if option_type == "CALL":
        option_map = chain.get(
            "callExpDateMap",
            {},
        )
    else:
        option_map = chain.get(
            "putExpDateMap",
            {},
        )

    normalized_contracts = []

    for (
        expiration_key,
        strikes,
    ) in option_map.items():

        expiration = (
            expiration_key.split(":")[0]
        )

        for (
            strike_key,
            contracts,
        ) in strikes.items():

            try:
                strike = float(
                    strike_key
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            for contract in contracts:

                bid = contract.get(
                    "bid"
                )

                ask = contract.get(
                    "ask"
                )

                mark = contract.get(
                    "mark"
                )

                if (
                    mark is None
                    and bid is not None
                    and ask is not None
                ):
                    mark = (
                        bid + ask
                    ) / 2

                normalized_contracts.append(
                    {
                        "Ticker": ticker,
                        "Symbol": contract.get(
                            "symbol"
                        ),
                        "Description": contract.get(
                            "description"
                        ),
                        "OptionType": option_type,
                        "Expiration": expiration,
                        "Strike": strike,
                        "Bid": bid,
                        "Ask": ask,
                        "Last": contract.get(
                            "last"
                        ),
                        "Mark": mark,
                        "Close": contract.get(
                            "closePrice"
                        ),
                        "Volume": contract.get(
                            "totalVolume"
                        ),
                        "OpenInterest": contract.get(
                            "openInterest"
                        ),
                        "Delta": contract.get(
                            "delta"
                        ),
                        "Gamma": contract.get(
                            "gamma"
                        ),
                        "Theta": contract.get(
                            "theta"
                        ),
                        "Vega": contract.get(
                            "vega"
                        ),
                        "Rho": contract.get(
                            "rho"
                        ),
                        "IV": contract.get(
                            "volatility"
                        ),
                        "InTheMoney": contract.get(
                            "inTheMoney"
                        ),
                        "DaysToExpiration": (
                            contract.get(
                                "daysToExpiration"
                            )
                        ),
                    }
                )

    return normalized_contracts

if __name__ == "__main__":

    print(
        "\nSchwab Market Data Client Test\n"
    )

    print(
        "Testing IFF equity quote..."
    )

    quote = (
        get_normalized_quote(
            "IFF"
        )
    )

    print(
        quote
    )

    print(
        "\nTesting IFF option contract..."
    )

    option = (
        get_normalized_option(
            ticker="IFF",
            expiration="2026-09-18",
            strike=55.0,
            option_type="CALL",
        )
    )

    print(
        option
    )