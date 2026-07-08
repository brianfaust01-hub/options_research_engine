"""
Project Stonks
Options Engine

Sprint 26:
Contract Scoring v2.

Research Mode uses best-available option data:
- Prefer bid/ask midpoint when available
- Fall back to lastPrice when bid/ask are unavailable
- Penalize weak quote quality instead of rejecting every contract
"""

from datetime import datetime

import pandas as pd
import yfinance as yf

from config import (
    MAX_MONEYNESS,
    MAX_PREMIUM_PCT_OF_STOCK,
    MIN_MONEYNESS,
    MIN_OPTION_DTE,
    MIN_OPTION_PREMIUM,
    MAX_OPTION_DTE,
)

from greeks import calculate_greeks


def get_option_expirations(ticker: str) -> list[str]:
    stock = yf.Ticker(ticker)
    return list(stock.options)


def get_target_expirations(
    ticker: str,
    min_dte: int = MIN_OPTION_DTE,
    max_dte: int = MAX_OPTION_DTE,
) -> list[str]:
    today = datetime.today().date()
    expirations = get_option_expirations(ticker)

    results = []

    for expiration in expirations:
        try:
            expiration_date = datetime.strptime(expiration, "%Y-%m-%d").date()
            dte = (expiration_date - today).days

            if min_dte <= dte <= max_dte:
                results.append(expiration)

        except ValueError:
            continue

    return results


def get_option_chain(ticker: str, expiration: str, option_type: str):
    try:
        stock = yf.Ticker(ticker)
        chain = stock.option_chain(expiration)

        if option_type.lower() == "call":
            return chain.calls.copy()

        if option_type.lower() == "put":
            return chain.puts.copy()

        raise ValueError("option_type must be 'call' or 'put'")

    except Exception as error:
        print(
            f"Option chain unavailable for {ticker} "
            f"{expiration} {option_type}: {error}"
        )
        return pd.DataFrame()


def _safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _calculate_mid(row) -> float:
    bid = _safe_float(row.get("bid", 0))
    ask = _safe_float(row.get("ask", 0))
    last_price = _safe_float(row.get("lastPrice", 0))

    if bid > 0 and ask > 0:
        return (bid + ask) / 2

    if last_price > 0:
        return last_price

    return 0.0


def _calculate_spread_pct(row):
    bid = _safe_float(row.get("bid", 0))
    ask = _safe_float(row.get("ask", 0))
    mid = _safe_float(row.get("mid", 0))

    if bid > 0 and ask > 0 and mid > 0:
        return (ask - bid) / mid

    return None


def _quote_quality(row) -> str:
    bid = _safe_float(row.get("bid", 0))
    ask = _safe_float(row.get("ask", 0))
    last_price = _safe_float(row.get("lastPrice", 0))
    spread_pct = row.get("spread_pct")

    if bid > 0 and ask > 0 and spread_pct is not None:
        if spread_pct <= 0.10:
            return "Excellent"
        if spread_pct <= 0.25:
            return "Good"
        if spread_pct <= 0.50:
            return "Wide"
        return "Very Wide"

    if last_price > 0:
        return "Last Price Fallback"

    return "No Quote"


def _score_dte(dte: int) -> int:
    if 30 <= dte <= 60:
        return 20
    if 21 <= dte < 30 or 60 < dte <= 90:
        return 15
    if 14 <= dte < 21 or 90 < dte <= 150:
        return 8
    return 0


def _score_quote_quality(quote_quality: str) -> int:
    if quote_quality == "Excellent":
        return 20
    if quote_quality == "Good":
        return 14
    if quote_quality == "Wide":
        return 5
    if quote_quality == "Very Wide":
        return -10
    if quote_quality == "Last Price Fallback":
        return 0
    return -25


def _score_open_interest(open_interest: float) -> int:
    if open_interest >= 2_000:
        return 20
    if open_interest >= 1_000:
        return 16
    if open_interest >= 500:
        return 12
    if open_interest >= 100:
        return 8
    if open_interest >= 25:
        return 4
    return 0


def _score_volume(volume: float) -> int:
    if volume >= 500:
        return 15
    if volume >= 250:
        return 12
    if volume >= 100:
        return 8
    if volume >= 10:
        return 4
    return 0


def _score_moneyness(moneyness: float) -> int:
    if 1.00 <= moneyness <= 1.07:
        return 20
    if 0.95 <= moneyness < 1.00:
        return 14
    if 1.07 < moneyness <= 1.15:
        return 12
    if 1.15 < moneyness <= 1.30:
        return 6
    if 1.30 < moneyness <= 1.40:
        return 2
    return -10


def _score_delta(delta_abs: float) -> int:
    if 0.30 <= delta_abs <= 0.55:
        return 25
    if 0.20 <= delta_abs < 0.30:
        return 15
    if 0.55 < delta_abs <= 0.70:
        return 12
    if 0.10 <= delta_abs < 0.20:
        return 5
    if 0.70 < delta_abs <= 0.85:
        return 2
    return -10


def _score_theta(theta: float, premium: float) -> int:
    if premium <= 0:
        return 0

    theta_drag = abs(theta) / premium

    if theta_drag <= 0.015:
        return 15
    if theta_drag <= 0.030:
        return 10
    if theta_drag <= 0.050:
        return 5
    if theta_drag <= 0.075:
        return 0
    return -8


def _assign_selection_tier(score: float) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Strong"
    if score >= 55:
        return "Tradable"
    if score >= 35:
        return "Speculative"
    return "Poor"


def score_contracts(
    chain,
    stock_price: float,
    option_type: str,
    expiration: str,
):
    contracts = chain.copy()

    if contracts.empty:
        return contracts

    required_columns = [
        "strike",
        "lastPrice",
        "bid",
        "ask",
        "impliedVolatility",
    ]

    for column in required_columns:
        if column not in contracts.columns:
            return pd.DataFrame()

    expiration_date = datetime.strptime(expiration, "%Y-%m-%d").date()
    today = datetime.today().date()
    dte = (expiration_date - today).days

    contracts["Expiration"] = expiration
    contracts["DTE"] = dte
    contracts["mid"] = contracts.apply(_calculate_mid, axis=1)
    contracts["spread_pct"] = contracts.apply(_calculate_spread_pct, axis=1)
    contracts["QuoteQuality"] = contracts.apply(_quote_quality, axis=1)

    contracts["impliedVolatility"] = contracts["impliedVolatility"].apply(
        lambda value: _safe_float(value, 0.0)
    )

    contracts = contracts[
        (contracts["mid"] >= MIN_OPTION_PREMIUM)
        & (contracts["mid"] <= stock_price * MAX_PREMIUM_PCT_OF_STOCK)
        & (contracts["impliedVolatility"] > 0)
        & (contracts["QuoteQuality"] != "No Quote")
    ].copy()

    if contracts.empty:
        return contracts

    if option_type.lower() == "call":
        contracts["moneyness"] = contracts["strike"] / stock_price
    elif option_type.lower() == "put":
        contracts["moneyness"] = stock_price / contracts["strike"]
    else:
        raise ValueError("option_type must be 'call' or 'put'")

    contracts = contracts[
        (contracts["moneyness"] >= MIN_MONEYNESS)
        & (contracts["moneyness"] <= MAX_MONEYNESS)
    ].copy()

    if contracts.empty:
        return contracts

    greek_rows = []

    for _, contract in contracts.iterrows():
        greek_rows.append(
            calculate_greeks(
                stock_price=stock_price,
                strike=contract["strike"],
                days_to_expiration=dte,
                implied_volatility=contract["impliedVolatility"],
                option_type=option_type,
            )
        )

    greeks_df = pd.DataFrame(
        greek_rows,
        index=contracts.index,
    )

    contracts = pd.concat(
        [contracts, greeks_df],
        axis=1,
    )

    contracts["openInterest"] = contracts.get(
        "openInterest",
        0,
    ).fillna(0)

    contracts["volume"] = contracts.get(
        "volume",
        0,
    ).fillna(0)

    contracts["ContractScore"] = 0
    contracts["ContractScore"] += contracts["DTE"].apply(_score_dte)
    contracts["ContractScore"] += contracts["QuoteQuality"].apply(
        _score_quote_quality
    )
    contracts["ContractScore"] += contracts["openInterest"].apply(
        _score_open_interest
    )
    contracts["ContractScore"] += contracts["volume"].apply(_score_volume)
    contracts["ContractScore"] += contracts["moneyness"].apply(
        _score_moneyness
    )
    contracts["ContractScore"] += contracts["delta"].abs().apply(_score_delta)
    contracts["ContractScore"] += contracts.apply(
        lambda row: _score_theta(row["theta"], row["mid"]),
        axis=1,
    )

    contracts["PremiumPctOfStock"] = contracts["mid"] / stock_price
    contracts["ThetaDragPct"] = contracts["theta"].abs() / contracts["mid"]
    contracts["SelectionTier"] = contracts["ContractScore"].apply(
        _assign_selection_tier
    )

    return contracts.sort_values(
        "ContractScore",
        ascending=False,
    )