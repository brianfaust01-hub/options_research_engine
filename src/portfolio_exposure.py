"""
Project Stonks
Portfolio Exposure Engine

Sprint 25:
Classifies trades by sector, industry, and theme to identify hidden
portfolio concentration.
"""


EXPOSURE_MAP = {
    "AAPL": {
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "theme": "Mega Cap Tech",
    },
    "MSFT": {
        "sector": "Technology",
        "industry": "Software",
        "theme": "Mega Cap Tech",
    },
    "NVDA": {
        "sector": "Technology",
        "industry": "Semiconductors",
        "theme": "AI Chips",
    },
    "AMD": {
        "sector": "Technology",
        "industry": "Semiconductors",
        "theme": "AI Chips",
    },
    "AVGO": {
        "sector": "Technology",
        "industry": "Semiconductors",
        "theme": "AI Chips",
    },
    "MU": {
        "sector": "Technology",
        "industry": "Semiconductors",
        "theme": "Memory Chips",
    },
    "GOOGL": {
        "sector": "Communication Services",
        "industry": "Internet Content",
        "theme": "Mega Cap Tech",
    },
    "META": {
        "sector": "Communication Services",
        "industry": "Social Media",
        "theme": "Mega Cap Tech",
    },
    "AMZN": {
        "sector": "Consumer Discretionary",
        "industry": "E-Commerce",
        "theme": "Mega Cap Tech",
    },
    "TSLA": {
        "sector": "Consumer Discretionary",
        "industry": "Automobiles",
        "theme": "High Beta Growth",
    },
    "DDOG": {
        "sector": "Technology",
        "industry": "Software",
        "theme": "Cloud Software",
    },
    "FFIV": {
        "sector": "Technology",
        "industry": "Networking",
        "theme": "Enterprise Infrastructure",
    },
}


def classify_ticker(ticker: str):
    return EXPOSURE_MAP.get(
        ticker,
        {
            "sector": "Unknown",
            "industry": "Unknown",
            "theme": "Unknown",
        },
    )


def add_exposure_fields(trades_df):
    trades_df = trades_df.copy()

    trades_df["sector"] = trades_df["ticker"].apply(
        lambda ticker: classify_ticker(ticker)["sector"]
    )

    trades_df["industry"] = trades_df["ticker"].apply(
        lambda ticker: classify_ticker(ticker)["industry"]
    )

    trades_df["theme"] = trades_df["ticker"].apply(
        lambda ticker: classify_ticker(ticker)["theme"]
    )

    return trades_df


def summarize_allocated_exposure(trades_df):
    allocated = trades_df[
        trades_df["allocation_decision"] == "Allocate"
    ].copy()

    if allocated.empty:
        return {
            "sector_exposure": {},
            "industry_exposure": {},
            "theme_exposure": {},
            "warnings": [],
        }

    sector_counts = allocated["sector"].value_counts().to_dict()
    industry_counts = allocated["industry"].value_counts().to_dict()
    theme_counts = allocated["theme"].value_counts().to_dict()

    warnings = []

    for sector, count in sector_counts.items():
        if count >= 2:
            warnings.append(
                f"Concentrated sector exposure: {sector} ({count} trades)"
            )

    for industry, count in industry_counts.items():
        if count >= 2:
            warnings.append(
                f"Concentrated industry exposure: {industry} ({count} trades)"
            )

    for theme, count in theme_counts.items():
        if count >= 2:
            warnings.append(
                f"Concentrated theme exposure: {theme} ({count} trades)"
            )

    return {
        "sector_exposure": sector_counts,
        "industry_exposure": industry_counts,
        "theme_exposure": theme_counts,
        "warnings": warnings,
    }