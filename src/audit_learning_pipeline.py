"""
Project Stonks
Learning Pipeline Audit

Sprint 30A

Purpose
-------
Validate that the learning pipeline is complete and internally
consistent before future learning is performed.
"""

import json
from pathlib import Path

import pandas as pd

from trade_journal import JOURNAL_PATH


def audit_learning_pipeline():

    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(
            f"Trade journal not found: {JOURNAL_PATH}"
        )

    journal = pd.read_csv(JOURNAL_PATH)

    print("\n========================================")
    print("Project Stonks Learning Pipeline Audit")
    print("========================================")

    required_columns = [
        "RecommendationID",
        "SnapshotPath",
        "SnapshotSchemaVersion",
        "TradeStatus",
        "OutcomeReviewed",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in journal.columns
    ]

    if missing_columns:
        print("\nFAIL")
        print(f"Missing columns: {missing_columns}")
        return False

    legacy_rows = 0
    snapshot_rows = 0

    duplicate_ids = 0
    missing_snapshot_paths = 0
    unreadable_snapshots = 0

    snapshot_paths = set()
    recommendation_ids = set()

    for _, row in journal.iterrows():

        schema_version = row.get("SnapshotSchemaVersion")

        #
        # Legacy / transitional records predate snapshot architecture.
        #
        if pd.isna(schema_version):
            legacy_rows += 1
            continue

        snapshot_rows += 1

        recommendation_id = row.get("RecommendationID")

        if pd.isna(recommendation_id):
            print("\nFAIL - Snapshot-era record missing RecommendationID.")
            return False

        if recommendation_id in recommendation_ids:
            duplicate_ids += 1
        else:
            recommendation_ids.add(recommendation_id)

        path = row.get("SnapshotPath")

        if pd.isna(path):
            missing_snapshot_paths += 1
            continue

        snapshot_file = Path(path)

        snapshot_paths.add(snapshot_file.resolve())

        if not snapshot_file.exists():
            missing_snapshot_paths += 1
            continue

        try:
            with open(snapshot_file, "r", encoding="utf-8") as f:
                json.load(f)
        except Exception:
            unreadable_snapshots += 1

    recommendations_dir = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "history"
        / "recommendations"
    )

    orphaned_snapshots = 0

    if recommendations_dir.exists():
        for snapshot in recommendations_dir.glob("*.json"):
            if snapshot.resolve() not in snapshot_paths:
                orphaned_snapshots += 1

    print(f"\nJournal Entries: {len(journal)}")
    print(f"Legacy / Transitional Rows: {legacy_rows}")
    print(f"Snapshot-era Rows: {snapshot_rows}")
    print(f"Duplicate Recommendation IDs: {duplicate_ids}")
    print(f"Missing Snapshot Paths: {missing_snapshot_paths}")
    print(f"Unreadable Snapshots: {unreadable_snapshots}")
    print(f"Orphaned Snapshots: {orphaned_snapshots}")

    passed = (
        duplicate_ids == 0
        and missing_snapshot_paths == 0
        and unreadable_snapshots == 0
        and orphaned_snapshots == 0
    )

    print("\n----------------------------------------")

    if passed:
        print("PASS - Learning pipeline validated.")

        if legacy_rows > 0:
            print(
                f"Note: {legacy_rows} historical records predate "
                "the snapshot architecture and were excluded "
                "from validation."
            )
    else:
        print("FAIL - Learning pipeline validation failed.")

    return passed


if __name__ == "__main__":
    audit_learning_pipeline()