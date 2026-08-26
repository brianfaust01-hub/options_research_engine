"""
Project Stonks
Indicators

Calculates technical indicators for each ticker.
"""

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import AverageTrueRange


def calculate_indicators_for_ticker(ticker: str, price_data: pd.DataFrame) -> dict:
    close = price_data["Close"]
    high = price_data["High"]
    low = price_data["Low"]
    volume = price_data["Volume"]

    latest_close = close.iloc[-1]

    sma_20 = close.rolling(window=20).mean().iloc[-1]
    sma_50 = close.rolling(window=50).mean().iloc[-1]
    sma_200 = close.rolling(window=200).mean().iloc[-1]

    rsi = RSIIndicator(close=close, window=14).rsi().iloc[-1]

    macd_calc = MACD(close=close)
    macd_value = macd_calc.macd().iloc[-1]
    macd_signal = macd_calc.macd_signal().iloc[-1]

    atr = AverageTrueRange(
        high=high,
        low=low,
        close=close,
        window=14
    ).average_true_range().iloc[-1]

    avg_volume_20 = volume.rolling(window=20).mean().iloc[-1]
    returns = close.pct_change()
    return_1d = returns.iloc[-1]
    return_3d = close.iloc[-1] / close.iloc[-4] - 1
    return_5d = close.iloc[-1] / close.iloc[-6] - 1
    prior_return_average = returns.iloc[-5:-1].mean()
    atr_pct = atr / latest_close if latest_close else 0
    price_acceleration_atr = (
        (return_1d - prior_return_average) / atr_pct
        if atr_pct > 0 else 0
    )
    volume_ratio_20 = volume.iloc[-1] / avg_volume_20 if avg_volume_20 else 0
    prior_20_high = close.iloc[-21:-1].max()
    prior_20_low = close.iloc[-21:-1].min()
    fresh_breakout_20 = bool(latest_close > prior_20_high)
    fresh_breakdown_20 = bool(latest_close < prior_20_low)

    above_sma_20 = close > close.rolling(window=20).mean()
    current_side = bool(above_sma_20.iloc[-1])
    signal_age_days = 0
    for value in reversed(above_sma_20.iloc[-20:].tolist()):
        if bool(value) != current_side:
            break
        signal_age_days += 1

    return {
        "Ticker": ticker,
        "Close": latest_close,
        "SMA_20": sma_20,
        "SMA_50": sma_50,
        "SMA_200": sma_200,
        "RSI_14": rsi,
        "MACD": macd_value,
        "MACD_Signal": macd_signal,
        "ATR_14": atr,
        "Avg_Volume_20": avg_volume_20,
        "Return1D": return_1d,
        "Return3D": return_3d,
        "Return5D": return_5d,
        "PriceAccelerationATR": price_acceleration_atr,
        "VolumeRatio20": volume_ratio_20,
        "FreshBreakout20": fresh_breakout_20,
        "FreshBreakdown20": fresh_breakdown_20,
        "SignalAgeDays": signal_age_days,
        "Above_SMA_20": latest_close > sma_20,
        "Above_SMA_50": latest_close > sma_50,
        "Above_SMA_200": latest_close > sma_200,
        "MACD_Bullish": macd_value > macd_signal
    }
