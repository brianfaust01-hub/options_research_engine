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
from market_breadth import evaluate_market_breadth
from market_context import evaluate_market_context
from outcome_review import review_open_trades
from portfolio_allocator import allocate_portfolio
from portfolio_exposure import (
    add_exposure_fields,
    summarize_allocated_exposure,
)
from position_review import review_positions
from research_engine import evaluate_strategies
from opportunity_engine import evaluate_opportunities


def _has_valid_option_trade(trade) -> bool:
    return (
        pd.notna(trade.get("option_strategy"))
        and pd.notna(trade.get("expiration"))
        and pd.notna(trade.get("strike"))
        and pd.notna(trade.get("premium"))
        and pd.notna(trade.get("contracts"))
        and int(trade.get("contracts")) > 0
    )


def main():

    print(f"\n{PROJECT_NAME} v{VERSION}")
    print("=" * 40)

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("\nReviewing open paper trades...")
    review_result = review_open_trades()
    print(review_result["message"])

    print("\nEvaluating market context...")
    market_context = evaluate_market_context()
    print(f"Market Regime: {market_context['market_regime']}")
    print(f"Risk Mode: {market_context['risk_mode']}")
    print(f"Allocation Bias: {market_context['allocation_bias']}")
    print(f"Market Score: {market_context['market_score']}")
    print(f"Market Reasons: {market_context['market_reasons']}")

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

    print("\nEvaluating market breadth...")
    market_breadth = evaluate_market_breadth(indicators_df)

    print("\nRunning opportunity engine...")
    trade_recommendations = indicators_df.apply(
        evaluate_opportunities,
        axis=1,
    )

    trades_df = pd.DataFrame(
        [asdict(trade) for trade in trade_recommendations]
    )

    print("\nRunning portfolio allocator...")
    trades_df = allocate_portfolio(
        trades_df=trades_df,
        market_context=market_context,
    )

    print("\nEvaluating portfolio exposure...")
    trades_df = add_exposure_fields(trades_df)
    exposure_summary = summarize_allocated_exposure(trades_df)

    print("\nReviewing existing portfolio...")
    positions_df = review_positions(trades_df)

    trades_df["breadth_score"] = market_breadth["breadth_score"]
    trades_df["breadth_regime"] = market_breadth["breadth_regime"]
    trades_df["breadth_reasons"] = "; ".join(
        market_breadth["breadth_reasons"]
    )

    processed_file = (
        PROCESSED_DATA_DIR
        / f"trade_recommendations_{timestamp}.csv"
    )

    trades_df.to_csv(processed_file, index=False)

    actionable_trades = trades_df[
        trades_df["action"] == "Evaluate Options"
    ].sort_values(
        ["allocation_score", "confidence"],
        ascending=[False, False],
    )

    watchlist = trades_df[
        trades_df["action"] == "Watch"
    ].sort_values("confidence", ascending=False)

    allocated_trades = trades_df[
        trades_df["allocation_decision"] == "Allocate"
    ].sort_values("allocation_score", ascending=False)

    print("\nRun complete.")
    print(f"Raw rows: {data.shape[0]}")
    print(f"Raw columns: {data.shape[1]}")
    print(f"Stocks analyzed: {len(indicators_df)}")
    print(f"Trade recommendations generated: {len(trades_df)}")
    print(f"Actionable trades: {len(actionable_trades)}")
    print(f"Allocated trades: {len(allocated_trades)}")
    print(f"Watchlist trades: {len(watchlist)}")
    print(f"Raw data saved to: {raw_file}")
    print(f"Trade recommendations saved to: {processed_file}")

    print("\n==================================================")
    print("Project Stonks Recommendations")
    print("==================================================")

    print("\nMARKET CONTEXT\n")
    print(f"Market Regime: {market_context['market_regime']}")
    print(f"Risk Mode: {market_context['risk_mode']}")
    print(f"Allocation Bias: {market_context['allocation_bias']}")
    print(f"Market Score: {market_context['market_score']}")
    print(f"Reasons: {market_context['market_reasons']}")

    print("\nMARKET BREADTH\n")
    print(f"Breadth Regime: {market_breadth['breadth_regime']}")
    print(f"Breadth Score: {market_breadth['breadth_score']}")

    for reason in market_breadth["breadth_reasons"]:
        print(f"- {reason}")

    print("\nCURRENT POSITIONS\n")

    if positions_df.empty:
        print("No open positions.")
    else:
        for _, position in positions_df.iterrows():
            print("----------------------------------------")
            print(f"Ticker: {position['ticker']}")
            print(
                "Recommendation: "
                f"{position['position_recommendation']}"
            )
            print(f"Reason: {position['position_reason']}")
            print(f"Option Strategy: {position['option_strategy']}")
            print(f"Expiration: {position['expiration']}")
            print(f"Strike: {position['strike']}")
            print(f"Contracts: {position['contracts']}")
            print(f"Entry Price: ${position['entry_price']:.2f}")

            if pd.notna(position["current_price"]):
                print(f"Current Price: ${position['current_price']:.2f}")
                print(f"P/L: ${position['pnl_dollars']:.2f}")
                print(f"P/L %: {position['pnl_pct'] * 100:.2f}%")
            else:
                print("Current Price: unavailable")

            print(f"Profit Target: ${position['profit_target']:.2f}")
            print(f"Stop Loss: ${position['stop_loss']:.2f}")
            print(f"DTE: {position['dte']}")
            print(f"Time Stop DTE: {position['time_stop_dte']}")
            print(f"Latest Action: {position['latest_action']}")
            print(
                "Latest Allocation Decision: "
                f"{position['latest_allocation_decision']}"
            )
            print(
                "Latest Allocation Score: "
                f"{position['latest_allocation_score']}"
            )
            print(
                "Latest Trade Quality: "
                f"{position['latest_trade_quality']}"
            )
            print(f"Latest Grade: {position['latest_grade']}")

    print("\nPORTFOLIO EXPOSURE\n")

    if len(exposure_summary["sector_exposure"]) == 0:
        print("No allocated exposure.")
    else:
        print("Sector Exposure:")
        for sector, count in exposure_summary["sector_exposure"].items():
            print(f"- {sector}: {count}")

        print("\nIndustry Exposure:")
        for industry, count in exposure_summary["industry_exposure"].items():
            print(f"- {industry}: {count}")

        print("\nTheme Exposure:")
        for theme, count in exposure_summary["theme_exposure"].items():
            print(f"- {theme}: {count}")

        if len(exposure_summary["warnings"]) > 0:
            print("\nExposure Warnings:")
            for warning in exposure_summary["warnings"]:
                print(f"- {warning}")

    print("\nPORTFOLIO ALLOCATION\n")

    valid_allocated_trades = [
        trade
        for _, trade in allocated_trades.head(10).iterrows()
        if _has_valid_option_trade(trade)
    ]

    if len(valid_allocated_trades) == 0:
        print("No trades selected for allocation.")
    else:
        for trade in valid_allocated_trades:
            print("----------------------------------------")
            print(f"Rank: {int(trade['allocation_rank'])}")
            print(f"Ticker: {trade['ticker']}")
            print(f"Allocation Score: {trade['allocation_score']}")
            print(f"Decision: {trade['allocation_decision']}")
            print(f"Trade Quality: {trade['trade_quality_score']}")
            print(f"Grade: {trade['trade_quality_grade']}")
            print(f"Sector: {trade['sector']}")
            print(f"Industry: {trade['industry']}")
            print(f"Theme: {trade['theme']}")
            print(f"Opportunity: {trade['opportunity_type']}")
            print(f"Confidence: {trade['confidence']}")
            print(f"Option Strategy: {trade['option_strategy']}")
            print(f"Expiration: {trade['expiration']}")
            print(f"Strike: {trade['strike']}")
            print(f"Premium: ${trade['premium']:.2f}")
            print(f"Contracts: {int(trade['contracts'])}")
            print(f"Position Value: ${trade['position_value']:.2f}")
            print(f"Max Risk: ${trade['max_risk_dollars']:.2f}")
            print(
                "Position Size: "
                f"{trade['position_size_pct'] * 100:.2f}%"
            )

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
            print(f"Allocation Score: {trade['allocation_score']}")
            print(f"Allocation Decision: {trade['allocation_decision']}")
            print(f"Sector: {trade['sector']}")
            print(f"Industry: {trade['industry']}")
            print(f"Theme: {trade['theme']}")

            if pd.notna(trade.get("trade_quality_score")):
                print(f"Trade Quality: {trade['trade_quality_score']}")

            if pd.notna(trade.get("trade_quality_grade")):
                print(f"Grade: {trade['trade_quality_grade']}")

            if _has_valid_option_trade(trade):
                print(f"Option Strategy: {trade['option_strategy']}")
                print(f"Expiration: {trade['expiration']}")
                print(f"Strike: {trade['strike']}")
                print(f"Premium: ${trade['premium']:.2f}")
                print(f"Contracts: {int(trade['contracts'])}")
                print(f"Position Value: ${trade['position_value']:.2f}")
                print(f"Max Risk: ${trade['max_risk_dollars']:.2f}")
                print(
                    "Position Size: "
                    f"{trade['position_size_pct'] * 100:.2f}%"
                )
            else:
                print("Option Strategy: No suitable executable contract found")

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
            print(f"Sector: {trade['sector']}")
            print(f"Industry: {trade['industry']}")
            print(f"Theme: {trade['theme']}")
            print(f"Notes: {trade['notes']}")

    print("\nSprint 27 complete.")


if __name__ == "__main__":
    main()