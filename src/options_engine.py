"""
Project Stonks - Options Engine
v0.3.0-alpha

Purpose:
- Fetch option expirations and chains safely from yfinance
- Prevent one ticker timeout from crashing the full scan
- Score option contracts for liquidity, pricing, moneyness, and execution
- Preserve the interface expected by option_selector.py
"""

from __future__ import annotations

import math
import time
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# Safe conversion helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or pd.isna(value):
            return None

        return int(value)

    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Expiration helpers
# ---------------------------------------------------------------------------

def days_to_expiration(expiration: str) -> Optional[int]:
    try:
        expiration_date = datetime.strptime(
            str(expiration),
            "%Y-%m-%d",
        ).date()

        return (expiration_date - date.today()).days

    except (TypeError, ValueError):
        return None


def _days_to_expiration(expiration: str) -> Optional[int]:
    """
    Internal compatibility alias.
    """
    return days_to_expiration(expiration)


def get_option_expirations(
    ticker: str,
    max_retries: int = 1,
    retry_sleep_seconds: float = 1.0,
) -> list[str]:
    """
    Fetch all available option expirations.

    Any network, curl, timeout, or yfinance error returns an empty list so one
    ticker cannot crash the entire S&P 500 scan.
    """
    ticker = str(ticker).upper().strip()

    for attempt in range(max_retries + 1):
        try:
            stock = yf.Ticker(ticker)
            expirations = list(stock.options or [])

            return expirations

        except Exception as error:
            print(
                f"[options_engine] WARNING: failed to fetch expirations for "
                f"{ticker} on attempt {attempt + 1}/{max_retries + 1}: "
                f"{type(error).__name__}: {error}"
            )

            if attempt < max_retries:
                time.sleep(retry_sleep_seconds)

    return []


def get_target_expirations(
    ticker: str,
    min_dte: int = 30,
    max_dte: int = 120,
    max_expirations: int = 8,
) -> list[str]:
    """
    Return expirations in the broad research-mode DTE window.

    option_selector.py applies the more precise horizon-fit score based on the
    expected holding period. This function intentionally supplies a wider
    expiration universe for that ranking step.
    """
    expirations = get_option_expirations(ticker)

    target_expirations: list[str] = []

    for expiration in expirations:
        dte = days_to_expiration(expiration)

        if dte is None:
            continue

        if min_dte <= dte <= max_dte:
            target_expirations.append(expiration)

    target_expirations.sort(
        key=lambda expiration: days_to_expiration(expiration) or 9999
    )

    return target_expirations[:max_expirations]


# ---------------------------------------------------------------------------
# Option-chain retrieval
# ---------------------------------------------------------------------------

def get_option_chain(
    ticker: str,
    expiration: str,
    option_type: str,
    max_retries: int = 1,
    retry_sleep_seconds: float = 1.0,
) -> pd.DataFrame:
    """
    Fetch one call or put chain.

    Returns an empty DataFrame on any error.
    """
    ticker = str(ticker).upper().strip()
    option_type = str(option_type).lower().strip()

    for attempt in range(max_retries + 1):
        try:
            stock = yf.Ticker(ticker)
            option_chain = stock.option_chain(expiration)

            if option_type in {"call", "calls"}:
                chain = option_chain.calls.copy()

            elif option_type in {"put", "puts"}:
                chain = option_chain.puts.copy()

            else:
                print(
                    f"[options_engine] WARNING: unsupported option type "
                    f"'{option_type}' for {ticker}"
                )
                return pd.DataFrame()

            return chain

        except Exception as error:
            print(
                f"[options_engine] WARNING: failed to fetch option chain for "
                f"{ticker} {expiration} {option_type} on attempt "
                f"{attempt + 1}/{max_retries + 1}: "
                f"{type(error).__name__}: {error}"
            )

            if attempt < max_retries:
                time.sleep(retry_sleep_seconds)

    return pd.DataFrame()


def get_option_chain_safe(
    ticker: str,
    expiration: str,
    option_type: str,
    max_retries: int = 1,
    retry_sleep_seconds: float = 1.0,
) -> pd.DataFrame:
    """
    Compatibility alias.
    """
    return get_option_chain(
        ticker=ticker,
        expiration=expiration,
        option_type=option_type,
        max_retries=max_retries,
        retry_sleep_seconds=retry_sleep_seconds,
    )


# ---------------------------------------------------------------------------
# Pricing helpers
# ---------------------------------------------------------------------------

def calculate_mid_price(row: pd.Series) -> Optional[float]:
    bid = _safe_float(row.get("bid")) or 0.0
    ask = _safe_float(row.get("ask")) or 0.0
    last_price = _safe_float(row.get("lastPrice")) or 0.0

    if bid > 0 and ask > 0 and ask >= bid:
        return round((bid + ask) / 2, 4)

    if last_price > 0:
        return round(last_price, 4)

    return None


def calculate_spread_pct(row: pd.Series) -> Optional[float]:
    bid = _safe_float(row.get("bid")) or 0.0
    ask = _safe_float(row.get("ask")) or 0.0

    if bid <= 0 or ask <= 0 or ask < bid:
        return None

    mid = (bid + ask) / 2

    if mid <= 0:
        return None

    return (ask - bid) / mid


def _calculate_moneyness(
    strike: float,
    stock_price: float,
    option_type: str,
) -> float:
    """
    Positive values are in the money.
    Negative values are out of the money.
    """
    if stock_price <= 0:
        return 0.0

    if option_type == "put":
        return (strike - stock_price) / stock_price

    return (stock_price - strike) / stock_price


def _estimate_delta(
    strike: float,
    stock_price: float,
    option_type: str,
) -> float:
    """
    Lightweight research-mode delta proxy.

    yfinance chains generally do not provide Greeks. This proxy is used only
    for relative contract ranking, not precise pricing or risk management.
    """
    if stock_price <= 0:
        return 0.0

    strike_distance = (strike - stock_price) / stock_price

    call_delta = 0.50 - (strike_distance * 2.5)
    call_delta = max(0.10, min(0.90, call_delta))

    if option_type == "put":
        return round(call_delta - 1.0, 4)

    return round(call_delta, 4)


def _estimate_theta(
    premium: float,
    dte: int,
) -> float:
    """
    Lightweight daily theta proxy used for relative ranking.
    """
    if premium <= 0 or dte <= 0:
        return 0.0

    estimated_daily_decay = -(premium / max(dte, 1)) * 0.35

    return round(estimated_daily_decay, 4)


# ---------------------------------------------------------------------------
# Contract scoring
# ---------------------------------------------------------------------------

def _quote_quality(
    bid: float,
    ask: float,
    mid: float,
    spread_pct: Optional[float],
) -> str:
    if bid <= 0 or ask <= 0 or mid <= 0:
        return "Poor"

    if spread_pct is None:
        return "Poor"

    if spread_pct <= 0.05:
        return "Excellent"

    if spread_pct <= 0.10:
        return "Good"

    if spread_pct <= 0.20:
        return "Acceptable"

    return "Poor"


def _selection_tier(contract_score: float) -> str:
    if contract_score >= 85:
        return "A"

    if contract_score >= 75:
        return "B"

    if contract_score >= 65:
        return "C"

    return "Reject"


def _calculate_contract_score(
    row: pd.Series,
    stock_price: float,
    option_type: str,
) -> float:
    """
    Produce a 0-100 contract score.

    Components:
    - Quote validity and spread
    - Open interest
    - Volume
    - Strike/moneyness fit
    - Premium efficiency
    - Implied-volatility sanity
    """
    score = 0.0

    bid = _safe_float(row.get("bid")) or 0.0
    ask = _safe_float(row.get("ask")) or 0.0
    mid = _safe_float(row.get("mid")) or 0.0
    strike = _safe_float(row.get("strike")) or 0.0
    spread_pct = _safe_float(row.get("spread_pct"))
    volume = _safe_int(row.get("volume")) or 0
    open_interest = _safe_int(row.get("openInterest")) or 0
    implied_volatility = (
        _safe_float(row.get("impliedVolatility")) or 0.0
    )

    # Quote quality: up to 30 points
    if bid > 0 and ask > 0 and ask >= bid and mid > 0:
        score += 10

        if spread_pct is not None:
            if spread_pct <= 0.05:
                score += 20
            elif spread_pct <= 0.10:
                score += 17
            elif spread_pct <= 0.15:
                score += 13
            elif spread_pct <= 0.20:
                score += 9
            elif spread_pct <= 0.30:
                score += 4

    # Open interest: up to 20 points
    if open_interest >= 2000:
        score += 20
    elif open_interest >= 1000:
        score += 18
    elif open_interest >= 500:
        score += 15
    elif open_interest >= 250:
        score += 12
    elif open_interest >= 100:
        score += 8
    elif open_interest >= 25:
        score += 4

    # Daily volume: up to 15 points
    if volume >= 1000:
        score += 15
    elif volume >= 500:
        score += 13
    elif volume >= 200:
        score += 11
    elif volume >= 100:
        score += 9
    elif volume >= 25:
        score += 6
    elif volume > 0:
        score += 3

    # Moneyness/strike fit: up to 20 points
    if stock_price > 0 and strike > 0:
        strike_distance = abs(strike - stock_price) / stock_price

        if strike_distance <= 0.02:
            score += 20
        elif strike_distance <= 0.05:
            score += 17
        elif strike_distance <= 0.08:
            score += 13
        elif strike_distance <= 0.12:
            score += 8
        elif strike_distance <= 0.18:
            score += 3

        # Avoid ranking deeply ITM contracts too highly.
        moneyness = _calculate_moneyness(
            strike=strike,
            stock_price=stock_price,
            option_type=option_type,
        )

        if moneyness > 0.15:
            score -= 8

    # Premium efficiency: up to 10 points
    if stock_price > 0 and mid > 0:
        premium_pct = mid / stock_price

        if 0.01 <= premium_pct <= 0.08:
            score += 10
        elif premium_pct <= 0.12:
            score += 7
        elif premium_pct <= 0.18:
            score += 3
        elif premium_pct > 0.25:
            score -= 5

    # IV sanity: up to 5 points
    if 0.10 <= implied_volatility <= 0.80:
        score += 5
    elif implied_volatility <= 1.20:
        score += 2
    elif implied_volatility > 1.50:
        score -= 5

    return round(max(0.0, min(100.0, score)), 2)


def score_contracts(
    chain: pd.DataFrame,
    stock_price: float,
    option_type: str,
    expiration: str,
) -> pd.DataFrame:
    """
    Score and enrich one option chain.

    This signature intentionally matches option_selector.py exactly.

    Required selector output columns include:
    - Expiration
    - DTE
    - mid
    - spread_pct
    - QuoteQuality
    - Executable
    - moneyness
    - delta
    - theta
    - ContractScore
    - SelectionTier
    - PremiumPctOfStock
    """
    if chain is None or chain.empty:
        return pd.DataFrame()

    try:
        stock_price = float(stock_price)
    except (TypeError, ValueError):
        return pd.DataFrame()

    if stock_price <= 0:
        return pd.DataFrame()

    option_type = str(option_type).lower().strip()

    if option_type not in {"call", "put"}:
        return pd.DataFrame()

    dte = days_to_expiration(expiration)

    if dte is None or dte <= 0:
        return pd.DataFrame()

    scored = chain.copy()

    required_columns = [
        "contractSymbol",
        "strike",
        "bid",
        "ask",
        "lastPrice",
        "volume",
        "openInterest",
        "impliedVolatility",
    ]

    for column in required_columns:
        if column not in scored.columns:
            scored[column] = pd.NA

    numeric_columns = [
        "strike",
        "bid",
        "ask",
        "lastPrice",
        "volume",
        "openInterest",
        "impliedVolatility",
    ]

    for column in numeric_columns:
        scored[column] = pd.to_numeric(
            scored[column],
            errors="coerce",
        )

    scored["Expiration"] = str(expiration)
    scored["DTE"] = int(dte)

    scored["mid"] = scored.apply(
        calculate_mid_price,
        axis=1,
    )

    scored["spread_pct"] = scored.apply(
        calculate_spread_pct,
        axis=1,
    )

    scored["moneyness"] = scored["strike"].apply(
        lambda strike: (
            _calculate_moneyness(
                strike=float(strike),
                stock_price=stock_price,
                option_type=option_type,
            )
            if pd.notna(strike)
            else None
        )
    )

    scored["delta"] = scored["strike"].apply(
        lambda strike: (
            _estimate_delta(
                strike=float(strike),
                stock_price=stock_price,
                option_type=option_type,
            )
            if pd.notna(strike)
            else None
        )
    )

    scored["theta"] = scored["mid"].apply(
        lambda premium: (
            _estimate_theta(
                premium=float(premium),
                dte=dte,
            )
            if premium is not None and pd.notna(premium)
            else None
        )
    )

    scored["PremiumPctOfStock"] = scored["mid"].apply(
        lambda premium: (
            float(premium) / stock_price
            if premium is not None
            and pd.notna(premium)
            and stock_price > 0
            else None
        )
    )

    scored["QuoteQuality"] = scored.apply(
        lambda row: _quote_quality(
            bid=_safe_float(row.get("bid")) or 0.0,
            ask=_safe_float(row.get("ask")) or 0.0,
            mid=_safe_float(row.get("mid")) or 0.0,
            spread_pct=_safe_float(row.get("spread_pct")),
        ),
        axis=1,
    )

    scored["ContractScore"] = scored.apply(
        lambda row: _calculate_contract_score(
            row=row,
            stock_price=stock_price,
            option_type=option_type,
        ),
        axis=1,
    )

    scored["SelectionTier"] = scored["ContractScore"].apply(
        _selection_tier
    )

    # Quote-level execution quality. option_selector.py later replaces this
    # with portfolio affordability.
    scored["Executable"] = (
        scored["mid"].notna()
        & (scored["mid"] > 0)
        & scored["bid"].notna()
        & scored["ask"].notna()
        & (scored["bid"] > 0)
        & (scored["ask"] >= scored["bid"])
    )

    # Remove unusable contracts but preserve a broad enough universe for
    # horizon-aware scoring and portfolio affordability.
    scored = scored[
        scored["contractSymbol"].notna()
        & scored["strike"].notna()
        & scored["mid"].notna()
        & (scored["mid"] > 0)
        & scored["Executable"]
    ].copy()

    if scored.empty:
        return scored

    scored = scored.sort_values(
        [
            "ContractScore",
            "openInterest",
            "volume",
            "spread_pct",
        ],
        ascending=[False, False, False, True],
        na_position="last",
    )

    return scored.reset_index(drop=True)