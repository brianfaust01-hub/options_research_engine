"""
Quick test for the Options Engine.
"""

import yfinance as yf

from options_engine import get_target_expirations, get_option_chain, score_contracts


ticker = "AAPL"
stock = yf.Ticker(ticker)
stock_price = stock.history(period="1d")["Close"].iloc[-1]

expirations = get_target_expirations(ticker=ticker, min_dte=30, max_dte=75)

print(f"\nTicker: {ticker}")
print(f"Stock price: {stock_price:.2f}")
print(f"Target expirations found: {len(expirations)}")
print(expirations[:5])

target_expiration = expirations[0]

calls = get_option_chain(ticker=ticker, expiration=target_expiration, option_type="call")

scored_calls = score_contracts(
    chain=calls,
    stock_price=stock_price,
    option_type="call",
)

print(f"\nTarget expiration: {target_expiration}")
print("\nTop scored calls:")
print(
    scored_calls[
        [
            "contractSymbol",
            "strike",
            "lastPrice",
            "bid",
            "ask",
            "mid",
            "spread_pct",
            "volume",
            "openInterest",
            "impliedVolatility",
            "moneyness",
            "ContractScore",
        ]
    ].head(10)
)