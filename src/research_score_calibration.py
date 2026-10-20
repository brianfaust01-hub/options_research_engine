"""Read-only calibration audit for the Project Stonks research layer."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from config_combination_analysis import post_fix_episode_frame
from hindsight_analytics import _column


COMPONENT_FIELDS = [
    "ResearchScore",
    "TrendScore",
    "MomentumScore",
    "RiskScore",
    "LiquidityScore",
    "StrategyScore",
    "OpportunityScore",
    "DirectionalConviction",
    "TimeEdgeScore",
]


def _auc(scores: pd.Series, wins: pd.Series) -> float | None:
    working = pd.DataFrame({"score": pd.to_numeric(scores, errors="coerce"), "win": wins}).dropna()
    positive = working.loc[working["win"], "score"].to_numpy()
    negative = working.loc[~working["win"], "score"].to_numpy()
    if not len(positive) or not len(negative):
        return None
    comparisons = positive[:, None] - negative[None, :]
    return float((np.sum(comparisons > 0) + .5 * np.sum(comparisons == 0)) / comparisons.size)


def _metrics(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {"episodes": 0, "win_rate": None, "average_return": None, "profit_factor": None}
    returns = frame["_Return"]
    gains = returns[returns > 0].sum()
    losses = -returns[returns < 0].sum()
    return {
        "episodes": int(len(frame)),
        "win_rate": float(returns.gt(0).mean()),
        "average_return": float(returns.mean()),
        "profit_factor": None if losses == 0 else float(gains / losses),
    }


def merge_research_components(episodes: pd.DataFrame, journal: pd.DataFrame) -> pd.DataFrame:
    """Attach immutable at-decision research components by recommendation ID."""
    if "RecommendationID" not in journal:
        return episodes.copy()
    available = ["RecommendationID"] + [
        field for field in COMPONENT_FIELDS if field in journal and field not in episodes
    ]
    latest = journal[available].drop_duplicates("RecommendationID", keep="last")
    return episodes.merge(latest, on="RecommendationID", how="left")


def audit_research_score(episodes: pd.DataFrame) -> dict:
    working = episodes.copy()
    wins = working["_Return"].gt(0)
    score = pd.to_numeric(_column(working, "ResearchScore", "research_score"), errors="coerce")
    working["_ResearchScore"] = score
    working["_ScoreBand"] = (score // 10 * 10).astype("Int64")
    valid = working[score.notna()].copy()

    bands = []
    for band, subset in valid.groupby("_ScoreBand"):
        bands.append({"band": f"{int(band)}-{int(band) + 9}", **_metrics(subset)})

    direction_bands = []
    for (direction, band), subset in valid.groupby(["_Direction", "_ScoreBand"]):
        direction_bands.append({
            "direction": str(direction),
            "band": f"{int(band)}-{int(band) + 9}",
            **_metrics(subset),
        })

    # Ranking within each recommendation date is the decision-relevant test:
    # the allocator can only choose among candidates available together.
    valid["_DatePercentile"] = valid.groupby("_Date")["_ResearchScore"].rank(pct=True, method="average")
    valid["_DateQuartile"] = pd.cut(
        valid["_DatePercentile"],
        [0, .25, .50, .75, 1.0],
        labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"],
        include_lowest=True,
    )
    quartiles = []
    for quartile, subset in valid.groupby("_DateQuartile", observed=True):
        quartiles.append({"quartile": str(quartile), **_metrics(subset)})

    date_tests = []
    for date, subset in valid.groupby("_Date"):
        date_tests.append({
            "date": pd.Timestamp(date).date().isoformat(),
            "episodes": int(len(subset)),
            "spearman_score_return": _safe_corr(subset["_ResearchScore"], subset["_Return"]),
            "score_auc": _auc(subset["_ResearchScore"], subset["_Return"].gt(0)),
        })

    components = []
    for field in COMPONENT_FIELDS:
        if field not in working:
            continue
        values = pd.to_numeric(working[field], errors="coerce")
        complete = values.notna()
        if complete.sum() < 5 or values[complete].nunique() < 2:
            continue
        components.append({
            "field": field,
            "coverage": int(complete.sum()),
            "unique_values": int(values[complete].nunique()),
            "spearman_return": _safe_corr(values[complete], working.loc[complete, "_Return"]),
            "win_auc": _auc(values[complete], working.loc[complete, "_Return"].gt(0)),
            "winner_mean": float(values[complete & wins].mean()),
            "loser_mean": float(values[complete & ~wins].mean()),
        })

    allocated = _column(working, "AllocationDecision", "allocation_decision") \
        .fillna("").astype(str).str.casefold().eq("allocate")
    return {
        "episode_count": int(len(working)),
        "date_count": int(working["_Date"].nunique()),
        "overall": _metrics(working),
        "research_score_coverage": int(score.notna().sum()),
        "research_score_spearman_return": _safe_corr(score, working["_Return"]),
        "research_score_win_auc": _auc(score, wins),
        "bands": bands,
        "direction_bands": direction_bands,
        "within_date_quartiles": quartiles,
        "date_tests": date_tests,
        "components": components,
        "allocated": _metrics(working[allocated]),
        "unallocated": _metrics(working[~allocated]),
        "allocated_average_research_score": None if not allocated.any() else float(score[allocated].mean()),
        "unallocated_average_research_score": None if (~allocated).sum() == 0 else float(score[~allocated].mean()),
    }


def _safe_corr(left: pd.Series, right: pd.Series) -> float | None:
    pair = pd.DataFrame({"left": pd.to_numeric(left, errors="coerce"), "right": pd.to_numeric(right, errors="coerce")}).dropna()
    if len(pair) < 3 or pair["left"].nunique() < 2 or pair["right"].nunique() < 2:
        return None
    value = pair["left"].corr(pair["right"], method="spearman")
    return None if pd.isna(value) else float(value)


def _pct(value) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{100 * value:.1f}%"


def _num(value, digits=2) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:.{digits}f}"


def render_report(result: dict, source: Path) -> str:
    lines = [
        "# Project Stonks — Research Score Calibration Audit",
        "",
        f"**Source:** `{source.name}`  ",
        f"**Generated:** {datetime.now().isoformat(timespec='seconds')}  ",
        f"**Post-fix matured episodes:** {result['episode_count']} across {result['date_count']} recommendation dates  ",
        "**Decision status:** research only; no production score or allocation rule changed",
        "",
        "## Headline Test",
        "",
        f"Research Score has a {_num(result['research_score_spearman_return'])} Spearman relationship with seven-day return and {_num(result['research_score_win_auc'], 3)} win/loss AUC. An AUC of 0.500 is random ranking; values below 0.500 mean winners tend to receive lower scores.",
        "",
        "## Research Score Bands",
        "",
        "| Score band | N | Win rate | Average return | Profit factor |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in result["bands"]:
        lines.append(f"| {row['band']} | {row['episodes']} | {_pct(row['win_rate'])} | {_pct(row['average_return'])} | {_num(row['profit_factor'])} |")
    lines.extend([
        "",
        "## Score Bands by Direction",
        "",
        "| Direction | Score band | N | Win rate | Average return | Profit factor |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ])
    for row in result["direction_bands"]:
        lines.append(f"| {row['direction']} | {row['band']} | {row['episodes']} | {_pct(row['win_rate'])} | {_pct(row['average_return'])} | {_num(row['profit_factor'])} |")
    lines.extend([
        "",
        "## Within-Date Ranking",
        "",
        "This is the closest test of the allocator's real choice: did higher-scored candidates outperform other candidates available on the same day?",
        "",
        "| Daily score quartile | N | Win rate | Average return | Profit factor |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for row in result["within_date_quartiles"]:
        lines.append(f"| {row['quartile']} | {row['episodes']} | {_pct(row['win_rate'])} | {_pct(row['average_return'])} | {_num(row['profit_factor'])} |")
    lines.extend([
        "",
        "## Available Research Components",
        "",
        "| Component | Coverage | Spearman vs return | Win AUC | Winner mean | Loser mean |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in sorted(result["components"], key=lambda item: (item["win_auc"] or 0), reverse=True):
        lines.append(f"| {row['field']} | {row['coverage']} | {_num(row['spearman_return'])} | {_num(row['win_auc'], 3)} | {_num(row['winner_mean'], 1)} | {_num(row['loser_mean'], 1)} |")
    lines.extend([
        "",
        "## Allocation Diagnostic",
        "",
        f"Only {result['allocated']['episodes']} post-fix allocated episodes have matured. They averaged Research Score {_num(result['allocated_average_research_score'], 1)}, versus {_num(result['unallocated_average_research_score'], 1)} for unallocated episodes. Their win rate was {_pct(result['allocated']['win_rate'])} and average return was {_pct(result['allocated']['average_return'])}; this allocation sample is too small for a final inference.",
        "",
        "## Interpretation",
        "",
        "- A healthy research score should rank within-day opportunities, not merely clear a candidate threshold.",
        "- The current evidence supports interpreting Research Score as a candidate gate, not as a calibrated probability or expected-return ranking.",
        "- Non-monotonic score bands, near-random AUC, or weak within-day quartiles indicate calibration/ranking weakness even if the overall research population has positive expectancy.",
        "- Component results are diagnostic. They do not authorize reweighting until date-grouped and forward-shadow validation is complete.",
        "- Contract Greeks, IV, execution, and allocation variables are intentionally excluded from this audit.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--journal", type=Path, default=Path("data/trade_journal.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    raw = pd.read_csv(args.source, low_memory=False)
    journal = pd.read_csv(args.journal, low_memory=False)
    episodes = merge_research_components(post_fix_episode_frame(raw), journal)
    result = audit_research_score(episodes)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = args.output_dir / f"research_score_calibration_{stamp}.md"
    data = args.output_dir / f"research_score_calibration_{stamp}.json"
    report.write_text(render_report(result, args.source), encoding="utf-8")
    data.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Research calibration report: {report}")
    print(f"Research calibration data: {data}")


if __name__ == "__main__":
    main()
