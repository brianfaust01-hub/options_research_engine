"""
Project Stonks
Scoring Engine

Determines bullish and bearish scores for each stock.
"""


def bullish_score(row):

    score = 0

    # ------------------------
    # Trend (30)
    # ------------------------

    if row["Above_SMA_20"]:
        score += 10

    if row["Above_SMA_50"]:
        score += 10

    if row["Above_SMA_200"]:
        score += 10

    # ------------------------
    # Momentum (25)
    # ------------------------

    if row["MACD_Bullish"]:
        score += 10

    if 50 <= row["RSI_14"] <= 65:
        score += 15

    elif 65 < row["RSI_14"] <= 70:
        score += 10

    return score


def bearish_score(row):

    score = 0

    # ------------------------
    # Trend
    # ------------------------

    if not row["Above_SMA_20"]:
        score += 10

    if not row["Above_SMA_50"]:
        score += 10

    if not row["Above_SMA_200"]:
        score += 10

    # ------------------------
    # Momentum
    # ------------------------

    if not row["MACD_Bullish"]:
        score += 10

    if 30 <= row["RSI_14"] <= 50:
        score += 15

    return score