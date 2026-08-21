"""Read-only audit of hindsight journal and immutable snapshots."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from data_quality import REQUIRED_HINDSIGHT_FIELDS, is_missing


def _coverage(records: list[dict]) -> dict:
    total = len(records)
    result = {}

    for field in REQUIRED_HINDSIGHT_FIELDS:
        present = sum(
            1
            for record in records
            if not is_missing(record.get(field))
        )
        result[field] = {
            "present": present,
            "missing": total - present,
        }

    return result


def read_journal_records(path: Path) -> tuple[list[dict], list[str]]:
    """Read a CSV while preserving awareness of duplicate columns."""

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        duplicate_columns = sorted(
            name
            for name, count in Counter(header).items()
            if count > 1
        )
        records = []

        for row in reader:
            record = {}

            for index, name in enumerate(header):
                value = row[index] if index < len(row) else None
                record.setdefault(name, value)

            records.append(record)

    return records, duplicate_columns


def find_case_collisions(columns: list[str]) -> list[list[str]]:
    """Find aliases such as ticker/Ticker without treating them as identical."""

    groups: dict[str, list[str]] = {}

    for column in columns:
        groups.setdefault(column.casefold(), []).append(column)

    return sorted(
        sorted(set(names))
        for names in groups.values()
        if len(set(names)) > 1
    )


def audit_repository(project_root: Path) -> dict:
    journal_path = project_root / "data" / "trade_journal.csv"
    snapshot_directory = (
        project_root / "data" / "History" / "recommendations"
    )
    with journal_path.open(newline="", encoding="utf-8-sig") as handle:
        journal_columns = next(csv.reader(handle))

    journal_records, duplicate_columns = read_journal_records(journal_path)
    snapshot_records = []
    invalid_snapshots = []

    for path in sorted(snapshot_directory.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                snapshot = json.load(handle)

            snapshot_records.append(
                snapshot.get("observation") or {}
            )
        except (OSError, json.JSONDecodeError, TypeError):
            invalid_snapshots.append(path.name)

    return {
        "journal": {
            "records": len(journal_records),
            "duplicate_columns": duplicate_columns,
            "case_collisions": find_case_collisions(journal_columns),
            "coverage": _coverage(journal_records),
        },
        "snapshots": {
            "records": len(snapshot_records),
            "invalid": invalid_snapshots,
            "coverage": _coverage(snapshot_records),
        },
        "policy": {
            "historical_records_rewritten": False,
            "incomplete_records_remain_evidence": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Project Stonks hindsight data without modifying it."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    args = parser.parse_args()
    print(
        json.dumps(
            audit_repository(args.project_root),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
