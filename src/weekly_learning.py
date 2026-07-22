"""
Project Stonks
Weekly Learning Engine

Sprint 32A

Purpose
-------
Transform Research Monitor outputs into structured weekly learning.

The engine analyzes:

- Current research accuracy
- Directional returns
- Alpha versus SPY
- Performance by strategy
- Performance by confidence
- Performance by recommendation age
- Performance by trade grade when snapshot data is available
- Performance by allocation score when snapshot data is available
- Top and bottom research ideas

Inputs
------
- Latest data/processed/research_hindsight_*.csv
- Immutable recommendation snapshots when available

Outputs
-------
- Console summary
- reports/weekly_learning_*.md
- data/processed/weekly_learning_*.json

This module does not modify the journal, snapshots, or portfolio.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"


def _latest_hindsight_file() -> Path | None:
    files = list(
        PROCESSED_DATA_DIR.glob(
            "research_hindsight_*.csv"
        )
    )

    if not files:
        return None

    return max(
        files,
        key=lambda path: path.stat().st_mtime,
    )


def _safe_float(
    value: Any,
) -> float | None:
    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_text(
    value: Any,
) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def _load_snapshot(
    path_value: Any,
) -> dict:
    path_text = _safe_text(path_value)

    if path_text is None:
        return {}

    snapshot_path = Path(path_text)

    if not snapshot_path.exists():
        return {}

    try:
        with snapshot_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            snapshot = json.load(file)

        if isinstance(snapshot, dict):
            return snapshot

    except (OSError, json.JSONDecodeError):
        pass

    return {}


def _find_nested_value(
    snapshot: dict,
    field_names: list[str],
):
    containers = [
        snapshot,
        snapshot.get("trade", {}),
        snapshot.get("research", {}),
    ]

    for container in containers:
        if not isinstance(container, dict):
            continue

        for field_name in field_names:
            if field_name in container:
                value = container[field_name]

                if value is not None:
                    return value

    return None


def _extract_snapshot_metadata(
    row: pd.Series,
) -> pd.Series:
    snapshot = _load_snapshot(
        row.get("SnapshotPath")
    )

    trade_quality_grade = _find_nested_value(
        snapshot,
        [
            "trade_quality_grade",
            "TradeQualityGrade",
            "grade",
            "Grade",
        ],
    )

    trade_quality_score = _find_nested_value(
        snapshot,
        [
            "trade_quality_score",
            "TradeQualityScore",
        ],
    )

    allocation_score = _find_nested_value(
        snapshot,
        [
            "allocation_score",
            "AllocationScore",
        ],
    )

    allocation_decision = _find_nested_value(
        snapshot,
        [
            "allocation_decision",
            "AllocationDecision",
        ],
    )

    premium = _find_nested_value(
        snapshot,
        [
            "premium",
            "Premium",
        ],
    )

    strike = _find_nested_value(
        snapshot,
        [
            "strike",
            "Strike",
        ],
    )

    delta = _find_nested_value(
        snapshot,
        [
            "delta",
            "Delta",
        ],
    )

    dte = _find_nested_value(
        snapshot,
        [
            "dte",
            "DTE",
        ],
    )

    return pd.Series(
        {
            "TradeQualityGrade": (
                _safe_text(trade_quality_grade)
            ),
            "TradeQualityScore": (
                _safe_float(trade_quality_score)
            ),
            "AllocationScore": (
                _safe_float(allocation_score)
            ),
            "AllocationDecision": (
                _safe_text(allocation_decision)
            ),
            "Premium": _safe_float(premium),
            "Strike": _safe_float(strike),
            "RecommendationDTE": _safe_float(dte),
            "Delta": _safe_float(delta),
        }
    )


def _bucket_allocation_score(
    value,
) -> str:
    score = _safe_float(value)

    if score is None:
        return "Unknown"

    if score >= 95:
        return "95+"

    if score >= 90:
        return "90-94"

    if score >= 85:
        return "85-89"

    return "<85"


def _bucket_confidence(
    value,
) -> str:
    confidence = _safe_float(value)

    if confidence is None:
        return "Unknown"

    if confidence >= 90:
        return "90+"

    if confidence >= 75:
        return "75-89"

    if confidence >= 60:
        return "60-74"

    return "<60"


def _bucket_age(
    value,
) -> str:
    age = _safe_float(value)

    if age is None:
        return "Unknown"

    if age <= 1:
        return "0-1 days"

    if age <= 3:
        return "2-3 days"

    if age <= 7:
        return "4-7 days"

    if age <= 14:
        return "8-14 days"

    if age <= 30:
        return "15-30 days"

    return "31+ days"


def _build_group_summary(
    dataframe: pd.DataFrame,
    group_column: str,
) -> dict:
    if (
        dataframe.empty
        or group_column not in dataframe.columns
    ):
        return {}

    summaries = {}

    for group_name, group in dataframe.groupby(
        group_column,
        dropna=False,
    ):
        name = (
            "Unknown"
            if pd.isna(group_name)
            else str(group_name)
        )

        returns = pd.to_numeric(
            group["CurrentDirectionalReturnPct"],
            errors="coerce",
        ).dropna()

        alpha = pd.to_numeric(
            group["CurrentAlphaVsSPY"],
            errors="coerce",
        ).dropna()

        thesis_results = group[
            "CurrentThesisResult"
        ]

        winners = int(
            (
                thesis_results == "CORRECT"
            ).sum()
        )

        losers = int(
            (
                thesis_results == "INCORRECT"
            ).sum()
        )

        scored = winners + losers

        win_rate = (
            winners / scored
            if scored > 0
            else None
        )

        summaries[name] = {
            "recommendations": int(len(group)),
            "scored": scored,
            "winners": winners,
            "losers": losers,
            "win_rate": win_rate,
            "average_return": (
                float(returns.mean())
                if not returns.empty
                else None
            ),
            "median_return": (
                float(returns.median())
                if not returns.empty
                else None
            ),
            "average_alpha": (
                float(alpha.mean())
                if not alpha.empty
                else None
            ),
        }

    return summaries


def _format_percent(
    value,
) -> str:
    numeric_value = _safe_float(value)

    if numeric_value is None:
        return "N/A"

    return f"{numeric_value:.2%}"


def _summary_to_dataframe(
    summary: dict,
    label_name: str,
) -> pd.DataFrame:
    rows = []

    for label, metrics in summary.items():
        rows.append(
            {
                label_name: label,
                "Recommendations": metrics.get(
                    "recommendations"
                ),
                "Scored": metrics.get("scored"),
                "Win Rate": _format_percent(
                    metrics.get("win_rate")
                ),
                "Average Return": _format_percent(
                    metrics.get("average_return")
                ),
                "Median Return": _format_percent(
                    metrics.get("median_return")
                ),
                "Average Alpha": _format_percent(
                    metrics.get("average_alpha")
                ),
            }
        )

    return pd.DataFrame(rows)


def _build_ranked_ideas(
    dataframe: pd.DataFrame,
    largest: bool,
    count: int = 10,
) -> pd.DataFrame:
    required_columns = [
        "Ticker",
        "RecommendationDate",
        "OptionStrategy",
        "CurrentDirectionalReturnPct",
        "CurrentAlphaVsSPY",
        "CurrentThesisResult",
        "RecommendationAgeDays",
    ]

    existing_columns = [
        column
        for column in required_columns
        if column in dataframe.columns
    ]

    ranked = dataframe.dropna(
        subset=["CurrentDirectionalReturnPct"]
    ).copy()

    if ranked.empty:
        return pd.DataFrame(
            columns=existing_columns
        )

    ranked[
        "CurrentDirectionalReturnPct"
    ] = pd.to_numeric(
        ranked["CurrentDirectionalReturnPct"],
        errors="coerce",
    )

    ranked = ranked.dropna(
        subset=["CurrentDirectionalReturnPct"]
    )

    if largest:
        ranked = ranked.nlargest(
            count,
            "CurrentDirectionalReturnPct",
        )
    else:
        ranked = ranked.nsmallest(
            count,
            "CurrentDirectionalReturnPct",
        )

    return ranked[existing_columns].copy()


def _format_ranked_for_report(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    formatted = dataframe.copy()

    for column in [
        "CurrentDirectionalReturnPct",
        "CurrentAlphaVsSPY",
    ]:
        if column in formatted.columns:
            formatted[column] = formatted[
                column
            ].apply(_format_percent)

    return formatted


def _write_markdown_report(
    learning: dict,
    output_path: Path,
) -> None:
    lines: list[str] = []

    lines.append(
        "# Project Stonks Weekly Learning Report"
    )
    lines.append("")
    lines.append(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    lines.append("")
    lines.append(
        f"Source: `{learning['source_file']}`"
    )
    lines.append("")

    summary = learning["summary"]

    lines.append("## Overall Research Performance")
    lines.append("")
    lines.append(
        f"- Recommendations analyzed: "
        f"{summary['total_recommendations']}"
    )
    lines.append(
        f"- Directional recommendations scored: "
        f"{summary['scored_recommendations']}"
    )
    lines.append(
        f"- In progress: {summary['in_progress']}"
    )
    lines.append(
        f"- Complete: {summary['complete']}"
    )
    lines.append(
        f"- Awaiting market data: "
        f"{summary['awaiting_market_data']}"
    )
    lines.append(
        f"- No directional thesis: "
        f"{summary['no_direction']}"
    )
    lines.append(
        f"- Current winners: {summary['current_winners']}"
    )
    lines.append(
        f"- Current losers: {summary['current_losers']}"
    )
    lines.append(
        f"- Current win rate: "
        f"{_format_percent(summary['current_win_rate'])}"
    )
    lines.append(
        f"- Average directional return: "
        f"{_format_percent(summary['average_return'])}"
    )
    lines.append(
        f"- Median directional return: "
        f"{_format_percent(summary['median_return'])}"
    )
    lines.append(
        f"- Average alpha vs. SPY: "
        f"{_format_percent(summary['average_alpha'])}"
    )
    lines.append("")

    report_sections = [
        (
            "Performance by Strategy",
            learning["by_strategy"],
            "Strategy",
        ),
        (
            "Performance by Direction",
            learning["by_direction"],
            "Direction",
        ),
        (
            "Performance by Confidence",
            learning["by_confidence"],
            "Confidence",
        ),
        (
            "Performance by Recommendation Age",
            learning["by_age"],
            "Age",
        ),
        (
            "Performance by Trade Grade",
            learning["by_grade"],
            "Grade",
        ),
        (
            "Performance by Allocation Score",
            learning["by_allocation_score"],
            "Allocation Score",
        ),
    ]

    for title, section, label_name in report_sections:
        lines.append(f"## {title}")
        lines.append("")

        section_df = _summary_to_dataframe(
            section,
            label_name,
        )

        if section_df.empty:
            lines.append(
                "No data available for this analysis."
            )
        else:
            lines.append(
                section_df.to_markdown(
                    index=False
                )
            )

        lines.append("")

    lines.append("## Top 10 Current Ideas")
    lines.append("")

    top_ideas = _format_ranked_for_report(
        learning["top_ideas"]
    )

    if top_ideas.empty:
        lines.append("No ranked ideas available.")
    else:
        lines.append(
            top_ideas.to_markdown(
                index=False
            )
        )

    lines.append("")
    lines.append("## Bottom 10 Current Ideas")
    lines.append("")

    bottom_ideas = _format_ranked_for_report(
        learning["bottom_ideas"]
    )

    if bottom_ideas.empty:
        lines.append("No ranked ideas available.")
    else:
        lines.append(
            bottom_ideas.to_markdown(
                index=False
            )
        )

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def generate_weekly_learning_report() -> dict:
    hindsight_path = _latest_hindsight_file()

    if hindsight_path is None:
        return {
            "status": "ERROR",
            "message": (
                "No research hindsight file found. "
                "Run research_hindsight.py first."
            ),
        }

    dataframe = pd.read_csv(
        hindsight_path
    )

    if dataframe.empty:
        return {
            "status": "ERROR",
            "message": (
                "Research hindsight file is empty."
            ),
        }

    required_columns = [
        "EvaluationStatus",
        "CurrentDirectionalReturnPct",
        "CurrentAlphaVsSPY",
        "CurrentThesisResult",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        return {
            "status": "ERROR",
            "message": (
                "Research hindsight file is missing "
                "required columns."
            ),
            "missing_columns": missing_columns,
        }

    print(
        "\nLoading snapshot metadata for weekly learning..."
    )

    snapshot_metadata = dataframe.apply(
        _extract_snapshot_metadata,
        axis=1,
    )

    for column in snapshot_metadata.columns:
        dataframe[column] = (
            snapshot_metadata[column]
        )

    dataframe["ConfidenceBucket"] = (
        dataframe["Confidence"].apply(
            _bucket_confidence
        )
        if "Confidence" in dataframe.columns
        else "Unknown"
    )

    dataframe["AgeBucket"] = (
        dataframe["RecommendationAgeDays"].apply(
            _bucket_age
        )
        if "RecommendationAgeDays"
        in dataframe.columns
        else "Unknown"
    )

    dataframe["AllocationBucket"] = (
        dataframe["AllocationScore"].apply(
            _bucket_allocation_score
        )
    )

    scored = dataframe[
        dataframe["CurrentThesisResult"].isin(
            [
                "CORRECT",
                "INCORRECT",
                "FLAT",
            ]
        )
    ].copy()

    winners = int(
        (
            scored["CurrentThesisResult"]
            == "CORRECT"
        ).sum()
    )

    losers = int(
        (
            scored["CurrentThesisResult"]
            == "INCORRECT"
        ).sum()
    )

    win_loss_scored = winners + losers

    current_win_rate = (
        winners / win_loss_scored
        if win_loss_scored > 0
        else None
    )

    directional_returns = pd.to_numeric(
        scored["CurrentDirectionalReturnPct"],
        errors="coerce",
    ).dropna()

    alpha_values = pd.to_numeric(
        scored["CurrentAlphaVsSPY"],
        errors="coerce",
    ).dropna()

    status_counts = (
        dataframe["EvaluationStatus"]
        .value_counts(dropna=False)
        .to_dict()
    )

    summary = {
        "total_recommendations": int(
            len(dataframe)
        ),
        "scored_recommendations": int(
            len(scored)
        ),
        "in_progress": int(
            status_counts.get(
                "IN_PROGRESS",
                0,
            )
        ),
        "complete": int(
            status_counts.get(
                "COMPLETE",
                0,
            )
        ),
        "awaiting_market_data": int(
            status_counts.get(
                "AWAITING_MARKET_DATA",
                0,
            )
            + status_counts.get(
                "MISSING_FINAL_MARKET_DATA",
                0,
            )
        ),
        "no_direction": int(
            status_counts.get(
                "NO_DIRECTION",
                0,
            )
        ),
        "current_winners": winners,
        "current_losers": losers,
        "current_win_rate": current_win_rate,
        "average_return": (
            float(directional_returns.mean())
            if not directional_returns.empty
            else None
        ),
        "median_return": (
            float(directional_returns.median())
            if not directional_returns.empty
            else None
        ),
        "average_alpha": (
            float(alpha_values.mean())
            if not alpha_values.empty
            else None
        ),
    }

    learning = {
        "status": "PASS",
        "source_file": str(
            hindsight_path
        ),
        "summary": summary,
        "by_strategy": _build_group_summary(
            scored,
            "OptionStrategy",
        ),
        "by_direction": _build_group_summary(
            scored,
            "Direction",
        ),
        "by_confidence": _build_group_summary(
            scored,
            "ConfidenceBucket",
        ),
        "by_age": _build_group_summary(
            scored,
            "AgeBucket",
        ),
        "by_grade": _build_group_summary(
            scored[
                scored[
                    "TradeQualityGrade"
                ].notna()
            ],
            "TradeQualityGrade",
        ),
        "by_allocation_score": (
            _build_group_summary(
                scored[
                    scored[
                        "AllocationScore"
                    ].notna()
                ],
                "AllocationBucket",
            )
        ),
        "top_ideas": _build_ranked_ideas(
            scored,
            largest=True,
        ),
        "bottom_ideas": _build_ranked_ideas(
            scored,
            largest=False,
        ),
    }

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        REPORTS_DIR
        / f"weekly_learning_{timestamp}.md"
    )

    json_path = (
        PROCESSED_DATA_DIR
        / f"weekly_learning_{timestamp}.json"
    )

    _write_markdown_report(
        learning=learning,
        output_path=report_path,
    )

    serializable_learning = {
        key: value
        for key, value in learning.items()
        if key not in [
            "top_ideas",
            "bottom_ideas",
        ]
    }

    serializable_learning["top_ideas"] = (
        learning["top_ideas"].to_dict(
            orient="records"
        )
    )

    serializable_learning["bottom_ideas"] = (
        learning["bottom_ideas"].to_dict(
            orient="records"
        )
    )

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            serializable_learning,
            file,
            indent=4,
            default=str,
        )

    print()
    print("========================================")
    print("Project Stonks Weekly Learning")
    print("========================================")
    print(
        f"Recommendations analyzed: "
        f"{summary['total_recommendations']}"
    )
    print(
        f"Directional recommendations scored: "
        f"{summary['scored_recommendations']}"
    )
    print(
        f"Current winners: "
        f"{summary['current_winners']}"
    )
    print(
        f"Current losers: "
        f"{summary['current_losers']}"
    )
    print(
        f"Current win rate: "
        f"{_format_percent(summary['current_win_rate'])}"
    )
    print(
        f"Average directional return: "
        f"{_format_percent(summary['average_return'])}"
    )
    print(
        f"Median directional return: "
        f"{_format_percent(summary['median_return'])}"
    )
    print(
        f"Average alpha vs. SPY: "
        f"{_format_percent(summary['average_alpha'])}"
    )
    print(f"Report: {report_path}")
    print(f"Structured output: {json_path}")

    learning["report_path"] = str(
        report_path
    )

    learning["json_path"] = str(
        json_path
    )

    return learning


if __name__ == "__main__":
    result = generate_weekly_learning_report()

    if result.get("status") == "ERROR":
        print()
        print("Weekly learning failed.")
        print(result.get("message"))

        if result.get("missing_columns"):
            print(
                f"Missing columns: "
                f"{result['missing_columns']}"
            )