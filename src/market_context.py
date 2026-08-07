"""
Project Stonks
Market Context Engine

Sprint 22:
Evaluates SPY to determine broad market regime and risk mode.
"""

from __future__ import annotations

import pandas as pd

from schwab.market_data_client import (
    get_normalized_price_history,
)


def evaluate_market_context():

    try:
        candles = get_normalized_price_history(
            ticker="SPY",
            period_type="year",
            period=1,
            frequency_type="daily",
            frequency=1,
            need_extended_hours_data=False,
        )

        data = pd.DataFrame(
            candles
        )

    except Exception as error:
        print(
            "[market_context] WARNING: "
            "failed to retrieve SPY history "
            f"from Schwab: {error}"
        )

        data = pd.DataFrame()

    if (
        data.empty
        or "Close" not in data.columns
        or len(data) < 200
    ):
        return {
            "market_regime": "Unknown",
            "risk_mode": "Neutral",
            "allocation_bias": "Normal",
            "market_score": 50,
            "market_reasons": "Insufficient SPY data",
        }

    close = pd.to_numeric(
        data["Close"],
        errors="coerce",
    ).dropna()

    if len(close) < 200:
        return {
            "market_regime": "Unknown",
            "risk_mode": "Neutral",
            "allocation_bias": "Normal",
            "market_score": 50,
            "market_reasons": "Insufficient SPY data",
        }

    latest_close = close.iloc[-1]

    sma_50 = (
        close
        .rolling(50)
        .mean()
        .iloc[-1]
    )

    sma_200 = (
        close
        .rolling(200)
        .mean()
        .iloc[-1]
    )

    score = 0
    reasons = []

    if latest_close > sma_200:
        score += 40
        reasons.append(
            "SPY above 200-day SMA"
        )
    else:
        reasons.append(
            "SPY below 200-day SMA"
        )

    if latest_close > sma_50:
        score += 30
        reasons.append(
            "SPY above 50-day SMA"
        )
    else:
        reasons.append(
            "SPY below 50-day SMA"
        )

    if sma_50 > sma_200:
        score += 30
        reasons.append(
            "50-day SMA above 200-day SMA"
        )
    else:
        reasons.append(
            "50-day SMA below 200-day SMA"
        )

    if score >= 75:
        market_regime = "Bullish"
        risk_mode = "Normal"
        allocation_bias = "Risk On"

    elif score >= 45:
        market_regime = "Neutral"
        risk_mode = "Selective"
        allocation_bias = "Quality Only"

    else:
        market_regime = "Bearish"
        risk_mode = "Defensive"
        allocation_bias = "Reduce Risk"

    return {
        "market_regime": market_regime,
        "risk_mode": risk_mode,
        "allocation_bias": allocation_bias,
        "market_score": score,
        "market_reasons": "; ".join(
            reasons
        ),
    }