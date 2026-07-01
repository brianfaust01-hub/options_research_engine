"""
Project Stonks
Weekly Scan Runner
"""

from dataclasses import asdict
from datetime import datetime

import pandas as pd

from config import (
    PROJECT_NAME,
    VERSION,
    LOOKBACK_PERIOD,
    INTERVAL,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    TEST_MODE,
    TEST_TICKERS,
)

from data_loader import get_sp500_tickers, download_price_data
from indicators import calculate_indicators_for_ticker
from research_engine import evaluate_strategies
from opportunity_engine import evaluate_opportunities


def main():

    print(f"\n{PROJECT_NAME} v{VERSION}")
    print("=" * 40)

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    if TEST_MODE:
        print("\nTEST MODE ENABLED")
        tickers = TEST_TICKERS
    else:
        print("\nDownloading S&P 500 ticker list...")
        tickers = get_sp500_tickers()

    print(f"Tickers selected: {len(tickers)}")

    print("\nDownloading historical price data...")
    data = download_price_data(
        tickers=tickers,
        period=LOOKBACK_PERIOD,
        interval=INTERVAL,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_file = RAW_DATA_DIR / f"price_data_{timestamp}.csv"
    data.to_csv(raw_file)

    print("\nCalculating indicators...")
    indicator_rows = []

    for ticker in tickers:
        try:
            ticker_data = data[ticker].dropna()

            if len(ticker_data) < 200:
                continue

            indicator_rows.append(
                calculate_indicators_for_ticker(ticker, ticker_data)
            )

        except Exception as error:
            print(f"Skipping {ticker}: {error}")

    indicators_df = pd.DataFrame(indicator_rows)

    print("\nRunning research engine...")
    research_results = indicators_df.apply(
        evaluate_strategies,
        axis=1,
        result_type="expand",
    )

    indicators_df = pd.concat([indicators_df, research_results], axis=1)

    print("\nRunning opportunity engine...")
    trade_recommendations = indicators_df.apply(
        evaluate_opportunities,
        axis=1,
    )

    trades_df = pd.DataFrame(
        [asdict(trade) for trade in trade_recommendations]
    )

    processed_file = (
        PROCESSED_DATA_DIR
        / f"trade_recommendations_{timestamp}.csv"
    )

    trades_df.to_csv(processed_file, index=False)

    actionable_trades = trades_df[
        trades_df["action"] == "Evaluate Options"
    ].sort_values("confidence", ascending=False)

    watchlist = trades_df[
        trades_df["action"] == "Watch"
    ].sort_values("confidence", ascending=False)

    print("\nRun complete.")
    print(f"Raw rows: {data.shape[0]}")
    print(f"Raw columns: {data.shape[1]}")
    print(f"Stocks analyzed: {len(indicators_df)}")
    print(f"Trade recommendations generated: {len(trades_df)}")
    print(f"Actionable trades: {len(actionable_trades)}")
    print(f"Watchlist trades: {len(watchlist)}")
    print(f"Raw data saved to: {raw_file}")
    print(f"Trade recommendations saved to: {processed_file}")

    print("\n==================================================")
    print("Project Stonks Recommendations")
    print("==================================================")

    print("\nACTIONABLE TRADES\n")

    if actionable_trades.empty:
        print("No actionable trades found.")
    else:
        for _, trade in actionable_trades.head(10).iterrows():
            print("----------------------------------------")
            print(f"Ticker: {trade['ticker']}")
            print(f"Opportunity: {trade['opportunity_type']}")
            print(f"Action: {trade['action']}")
            print(f"Confidence: {trade['confidence']}")

            if trade["option_strategy"] is not None:
                print(f"Option Strategy: {trade['option_strategy']}")
                print(f"Expiration: {trade['expiration']}")
                print(f"Strike: {trade['strike']}")
                print(f"Premium: {trade['notes'][-1]}")
            else:
                print("Option Strategy: No suitable contract found")

            print(f"Notes: {trade['notes']}")

    print("\nWATCHLIST\n")

    if watchlist.empty:
        print("No watchlist opportunities found.")
    else:
        for _, trade in watchlist.head(10).iterrows():
            print("----------------------------------------")
            print(f"Ticker: {trade['ticker']}")
            print(f"Opportunity: {trade['opportunity_type']}")
            print(f"Action: {trade['action']}")
            print(f"Confidence: {trade['confidence']}")
            print(f"Notes: {trade['notes']}")

    print("\nSprint 14 complete.")


if __name__ == "__main__":
    main()