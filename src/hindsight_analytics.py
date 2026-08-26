"""Read-only credibility and calibration analytics for research hindsight.

This module consumes hindsight output.  It never changes recommendations,
portfolio state, scoring weights, or immutable snapshots.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
HORIZONS = (3, 5, 7, 14, 30)
MIN_CREDIBLE_SAMPLE = 30
EPISODE_RESET_CALENDAR_DAYS = 7
NEUTRAL_RETURN_BAND = 0.0025
MEANINGFUL_RETURN_THRESHOLD = 0.01


def _number(value):
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _column(frame: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in frame.columns:
            return frame[name]
    return pd.Series(index=frame.index, dtype="object")


def _wilson_interval(wins: int, total: int, z: float = 1.96):
    if total <= 0:
        return None, None
    p = wins / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(
        (p * (1 - p) + z * z / (4 * total)) / total
    ) / denominator
    return center - margin, center + margin


def build_thesis_episodes(
    observations: pd.DataFrame,
    reset_days: int = EPISODE_RESET_CALENDAR_DAYS,
) -> pd.DataFrame:
    """Assign ticker/direction observations to contiguous thesis episodes."""
    result = observations.copy()
    result["RecommendationDateParsed"] = pd.to_datetime(
        _column(result, "RecommendationDate"),
        errors="coerce",
        utc=True,
        format="mixed",
    ).dt.tz_convert(None)
    result["DirectionNormalized"] = _column(result, "Direction").fillna("")
    result["TickerNormalized"] = _column(result, "Ticker", "ticker").fillna("")
    result = result.sort_values(
        ["TickerNormalized", "RecommendationDateParsed", "RecommendationID"],
        na_position="last",
    )

    episode_ids = []
    episode = 0
    prior_by_ticker: dict[str, tuple[pd.Timestamp, str, int]] = {}
    for _, row in result.iterrows():
        ticker = str(row["TickerNormalized"])
        direction = str(row["DirectionNormalized"])
        date = row["RecommendationDateParsed"]
        prior = prior_by_ticker.get(ticker)
        starts_new = prior is None
        if prior is not None:
            prior_date, prior_direction, prior_episode = prior
            gap = (date - prior_date).days if pd.notna(date) else reset_days + 1
            starts_new = direction != prior_direction or gap > reset_days
            if not starts_new:
                episode = prior_episode
        if starts_new:
            episode += 1
        episode_id = f"TE-{episode:06d}"
        episode_ids.append(episode_id)
        prior_by_ticker[ticker] = (date, direction, episode)

    result["ThesisEpisodeID"] = episode_ids
    return result.sort_index()


def _metrics(values: pd.Series, alpha_values: pd.Series | None = None) -> dict:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    wins = int((numeric > 0).sum())
    losses = int((numeric < 0).sum())
    evaluated = wins + losses
    lower, upper = _wilson_interval(wins, evaluated)
    winning = numeric[numeric > 0]
    losing = numeric[numeric < 0]
    avg_win = winning.mean() if not winning.empty else None
    avg_loss = losing.mean() if not losing.empty else None
    payoff = (
        avg_win / abs(avg_loss)
        if avg_win is not None and avg_loss not in (None, 0)
        else None
    )
    alpha = pd.to_numeric(alpha_values, errors="coerce").dropna() \
        if alpha_values is not None else pd.Series(dtype=float)
    return {
        "observations": int(len(values)),
        "evaluated": evaluated,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / evaluated if evaluated else None,
        "win_rate_ci_low": lower,
        "win_rate_ci_high": upper,
        "average_return": numeric.mean() if not numeric.empty else None,
        "median_return": numeric.median() if not numeric.empty else None,
        "average_winner": avg_win,
        "average_loser": avg_loss,
        "payoff_ratio": payoff,
        "positive_alpha_rate": float((alpha > 0).mean()) if not alpha.empty else None,
        "average_alpha": alpha.mean() if not alpha.empty else None,
        "sample_status": "CREDIBLE" if evaluated >= MIN_CREDIBLE_SAMPLE else "PRELIMINARY",
        "meaningful_wins": int((numeric >= MEANINGFUL_RETURN_THRESHOLD).sum()),
        "noise": int((numeric.abs() <= NEUTRAL_RETURN_BAND).sum()),
        "meaningful_losses": int((numeric <= -MEANINGFUL_RETURN_THRESHOLD).sum()),
    }


def summarize_horizons(frame: pd.DataFrame) -> dict[str, dict]:
    summaries = {}
    for days in HORIZONS:
        return_col = f"Horizon{days}DDirectionalReturnPct"
        alpha_col = f"Horizon{days}DAlphaVsSPY"
        if return_col not in frame.columns:
            summaries[f"{days}D"] = {**_metrics(pd.Series(dtype=float)), "available": False}
            continue
        complete = frame[_column(frame, f"Horizon{days}DStatus").eq("COMPLETE")]
        summaries[f"{days}D"] = {
            **_metrics(
                complete[return_col],
                complete[alpha_col] if alpha_col in complete else None,
            ),
            "available": True,
        }
    return summaries


def _bucket_score(value) -> str:
    number = _number(value)
    if number is None:
        return "Unknown"
    floor = int(number // 10) * 10
    return f"{floor}-{floor + 9}"


def _group_metrics(frame: pd.DataFrame, group: pd.Series, return_col: str) -> list[dict]:
    working = frame.assign(_Group=group)
    rows = []
    for label, subset in working.groupby("_Group", dropna=False):
        row = _metrics(subset[return_col])
        row["group"] = "Unknown" if pd.isna(label) else str(label)
        rows.append(row)
    return sorted(rows, key=lambda row: row["group"])


def _episode_representatives(episodes: pd.DataFrame, return_col: str) -> pd.DataFrame:
    complete = episodes[pd.to_numeric(episodes[return_col], errors="coerce").notna()]
    if complete.empty:
        return complete
    return complete.sort_values("RecommendationDateParsed").groupby(
        "ThesisEpisodeID", as_index=False
    ).first()


def analyze_hindsight(frame: pd.DataFrame) -> dict:
    directional = frame[_column(frame, "Direction").isin(["BULLISH", "BEARISH"])].copy()
    episodes = build_thesis_episodes(directional)
    horizon_summary = summarize_horizons(directional)
    primary_days = 7 if "Horizon7DDirectionalReturnPct" in directional else None
    primary_col = (
        "Horizon7DDirectionalReturnPct" if primary_days else "CurrentDirectionalReturnPct"
    )
    episode_view = _episode_representatives(episodes, primary_col)

    calibration = {}
    if primary_col in directional:
        complete = directional[pd.to_numeric(directional[primary_col], errors="coerce").notna()]
        fields = {
            "direction": _column(complete, "Direction"),
            "confidence": _column(complete, "Confidence").map(_bucket_score),
            "research_score": _column(complete, "ResearchScore", "research_score").map(_bucket_score),
            "time_edge": _column(complete, "TimeEdgeScore", "time_edge_score").map(_bucket_score),
            "institutional_trade_score": _column(complete, "InstitutionalTradeScore", "institutional_trade_score").map(_bucket_score),
            "directional_conviction": _column(complete, "DirectionalConviction", "directional_conviction").map(_bucket_score),
            "allocation": _column(complete, "AllocationDecision", "allocation_decision").fillna("Unknown"),
            "market_regime": _column(complete, "MarketRegime", "market_regime").fillna("Unknown"),
            "earnings_status": _column(complete, "EarningsStatus", "earnings_status").fillna("Unknown"),
        }
        calibration = {
            name: _group_metrics(complete, groups, primary_col)
            for name, groups in fields.items()
        }

    dates = pd.to_datetime(
        _column(directional, "RecommendationDate"),
        errors="coerce",
        format="mixed",
    )
    missing_rate = float(directional.isna().mean().mean()) if not directional.empty else 0.0
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "primary_horizon": f"{primary_days}D" if primary_days else "CURRENT",
        "counts": {
            "total_records": int(len(frame)),
            "directional_records": int(len(directional)),
            "unique_recommendations": int(_column(frame, "RecommendationID").nunique()),
            "unique_tickers": int(_column(directional, "Ticker", "ticker").nunique()),
            "recommendation_date_cohorts": int(dates.dt.date.nunique()),
            "thesis_episodes": int(episodes["ThesisEpisodeID"].nunique()),
            "episode_results_available": int(len(episode_view)),
            "no_direction_records": int(len(frame) - len(directional)),
        },
        "horizons": horizon_summary,
        "raw_primary": _metrics(directional[primary_col]) if primary_col in directional else _metrics(pd.Series(dtype=float)),
        "episode_primary": _metrics(episode_view[primary_col]) if primary_col in episode_view else _metrics(pd.Series(dtype=float)),
        "calibration": calibration,
        "data_quality": {
            "overall_missing_cell_rate": missing_rate,
            "minimum_credible_sample": MIN_CREDIBLE_SAMPLE,
            "warnings": _warnings(directional, horizon_summary, episode_view),
        },
        "contract_counterfactual": {
            "status": "UNAVAILABLE",
            "reason": (
                "Historical option-quote paths are not available. Underlying "
                "thesis outcomes are not treated as option-contract returns."
            ),
        },
    }


def _warnings(frame: pd.DataFrame, horizons: dict, episodes: pd.DataFrame) -> list[str]:
    warnings = []
    if not any(item.get("available") for item in horizons.values()):
        warnings.append("Fixed-horizon fields are unavailable; regenerate hindsight with the current engine.")
    bearish = int(_column(frame, "Direction").eq("BEARISH").sum())
    if bearish < MIN_CREDIBLE_SAMPLE:
        warnings.append(f"Bearish sample is preliminary ({bearish} observations).")
    if len(episodes) < MIN_CREDIBLE_SAMPLE:
        warnings.append(f"Deduplicated episode sample is preliminary ({len(episodes)} evaluated episodes).")
    warnings.append("Analytics are observational and never change production weights automatically.")
    return warnings


def _pct(value) -> str:
    return "Unavailable" if value is None or pd.isna(value) else f"{value:.1%}"


def _markdown(summary: dict, source: Path) -> str:
    counts = summary["counts"]
    lines = [
        "# Project Stonks — Hindsight Analytics", "",
        f"Generated: {summary['generated_at']}",
        f"Source: `{source}`", "",
        "## Credibility", "",
        f"- Records: {counts['total_records']:,}",
        f"- Directional observations: {counts['directional_records']:,}",
        f"- Unique tickers: {counts['unique_tickers']:,}",
        f"- Recommendation-date cohorts: {counts['recommendation_date_cohorts']:,}",
        f"- Deduplicated thesis episodes: {counts['thesis_episodes']:,}", "",
        "## Fixed-Horizon Performance", "",
        "| Horizon | Evaluated | Win Rate | 95% CI | Avg Return | Meaningful W/L | Payoff | Status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for label, metrics in summary["horizons"].items():
        interval = f"{_pct(metrics.get('win_rate_ci_low'))}–{_pct(metrics.get('win_rate_ci_high'))}"
        payoff = metrics.get("payoff_ratio")
        lines.append(
            f"| {label} | {metrics['evaluated']:,} | {_pct(metrics.get('win_rate'))} | "
            f"{interval} | {_pct(metrics.get('average_return'))} | "
            f"{metrics.get('meaningful_wins', 0):,}/{metrics.get('meaningful_losses', 0):,} | "
            f"{'Unavailable' if payoff is None else f'{payoff:.2f}'} | {metrics['sample_status']} |"
        )
    lines.extend(["", "## Raw vs Deduplicated", ""])
    for label, key in [("Raw observations", "raw_primary"), ("Thesis episodes", "episode_primary")]:
        metrics = summary[key]
        lines.append(
            f"- {label}: {metrics['evaluated']:,} evaluated; "
            f"{_pct(metrics.get('win_rate'))} win rate; "
            f"{_pct(metrics.get('average_return'))} average return."
        )
    lines.extend(["", "## Score and Context Calibration (Primary Horizon)", ""])
    for section_name, rows in summary.get("calibration", {}).items():
        lines.extend([
            f"### {section_name.replace('_', ' ').title()}", "",
            "| Band | Evaluated | Win Rate | Avg Return | Sample |",
            "| --- | ---: | ---: | ---: | --- |",
        ])
        for row in rows:
            lines.append(
                f"| {row['group']} | {row['evaluated']:,} | "
                f"{_pct(row.get('win_rate'))} | {_pct(row.get('average_return'))} | "
                f"{row['sample_status']} |"
            )
        lines.append("")
    contract = summary["contract_counterfactual"]
    lines.extend([
        "## Option-Contract Counterfactual", "",
        f"Status: **{contract['status']}**", "",
        contract["reason"], "",
    ])
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in summary["data_quality"]["warnings"])
    lines.extend(["", "No production scoring or allocation behavior was changed.", ""])
    return "\n".join(lines)


def latest_hindsight_file(directory: Path = PROCESSED_DIR) -> Path | None:
    files = sorted(directory.glob("research_hindsight_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def generate_hindsight_analytics(
    source_path: str | Path | None = None,
    processed_dir: str | Path = PROCESSED_DIR,
    reports_dir: str | Path = REPORTS_DIR,
) -> dict:
    source = Path(source_path) if source_path else latest_hindsight_file(Path(processed_dir))
    if source is None or not source.exists():
        raise FileNotFoundError("No research hindsight CSV is available.")
    frame = pd.read_csv(source, low_memory=False)
    summary = analyze_hindsight(frame)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    processed = Path(processed_dir)
    reports = Path(reports_dir)
    processed.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    json_path = processed / f"hindsight_analytics_{timestamp}.json"
    report_path = reports / f"hindsight_analytics_{timestamp}.md"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report_path.write_text(_markdown(summary, source), encoding="utf-8")
    return {**summary, "json_path": str(json_path), "report_path": str(report_path)}


def main(argv: Iterable[str] | None = None):
    parser = argparse.ArgumentParser(description="Generate read-only Project Stonks hindsight analytics.")
    parser.add_argument("--source", help="Specific research_hindsight CSV")
    args = parser.parse_args(argv)
    result = generate_hindsight_analytics(args.source)
    print(f"Hindsight analytics report: {result['report_path']}")


if __name__ == "__main__":
    main()
