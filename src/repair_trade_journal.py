"""
Project Stonks
Trade Journal Repair Utility

Repairs a journal truncated during its final CSV row.

The original corrupted file is preserved as a timestamped backup.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
JOURNAL_PATH = PROJECT_ROOT / "data" / "trade_journal.csv"


def _can_read_csv(content: bytes) -> bool:
    try:
        pd.read_csv(BytesIO(content))
        return True
    except Exception:
        return False


def repair_trade_journal() -> None:
    if not JOURNAL_PATH.exists():
        raise FileNotFoundError(
            f"Trade journal not found: {JOURNAL_PATH}"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_path = (
        JOURNAL_PATH.parent
        / f"trade_journal_corrupt_{timestamp}.csv"
    )

    shutil.copy2(
        JOURNAL_PATH,
        backup_path,
    )

    original_bytes = JOURNAL_PATH.read_bytes()
    lines = original_bytes.splitlines(keepends=True)

    if not lines:
        raise ValueError("Trade journal is empty.")

    removed_lines = 0
    repaired_content = original_bytes

    while lines:
        candidate = b"".join(lines)

        if _can_read_csv(candidate):
            repaired_content = candidate
            break

        lines.pop()
        removed_lines += 1

    if not lines:
        raise RuntimeError(
            "Unable to recover a readable journal. "
            f"Backup preserved at: {backup_path}"
        )

    temporary_path = JOURNAL_PATH.with_suffix(".repairing.csv")

    temporary_path.write_bytes(repaired_content)

    os.replace(
        temporary_path,
        JOURNAL_PATH,
    )

    repaired = pd.read_csv(JOURNAL_PATH)

    print("\n========================================")
    print("Project Stonks Journal Repair")
    print("========================================")
    print(f"Backup: {backup_path}")
    print(f"Trailing physical lines removed: {removed_lines}")
    print(f"Recovered journal rows: {len(repaired)}")
    print(f"Repaired journal: {JOURNAL_PATH}")


if __name__ == "__main__":
    repair_trade_journal()