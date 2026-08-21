"""Build and send an action brief from the latest completed run."""

from __future__ import annotations

from daily_run import DATA_PROCESSED_DIR, REPORTS_DIR, latest_file
from email_reporter import send_email_report
from report_writer import build_daily_report


def main() -> None:
    recommendations_path = latest_file(
        str(DATA_PROCESSED_DIR / "trade_recommendations_*.csv")
    )
    positions_path = latest_file(
        str(DATA_PROCESSED_DIR / "position_actions_*.csv")
    )

    if recommendations_path is None:
        raise FileNotFoundError("No completed recommendation file is available.")

    report_path = build_daily_report(
        recommendations_path=recommendations_path,
        positions_review_path=positions_path,
        output_dir=REPORTS_DIR,
    )
    attachments = [recommendations_path]
    if positions_path is not None:
        attachments.append(positions_path)

    send_email_report(report_path, attachment_paths=attachments)
    print(f"Test action brief sent: {report_path}")


if __name__ == "__main__":
    main()
