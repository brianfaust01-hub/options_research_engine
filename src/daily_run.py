from __future__ import annotations

import glob
import subprocess
import sys
from pathlib import Path

from report_writer import build_daily_report
from email_reporter import send_email_report


SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
WEEKLY_SCAN_PATH = SRC_DIR / "weekly_scan.py"


def latest_file(pattern: str) -> Path | None:
    matches = [Path(p) for p in glob.glob(pattern)]

    if not matches:
        return None

    return max(matches, key=lambda p: p.stat().st_mtime)


def main() -> None:
    print("Starting Project Stonks daily run...")
    print(f"Project root: {PROJECT_ROOT}")

    if not WEEKLY_SCAN_PATH.exists():
        raise FileNotFoundError(
            f"Could not find weekly_scan.py at: {WEEKLY_SCAN_PATH}"
        )

    result = subprocess.run(
        [sys.executable, str(WEEKLY_SCAN_PATH)],
        cwd=str(PROJECT_ROOT),
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "weekly_scan.py failed. Daily report was not generated."
        )

    recommendations_path = latest_file(
        str(DATA_PROCESSED_DIR / "*recommendations*.csv")
    )

    positions_review_path = latest_file(
        str(DATA_PROCESSED_DIR / "position_actions_*.csv")
    )

    if recommendations_path is None:
        raise FileNotFoundError(
            f"No recommendations CSV found in: {DATA_PROCESSED_DIR}"
        )

    report_path = build_daily_report(
        recommendations_path=recommendations_path,
        positions_review_path=positions_review_path,
        output_dir=REPORTS_DIR,
    )

    print(f"Report written to: {report_path}")

    try:
        send_email_report(
            report_path,
            attachment_paths=[
                recommendations_path,
                *(
                    [positions_review_path]
                    if positions_review_path is not None
                    else []
                ),
            ],
        )
        print("Daily email report sent successfully.")

    except ValueError as e:
        print()
        print("Email skipped.")
        print(e)

    print()
    print("Project Stonks daily run completed successfully.")


if __name__ == "__main__":
    main()
