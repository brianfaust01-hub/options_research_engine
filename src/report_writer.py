from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from paper_portfolio import get_open_positions


REPORTS_DIR = Path("reports")


def _safe_read_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


def build_daily_report(
    recommendations_path: str | Path,
    positions_review_path: str | Path | None = None,
    output_dir: str | Path = REPORTS_DIR,
) -> Path:

    output_dir = Path(output_dir)
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    report_path = output_dir / f"daily_report_{timestamp}.md"

    recommendations = _safe_read_csv(
        recommendations_path
    )

    portfolio = get_open_positions()

    positions = (
        _safe_read_csv(positions_review_path)
        if positions_review_path
        else pd.DataFrame()
    )

    lines = []

    lines.append("# Project Stonks Daily Report")
    lines.append("")
    lines.append(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    lines.append("")

    #
    # Open Portfolio
    #

    lines.append("## Open Paper Portfolio")
    lines.append("")

    if portfolio.empty:

        lines.append("No open paper positions.")

    else:

        display_cols = [
            c
            for c in [
                "Ticker",
                "OptionStrategy",
                "Expiration",
                "Strike",
                "Contracts",
                "EntryPremium",
                "CurrentPremium",
                "PnLPct",
            ]
            if c in portfolio.columns
        ]



        if display_cols:

            lines.append(
                portfolio[display_cols].to_markdown(
                    index=False
                )
            )

        else:

            lines.append(
                portfolio.to_markdown(
                    index=False
                )
            )

    lines.append("")

    #
    # Recommendations
    #

    lines.append("## New Recommendations")
    lines.append("")

    if recommendations.empty:

        lines.append(
            "No recommendation file found or no recommendations generated."
        )

    else:

        display_cols = [
            c
            for c in [
                "Ticker",
                "Action",
                "Direction",
                "Confidence",
                "RecommendedCapital",
                "ContractSymbol",
                "Expiration",
                "Strike",
                "Reason",
            ]
            if c in recommendations.columns
        ]

        if display_cols:

            lines.append(
                recommendations[
                    display_cols
                ].to_markdown(
                    index=False
                )
            )

        else:

            lines.append(
                recommendations.head(
                    25
                ).to_markdown(
                    index=False
                )
            )

    lines.append("")

    #
    # Position Review
    #

    lines.append("## Position Review")
    lines.append("")

    if positions.empty:

        lines.append(
            "No position review generated."
        )

    else:

        lines.append(
            positions.to_markdown(
                index=False
            )
        )

    report_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return report_path