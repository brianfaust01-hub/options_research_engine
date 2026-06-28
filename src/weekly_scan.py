"""
Project Stonks
Weekly Scan Runner
"""

from datetime import datetime

from config import PROJECT_NAME, VERSION, LOOKBACK_PERIOD, INTERVAL, RAW_DATA_DIR
from data_loader import get_sp500_tickers, download_price_data


def main():
    print(f"\n{PROJECT_NAME} v{VERSION}")
    print("=" * 40)

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("\nDownloading S&P 500 ticker list...")
    tickers = get_sp500_tickers()
    print(f"Tickers found: {len(tickers)}")

    print("\nDownloading historical price data...")
    data = download_price_data(
        tickers=tickers,
        period=LOOKBACK_PERIOD,
        interval=INTERVAL
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RAW_DATA_DIR / f"sp500_price_data_{timestamp}.csv"

    data.to_csv(output_file)

    print("\nDownload complete.")
    print(f"Rows: {data.shape[0]}")
    print(f"Columns: {data.shape[1]}")
    print(f"Saved to: {output_file}")

    print("\nSprint 1 complete.")


if __name__ == "__main__":
    main()