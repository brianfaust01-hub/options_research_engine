"""
Project Stonks
Contract Selection Audit

Sprint 32D

Purpose
-------
Preserve the complete candidate-contract leaderboard used by the option
selector so contract decisions can be reviewed after the scan.

Outputs
-------
data/processed/contract_audits/
    <ticker>_<timestamp>.csv
    <ticker>_<timestamp>.md

This module does not change contract selection.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent

AUDIT_DIRECTORY = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "contract_audits"
)


AUDIT_COLUMNS = [
    "AuditRank",
    "Ticker",
    "OptionType",
    "StockPrice",
    "contractSymbol",
    "Expiration",
    "DTE",
    "strike",
    "bid",
    "ask",
    "lastPrice",
    "mid",
    "SpreadDollars",
    "spread_pct",
    "QuoteQuality",
    "QuoteExecutable",
    "Affordable",
    "SelectorEligible",
    "RejectionReason",
    "volume",
    "openInterest",
    "impliedVolatility",
    "moneyness",
    "delta",
    "theta",
    "PremiumPctOfStock",
    "ContractScore",
    "SelectionTier",
    "PreferredMinDTE",
    "PreferredMaxDTE",
    "HorizonFitScore",
    "FinalContractScore",
    "ExecutionScore",
    "ExecutionGrade",
    "ExecutionFriction",
    "ExecutionEntryPrice",
    "ExecutionExitPrice",
    "EntryExecutionCostPct",
    "ImmediateLiquidationReturnPct",
    "Selected",
]


def _safe_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_percent(
    value: Any,
) -> str:
    numeric_value = _safe_float(value)

    if numeric_value is None:
        return "N/A"

    return f"{numeric_value:.2%}"


def _format_money(
    value: Any,
) -> str:
    numeric_value = _safe_float(value)

    if numeric_value is None:
        return "N/A"

    return f"${numeric_value:,.2f}"


def _normalize_selected_symbol(
    selected_contract,
) -> str | None:
    if selected_contract is None:
        return None

    try:
        value = selected_contract.get(
            "contractSymbol"
        )
    except AttributeError:
        return None

    if value is None or pd.isna(value):
        return None

    return str(value)


def _prepare_audit_dataframe(
    ticker: str,
    option_type: str,
    stock_price: float,
    candidates: pd.DataFrame,
    selected_contract,
) -> pd.DataFrame:
    audit = candidates.copy()

    selected_symbol = _normalize_selected_symbol(
        selected_contract
    )

    if "contractSymbol" not in audit.columns:
        audit["contractSymbol"] = pd.NA

    audit["Ticker"] = ticker
    audit["OptionType"] = option_type
    audit["StockPrice"] = stock_price

    audit["Selected"] = (
        audit["contractSymbol"].astype(str)
        == str(selected_symbol)
    )

    sort_columns = [
        column
        for column in [
            "FinalContractScore",
            "HorizonFitScore",
            "ContractScore",
            "DTE",
            "PremiumPctOfStock",
        ]
        if column in audit.columns
    ]

    ascending_map = {
        "FinalContractScore": False,
        "HorizonFitScore": False,
        "ContractScore": False,
        "DTE": True,
        "PremiumPctOfStock": True,
    }

    if sort_columns:
        audit = audit.sort_values(
            sort_columns,
            ascending=[
                ascending_map[column]
                for column in sort_columns
            ],
            na_position="last",
        )

    audit = audit.reset_index(
        drop=True
    )

    audit.insert(
        0,
        "AuditRank",
        range(
            1,
            len(audit) + 1,
        ),
    )

    existing_columns = [
        column
        for column in AUDIT_COLUMNS
        if column in audit.columns
    ]

    remaining_columns = [
        column
        for column in audit.columns
        if column not in existing_columns
    ]

    return audit[
        existing_columns
        + remaining_columns
    ]


def _build_summary(
    audit: pd.DataFrame,
) -> dict:
    selected = audit[
        audit["Selected"] == True
    ]

    selected_row = (
        selected.iloc[0]
        if not selected.empty
        else None
    )

    rejection_counts = {}

    if "RejectionReason" in audit.columns:
        rejection_counts = (
            audit.loc[
                audit["Selected"] != True,
                "RejectionReason",
            ]
            .fillna("UNKNOWN")
            .value_counts()
            .to_dict()
        )

    spread_series = pd.to_numeric(
        audit.get(
            "spread_pct",
            pd.Series(dtype=float),
        ),
        errors="coerce",
    ).dropna()

    return {
        "contracts_evaluated": int(
            len(audit)
        ),
        "quote_executable": int(
            audit.get(
                "QuoteExecutable",
                pd.Series(dtype=bool),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "affordable": int(
            audit.get(
                "Affordable",
                pd.Series(dtype=bool),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "selector_eligible": int(
            audit.get(
                "SelectorEligible",
                pd.Series(dtype=bool),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "average_spread": (
            float(spread_series.mean())
            if not spread_series.empty
            else None
        ),
        "median_spread": (
            float(spread_series.median())
            if not spread_series.empty
            else None
        ),
        "selected": selected_row,
        "rejection_counts": rejection_counts,
    }


def _format_leaderboard(
    audit: pd.DataFrame,
    count: int = 20,
) -> pd.DataFrame:
    columns = [
        column
        for column in [
            "AuditRank",
            "Selected",
            "contractSymbol",
            "Expiration",
            "DTE",
            "strike",
            "bid",
            "ask",
            "mid",
            "SpreadDollars",
            "spread_pct",
            "openInterest",
            "volume",
            "delta",
            "theta",
            "ContractScore",
            "HorizonFitScore",
            "FinalContractScore",
            "ExecutionScore",
            "ExecutionGrade",
            "QuoteExecutable",
            "Affordable",
            "SelectorEligible",
            "RejectionReason",
        ]
        if column in audit.columns
    ]

    leaderboard = audit[
        columns
    ].head(count).copy()

    if "spread_pct" in leaderboard.columns:
        leaderboard["spread_pct"] = (
            leaderboard["spread_pct"]
            .apply(_format_percent)
        )

    for column in [
        "bid",
        "ask",
        "mid",
        "SpreadDollars",
    ]:
        if column in leaderboard.columns:
            leaderboard[column] = (
                leaderboard[column]
                .apply(_format_money)
            )

    return leaderboard


def write_contract_audit(
    ticker: str,
    option_type: str,
    stock_price: float,
    candidates: pd.DataFrame,
    selected_contract,
) -> dict:
    if candidates is None or candidates.empty:
        return {
            "status": "SKIPPED",
            "message": "No candidate contracts to audit.",
        }

    AUDIT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit = _prepare_audit_dataframe(
        ticker=ticker,
        option_type=option_type,
        stock_price=stock_price,
        candidates=candidates,
        selected_contract=selected_contract,
    )

    summary = _build_summary(
        audit
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    safe_ticker = (
        str(ticker)
        .upper()
        .replace(
            "/",
            "_",
        )
    )

    csv_path = (
        AUDIT_DIRECTORY
        / f"{safe_ticker}_{timestamp}.csv"
    )

    markdown_path = (
        AUDIT_DIRECTORY
        / f"{safe_ticker}_{timestamp}.md"
    )

    audit.to_csv(
        csv_path,
        index=False,
    )

    lines: list[str] = []

    lines.append(
        "# Project Stonks Contract Selection Audit"
    )
    lines.append("")
    lines.append(
        f"Generated: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    lines.append("")
    lines.append(
        f"- Ticker: **{ticker}**"
    )
    lines.append(
        f"- Option type: **{option_type}**"
    )
    lines.append(
        f"- Underlying price: "
        f"**{_format_money(stock_price)}**"
    )
    lines.append(
        f"- Contracts evaluated: "
        f"**{summary['contracts_evaluated']}**"
    )
    lines.append(
        f"- Valid quoted contracts: "
        f"**{summary['quote_executable']}**"
    )
    lines.append(
        f"- Affordable contracts: "
        f"**{summary['affordable']}**"
    )
    lines.append(
        f"- Selector-eligible contracts: "
        f"**{summary['selector_eligible']}**"
    )
    lines.append(
        f"- Average spread: "
        f"**{_format_percent(summary['average_spread'])}**"
    )
    lines.append(
        f"- Median spread: "
        f"**{_format_percent(summary['median_spread'])}**"
    )
    lines.append("")

    lines.append(
        "## Selected Contract"
    )
    lines.append("")

    selected = summary["selected"]

    if selected is None:
        lines.append(
            "No contract was selected."
        )
    else:
        lines.append(
            f"- Symbol: `{selected.get('contractSymbol')}`"
        )
        lines.append(
            f"- Expiration: "
            f"{selected.get('Expiration')}"
        )
        lines.append(
            f"- Strike: "
            f"{selected.get('strike')}"
        )
        lines.append(
            f"- Bid: "
            f"{_format_money(selected.get('bid'))}"
        )
        lines.append(
            f"- Ask: "
            f"{_format_money(selected.get('ask'))}"
        )
        lines.append(
            f"- Mid: "
            f"{_format_money(selected.get('mid'))}"
        )
        lines.append(
            f"- Spread: "
            f"{_format_money(selected.get('SpreadDollars'))}"
        )
        lines.append(
            f"- Spread percentage: "
            f"{_format_percent(selected.get('spread_pct'))}"
        )
        lines.append(
            f"- Open interest: "
            f"{selected.get('openInterest')}"
        )
        lines.append(
            f"- Volume: "
            f"{selected.get('volume')}"
        )
        lines.append(
            f"- Contract score: "
            f"{selected.get('ContractScore')}"
        )
        lines.append(
            f"- Horizon-fit score: "
            f"{selected.get('HorizonFitScore')}"
        )
        lines.append(
            f"- Final contract score: "
            f"{selected.get('FinalContractScore')}"
        )
        lines.append(
            f"- Execution score: "
            f"{selected.get('ExecutionScore')}"
        )
        lines.append(
            f"- Execution grade: "
            f"{selected.get('ExecutionGrade')}"
        )
        lines.append(
            f"- Affordable: "
            f"{selected.get('Affordable')}"
        )

    lines.append("")
    lines.append(
        "## Rejection Summary"
    )
    lines.append("")

    if not summary["rejection_counts"]:
        lines.append(
            "No rejected candidate reasons were recorded."
        )
    else:
        for reason, count in (
            summary[
                "rejection_counts"
            ].items()
        ):
            lines.append(
                f"- {reason}: {count}"
            )

    lines.append("")
    lines.append(
        "## Top Candidate Leaderboard"
    )
    lines.append("")

    lines.append(
        _format_leaderboard(
            audit
        ).to_markdown(
            index=False
        )
    )

    markdown_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return {
        "status": "PASS",
        "csv_path": str(csv_path),
        "markdown_path": str(markdown_path),
        "contracts_evaluated": int(
            len(audit)
        ),
    }