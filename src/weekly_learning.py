"""
Project Stonks
Weekly Learning

Sprint 30A

Purpose
-------
Validate that the learning pipeline is complete and produce a basic
weekly learning summary.

Future sprints will expand this into:
- Insight generation
- Experiment queue
- Strategy evaluation
- Research accuracy scoring
"""

from pathlib import Path

import pandas as pd


JOURNAL_PATH = Path("data/trade_journal.csv")


def generate_weekly_learning_report():
    """
    Validate the learning dataset and return a summary.

    Returns
    -------
    dict
    """

    if not JOURNAL_PATH.exists():
        return {
            "status": "ERROR",
            "message": "Trade journal not found.",
        }

    journal = pd.read_csv(JOURNAL_PATH)

    if journal.empty:
        return {
            "status": "ERROR",
            "message": "Trade journal is empty.",
        }

    required_columns = [
        "RecommendationID",
        "TradeStatus",
        "OutcomeReviewed",
        "SnapshotPath",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in journal.columns
    ]

    if missing_columns:
        return {
            "status": "ERROR",
            "message": "Journal missing required columns.",
            "missing_columns": missing_columns,
        }

    missing_snapshots = 0

    for path in journal["SnapshotPath"]:
        if pd.isna(path):
            missing_snapshots += 1
            continue

        if not Path(path).exists():
            missing_snapshots += 1

    total = len(journal)

    reviewed = int(journal["OutcomeReviewed"].fillna(False).sum())

    pending = total - reviewed

    by_status = (
        journal["TradeStatus"]
        .value_counts(dropna=False)
        .to_dict()
    )

    report = {
        "status": "PASS" if missing_snapshots == 0 else "WARNING",
        "total_recommendations": total,
        "reviewed": reviewed,
        "pending_review": pending,
        "missing_snapshots": missing_snapshots,
        "trade_status_breakdown": by_status,
    }

    print("\n==============================")
    print("Weekly Learning Summary")
    print("==============================")
    print(f"Recommendations: {total}")
    print(f"Reviewed: {reviewed}")
    print(f"Pending Review: {pending}")
    print(f"Missing Snapshots: {missing_snapshots}")

    print("\nTrade Status")

    for status, count in by_status.items():
        print(f"- {status}: {count}")

    return report


if __name__ == "__main__":
    generate_weekly_learning_report()