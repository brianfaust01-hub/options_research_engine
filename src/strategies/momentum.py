"""
Project Stonks
Momentum Research Module
"""

from models.research_result import ResearchResult


def _score_rsi_bullish(rsi: float) -> tuple[int, str]:
    if 50 <= rsi <= 60:
        return 20, "RSI in ideal bullish range"
    if 60 < rsi <= 65:
        return 15, "RSI bullish but warming up"
    if 65 < rsi <= 70:
        return 8, "RSI bullish but near overbought"
    if 45 <= rsi < 50:
        return 5, "RSI improving but not bullish yet"
    return 0, "RSI not favorable for bullish momentum"


def _score_rsi_bearish(rsi: float) -> tuple[int, str]:
    if 40 <= rsi <= 50:
        return 20, "RSI in ideal bearish range"
    if 30 <= rsi < 40:
        return 12, "RSI bearish but approaching oversold"
    if 50 < rsi <= 55:
        return 5, "RSI weakening but not bearish yet"
    return 0, "RSI not favorable for bearish momentum"


def evaluate_momentum(row) -> ResearchResult:
    bullish_score = 0
    bearish_score = 0
    bullish_reasons = []
    bearish_reasons = []

    close = row["Close"]

    if row["Above_SMA_20"]:
        bullish_score += 8
        bullish_reasons.append("Above 20-day SMA")
    else:
        bearish_score += 8
        bearish_reasons.append("Below 20-day SMA")

    if row["Above_SMA_50"]:
        bullish_score += 10
        bullish_reasons.append("Above 50-day SMA")
    else:
        bearish_score += 10
        bearish_reasons.append("Below 50-day SMA")

    if row["Above_SMA_200"]:
        bullish_score += 12
        bullish_reasons.append("Above 200-day SMA")
    else:
        bearish_score += 12
        bearish_reasons.append("Below 200-day SMA")

    pct_from_sma_20 = (close - row["SMA_20"]) / row["SMA_20"]
    pct_from_sma_50 = (close - row["SMA_50"]) / row["SMA_50"]

    if 0.00 <= pct_from_sma_20 <= 0.05:
        bullish_score += 10
        bullish_reasons.append("Healthy distance above 20-day SMA")
    elif pct_from_sma_20 > 0.08:
        bullish_score -= 5
        bullish_reasons.append("Extended above 20-day SMA")

    if 0.00 <= pct_from_sma_50 <= 0.10:
        bullish_score += 10
        bullish_reasons.append("Healthy distance above 50-day SMA")
    elif pct_from_sma_50 > 0.15:
        bullish_score -= 5
        bullish_reasons.append("Extended above 50-day SMA")

    if -0.05 <= pct_from_sma_20 < 0:
        bearish_score += 10
        bearish_reasons.append("Healthy distance below 20-day SMA")
    elif pct_from_sma_20 < -0.08:
        bearish_score -= 5
        bearish_reasons.append("Extended below 20-day SMA")

    if -0.10 <= pct_from_sma_50 < 0:
        bearish_score += 10
        bearish_reasons.append("Healthy distance below 50-day SMA")
    elif pct_from_sma_50 < -0.15:
        bearish_score -= 5
        bearish_reasons.append("Extended below 50-day SMA")

    if row["MACD_Bullish"]:
        bullish_score += 10
        bullish_reasons.append("MACD bullish")
    else:
        bearish_score += 10
        bearish_reasons.append("MACD bearish")

    rsi = row["RSI_14"]

    rsi_bull_score, rsi_bull_reason = _score_rsi_bullish(rsi)
    bullish_score += rsi_bull_score
    bullish_reasons.append(rsi_bull_reason)

    rsi_bear_score, rsi_bear_reason = _score_rsi_bearish(rsi)
    bearish_score += rsi_bear_score
    bearish_reasons.append(rsi_bear_reason)

    if row["Avg_Volume_20"] >= 5_000_000:
        bullish_score += 10
        bearish_score += 10
        bullish_reasons.append("High liquidity")
        bearish_reasons.append("High liquidity")
    elif row["Avg_Volume_20"] >= 1_000_000:
        bullish_score += 5
        bearish_score += 5
        bullish_reasons.append("Acceptable liquidity")
        bearish_reasons.append("Acceptable liquidity")

    bullish_score = max(0, bullish_score)
    bearish_score = max(0, bearish_score)

    if bullish_score >= bearish_score:
        return ResearchResult(
            module="Momentum",
            signal="Bullish",
            confidence=bullish_score,
            trend=0,
            momentum=bullish_score,
            risk=0,
            liquidity=0,
            reasons=bullish_reasons,
        )

    return ResearchResult(
        module="Momentum",
        signal="Bearish",
        confidence=bearish_score,
        trend=0,
        momentum=bearish_score,
        risk=0,
        liquidity=0,
        reasons=bearish_reasons,
    )