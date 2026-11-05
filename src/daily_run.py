from __future__ import annotations

import glob
import subprocess
import sys
from pathlib import Path

from report_writer import build_daily_report
from email_reporter import send_email_report
from schwab.market_data_client import get_normalized_price_history


SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
CAPITAL_SNAPSHOTS_PATH = PROJECT_ROOT / "data" / "account_state_snapshots.csv"
WEEKLY_SCAN_PATH = SRC_DIR / "production_scan.py"
OPTION_COLLECTION_PATH = SRC_DIR / "option_observation_collector.py"
RESEARCH_RANKING_PATH = SRC_DIR / "research_ranking.py"


def validate_market_data() -> None:
    """Fail closed before producing guidance when Schwab data is unavailable."""
    try:
        candles = get_normalized_price_history(
            ticker="SPY",
            period_type="year",
            period=1,
            frequency_type="daily",
            frequency=1,
            need_extended_hours_data=False,
        )
    except Exception as error:
        raise RuntimeError(
            "Schwab market-data preflight failed. Daily guidance and email "
            "were suppressed because prices and allocations would be invalid."
        ) from error
    valid_closes = [row.get("Close") for row in candles if row.get("Close") is not None]
    if len(valid_closes) < 200:
        raise RuntimeError(
            "Schwab market-data preflight returned insufficient SPY history. "
            "Daily guidance and email were suppressed."
        )


def run_evidence_audit() -> None:
    """Persist a read-only coverage checklist after email and quote collection."""
    try:
        result = subprocess.run(
            [sys.executable, "-u", str(SRC_DIR / "config_evidence_audit.py"),
             "--output-dir", str(REPORTS_DIR)],
            cwd=str(PROJECT_ROOT), timeout=30, check=False,
        )
        if result.returncode:
            print("WARNING: config evidence audit failed; daily report unaffected.")
    except (subprocess.TimeoutExpired, OSError):
        print("WARNING: config evidence audit unavailable; daily report unaffected.")


def collect_research_observations() -> None:
    """Collect after email; learning-data failures cannot block trading guidance."""
    try:
        result = subprocess.run(
            [sys.executable, "-u", str(OPTION_COLLECTION_PATH)],
            cwd=str(PROJECT_ROOT), timeout=45, check=False,
        )
        if result.returncode:
            print("WARNING: option research collection incomplete; daily report unaffected.")
    except subprocess.TimeoutExpired:
        print("WARNING: option research collection exceeded 45 seconds; saved batches remain valid.")
    except OSError:
        print("WARNING: option research collector could not start; daily report unaffected.")


def refresh_research_ranking_shadow() -> None:
    """Refresh the derived ledger without modifying immutable recommendations."""
    try:
        result = subprocess.run(
            [sys.executable, "-u", str(RESEARCH_RANKING_PATH)],
            cwd=str(PROJECT_ROOT), timeout=30, check=False,
        )
        if result.returncode:
            print("WARNING: shadow research ranking refresh failed; guidance unaffected.")
    except (subprocess.TimeoutExpired, OSError):
        print("WARNING: shadow research ranking refresh unavailable; guidance unaffected.")


def refresh_six_week_shadow() -> None:
    """Opt-in sidecar; no baseline recommendations or email content changes."""
    from six_week_release import active_settings
    try:
        settings = active_settings(PROJECT_ROOT)
    except (ValueError, OSError):
        print("WARNING: six-week shadow activation invalid; baseline guidance unaffected.")
        return
    if settings.get("comparison"):
        try:
            recommendations = latest_file(str(DATA_PROCESSED_DIR / "trade_recommendations_*.csv"))
            if recommendations is None:
                raise FileNotFoundError("No comparison candidate snapshot")
            result = subprocess.run(
                [sys.executable, "-u", str(SRC_DIR / "shadow_comparison_runtime.py"),
                 "daily", "--candidates", str(recommendations)],
                cwd=str(PROJECT_ROOT), timeout=45, check=False,
            )
            if result.returncode:
                print("WARNING: option comparison decision capture failed; baseline guidance unaffected.")
        except (subprocess.TimeoutExpired, OSError):
            print("WARNING: option comparison unavailable; baseline guidance unaffected.")
    model_path = settings.get("model")
    if not model_path:
        return
    from datetime import datetime, timezone
    output = DATA_PROCESSED_DIR / "six_week_shadow" / (
        "predictions_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f") + ".csv"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-u", str(SRC_DIR / "six_week_calibration.py"),
             "shadow", "--journal", str(PROJECT_ROOT / "data" / "trade_journal.csv"),
             "--model", model_path, "--output", str(output)],
            cwd=str(PROJECT_ROOT), timeout=45, check=False,
        )
        if result.returncode:
            print("WARNING: six-week shadow failed; baseline guidance unaffected.")
    except (subprocess.TimeoutExpired, OSError):
        print("WARNING: six-week shadow unavailable; baseline guidance unaffected.")


def collect_spy_research() -> None:
    """Isolated bounded SPY selection; never adds to production candidates."""
    try:
        result = subprocess.run(
            [sys.executable, "-u", str(SRC_DIR / "spy_option_research.py")],
            cwd=str(PROJECT_ROOT), timeout=90, check=False,
        )
        if result.returncode:
            print("WARNING: SPY research selection failed; baseline guidance unaffected.")
    except (subprocess.TimeoutExpired, OSError) as error:
        from spy_option_research import atomic_json, DIRECTORY
        from datetime import datetime, timezone
        atomic_json(PROJECT_ROOT / DIRECTORY / "health_latest.json", {
            "status": "CAPTURE_TIMEOUT_OR_UNAVAILABLE", "error_type": type(error).__name__,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        print("WARNING: SPY research unavailable; baseline guidance unaffected.")


def refresh_evidence_monitor() -> None:
    """Observational report only, isolated from trading and email delivery."""
    try:
        result = subprocess.run(
            [sys.executable, "-u", str(SRC_DIR / "evidence_monitor.py")],
            cwd=str(PROJECT_ROOT), timeout=45, check=False,
        )
        if result.returncode:
            print("WARNING: evidence monitor unavailable; experiment decisions unaffected.")
    except (subprocess.TimeoutExpired, OSError):
        print("WARNING: evidence monitor did not complete; experiment decisions unaffected.")


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

    print("Validating Schwab market data...")
    validate_market_data()
    print("Schwab market-data preflight passed.")

    result = subprocess.run(
        [sys.executable, "-u", str(WEEKLY_SCAN_PATH)],
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
        capital_snapshot_path=CAPITAL_SNAPSHOTS_PATH,
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

    collect_research_observations()
    refresh_research_ranking_shadow()
    refresh_six_week_shadow()
    collect_spy_research()
    run_evidence_audit()
    refresh_evidence_monitor()
    print()
    print("Project Stonks daily run completed successfully.")


if __name__ == "__main__":
    main()
