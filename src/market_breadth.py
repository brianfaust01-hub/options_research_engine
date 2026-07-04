"""
Project Stonks
Market Breadth Engine

Measures overall market participation using all scanned stocks.
"""

import pandas as pd


def evaluate_market_breadth(indicators_df: pd.DataFrame):

    total = len(indicators_df)

    if total == 0:
        return {
            "breadth_score": 0,
            "breadth_regime": "Unknown",
            "breadth_reasons": [],
        }

    pct_above_20 = (
        indicators_df["Above_SMA_20"].sum() / total
    )

    pct_above_50 = (
        indicators_df["Above_SMA_50"].sum() / total
    )

    pct_above_200 = (
        indicators_df["Above_SMA_200"].sum() / total
    )

    pct_macd = (
        indicators_df["MACD_Bullish"].sum() / total
    )

    pct_bullish = (
        (indicators_df["Direction"] == "Bullish").sum() / total
    )

    score = 0

    score += pct_above_20 * 20
    score += pct_above_50 * 25
    score += pct_above_200 * 30
    score += pct_macd * 10
    score += pct_bullish * 15

    score = round(score)

    if score >= 80:
        regime = "Strong Breadth"

    elif score >= 65:
        regime = "Healthy Breadth"

    elif score >= 50:
        regime = "Neutral Breadth"

    elif score >= 35:
        regime = "Weak Breadth"

    else:
        regime = "Very Weak Breadth"

    reasons = [
        f"{pct_above_20:.0%} above 20 SMA",
        f"{pct_above_50:.0%} above 50 SMA",
        f"{pct_above_200:.0%} above 200 SMA",
        f"{pct_macd:.0%} bullish MACD",
        f"{pct_bullish:.0%} bullish research signals",
    ]

    return {
        "breadth_score": score,
        "breadth_regime": regime,
        "breadth_reasons": reasons,
    }