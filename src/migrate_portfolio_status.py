"""
Project Stonks
Portfolio Status Migration

Sprint 30A

One-time migration to introduce PortfolioStatus.

All historical recommendations are marked NOT_ALLOCATED.

The current open paper trades are then marked OPEN.
"""

from pathlib import Path

import pandas as pd


JOURNAL_PATH = Path("data/trade_journal.csv")

#
# Update these to match your current open paper positions.
#
OPEN_POSITIONS = [
    {
        "ticker": "IBKR",
        "expiration": "2026-09-18",
        "strike": 100.0,
    },
    {
        "ticker": "UPS",
        "expiration": "2026-08-21",
        "strike": 115.0,
    },
    {
        "ticker": "BAC",
        "expiration": "2026-09-18",
        "strike": 62.50,
    },
    {
        "ticker": "BNY",
        "expiration": "2026-09-18",
        "strike": 155.0,
    },
    {
        "ticker": "MO",
        "expiration": "2026-09-18",
        "strike": 72.50,
    },
    {
        "ticker": "PCG",
        "expiration": "2026-09-18",
        "strike": 17.0,
    }
    # Add remaining open trades here
]


def main():

    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(JOURNAL_PATH)

    journal = pd.read_csv(JOURNAL_PATH)

    journal["PortfolioStatus"] = "NOT_ALLOCATED"

    updated = 0

    for position in OPEN_POSITIONS:

        mask = (
            (journal["ticker"] == position["ticker"])
            &
            (journal["expiration"] == position["expiration"])
            &
            (journal["strike"].astype(float) == float(position["strike"]))
        )

        count = mask.sum()

        if count == 0:
            print(f"WARNING - Position not found: {position}")
            continue

        journal.loc[mask, "PortfolioStatus"] = "OPEN"
        updated += count

    journal.to_csv(JOURNAL_PATH, index=False)

    print()
    print("Migration complete.")
    print(f"Rows marked OPEN: {updated}")
    print(f"All other rows marked NOT_ALLOCATED.")


if __name__ == "__main__":
    main()