"""
Project Stonks
Greeks Calculator

Uses Black-Scholes approximation for European-style option Greeks.
"""

import math

from scipy.stats import norm


def calculate_greeks(
    stock_price: float,
    strike: float,
    days_to_expiration: int,
    implied_volatility: float,
    risk_free_rate: float = 0.04,
    option_type: str = "call",
) -> dict:
    if days_to_expiration <= 0 or implied_volatility <= 0:
        return {
            "delta": None,
            "gamma": None,
            "theta": None,
            "vega": None,
        }

    time_to_expiration = days_to_expiration / 365

    d1 = (
        math.log(stock_price / strike)
        + (risk_free_rate + 0.5 * implied_volatility ** 2) * time_to_expiration
    ) / (
        implied_volatility * math.sqrt(time_to_expiration)
    )

    d2 = d1 - implied_volatility * math.sqrt(time_to_expiration)

    if option_type.lower() == "call":
        delta = norm.cdf(d1)
        theta = (
            -stock_price
            * norm.pdf(d1)
            * implied_volatility
            / (2 * math.sqrt(time_to_expiration))
            - risk_free_rate
            * strike
            * math.exp(-risk_free_rate * time_to_expiration)
            * norm.cdf(d2)
        ) / 365

    elif option_type.lower() == "put":
        delta = norm.cdf(d1) - 1
        theta = (
            -stock_price
            * norm.pdf(d1)
            * implied_volatility
            / (2 * math.sqrt(time_to_expiration))
            + risk_free_rate
            * strike
            * math.exp(-risk_free_rate * time_to_expiration)
            * norm.cdf(-d2)
        ) / 365

    else:
        raise ValueError("option_type must be 'call' or 'put'")

    gamma = norm.pdf(d1) / (
        stock_price
        * implied_volatility
        * math.sqrt(time_to_expiration)
    )

    vega = (
        stock_price
        * norm.pdf(d1)
        * math.sqrt(time_to_expiration)
    ) / 100

    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
    }