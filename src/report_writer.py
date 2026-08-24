from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd


REPORTS_DIR = Path("reports")


def _safe_read_csv(path):
    if path is None or not Path(path).exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _number(value, default=None):
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _money(value):
    value = _number(value)
    return f"${value:,.2f}" if value is not None else "Unavailable"


def _percent(value):
    value = _number(value)
    return f"{value:.1%}" if value is not None else "Unavailable"


def _whole(value):
    value = _number(value)
    return str(int(value)) if value is not None else "—"


def _allocated_rows(recommendations):
    if recommendations.empty or "allocation_decision" not in recommendations:
        return []
    allocated = recommendations[
        recommendations["allocation_decision"].eq("Allocate")
    ].sort_values("allocation_rank")
    rows = []
    for _, trade in allocated.iterrows():
        premium = _number(trade.get("premium"))
        target_pct = _number(trade.get("profit_target_pct"))
        stop_pct = _number(trade.get("stop_loss_pct"))
        rows.append([
            _whole(trade.get("allocation_rank")),
            str(trade.get("ticker", "")),
            (
                f"{trade.get('option_strategy', '')} "
                f"{trade.get('expiration', '')} "
                f"{_money(trade.get('strike'))}"
            ),
            _whole(trade.get("contracts")),
            _money(trade.get("execution_entry_price")),
            _money(
                premium * (1 + target_pct)
                if premium is not None and target_pct is not None else None
            ),
            _money(
                premium * (1 - stop_pct)
                if premium is not None and stop_pct is not None else None
            ),
            f"{_whole(trade.get('time_stop_dte'))} DTE",
            _money(trade.get("max_risk_dollars")),
            (
                f"{trade.get('institutional_trade_grade', '')} / "
                f"Exec {trade.get('execution_grade', '')}"
            ),
        ])
    return rows


def _position_rows(positions):
    rows = []
    for _, position in positions.iterrows():
        rows.append([
            str(position.get("position_recommendation", "REVIEW")),
            str(position.get("ticker", "")),
            (
                f"{position.get('option_strategy', '')} "
                f"{position.get('expiration', '')} "
                f"{_money(position.get('strike'))} "
                f"x{_whole(position.get('contracts'))}"
            ),
            _money(position.get("current_price")),
            _percent(position.get("pnl_pct")),
            _money(position.get("profit_target")),
            _money(position.get("stop_loss")),
            _whole(position.get("dte")),
            str(position.get("position_reason", "Review required")),
        ])
    return rows


def _markdown_table(headers, rows):
    if not rows:
        return ["None.", ""]
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
        *["| " + " | ".join(row) + " |" for row in rows],
        "",
    ]


def _html_table(headers, rows):
    if not rows:
        return "<p>None.</p>"
    head = "".join(f"<th>{escape(value)}</th>" for value in headers)
    body = "".join(
        "<tr>" + "".join(
            f"<td>{escape(value)}</td>" for value in row
        ) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_daily_report(
    recommendations_path,
    positions_review_path=None,
    output_dir=REPORTS_DIR,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now()
    stem = f"daily_report_{generated:%Y-%m-%d_%H-%M}"
    report_path = output_dir / f"{stem}.md"
    html_path = output_dir / f"{stem}.html"

    recommendations = _safe_read_csv(recommendations_path)
    positions_source_exists = (
        positions_review_path is not None
        and Path(positions_review_path).exists()
    )
    positions = _safe_read_csv(positions_review_path)
    trade_rows = _allocated_rows(recommendations)
    position_rows = _position_rows(positions)
    first = recommendations.iloc[0] if not recommendations.empty else {}
    market = str(first.get("market_regime", "Unavailable"))
    risk = str(first.get("risk_mode", "Unavailable"))
    breadth = str(first.get("breadth_regime", "Unavailable"))
    opportunities = recommendations.get(
        "opportunity_type", pd.Series(dtype=str)
    )
    call_count = int(opportunities.eq("Long Call Candidate").sum())
    put_count = int(opportunities.eq("Long Put Candidate").sum())

    warnings = []
    if recommendations.empty:
        warnings.append("NO RECOMMENDATIONS — do not place new trades.")
    if positions.empty and not positions_source_exists:
        warnings.append(
            "Position analysis unavailable — review open positions manually."
        )
    missing_prices = sum(row[3] == "Unavailable" for row in position_rows)
    if missing_prices:
        warnings.append(
            f"{missing_prices} open position(s) lack current option pricing."
        )

    position_headers = [
        "Action", "Ticker", "Contract", "Current", "P/L",
        "Target", "Stop", "DTE", "Reason",
    ]
    trade_headers = [
        "Rank", "Ticker", "Contract", "Qty", "Entry Limit",
        "Target Exit", "Stop Exit", "Time Stop", "Max Risk", "Grade",
    ]
    summary = (
        f"Market: {market} | Risk: {risk} | Breadth: {breadth}\n"
        f"Candidates: {call_count} calls | {put_count} puts | "
        f"Allocated: {len(trade_rows)}"
    )
    lines = [
        "# Project Stonks — Daily Action Brief", "",
        f"Generated: {generated:%Y-%m-%d %H:%M}", summary, "",
        "## Attention Required", "",
        *(
            [f"- {warning}" for warning in warnings]
            if warnings else ["- No run-health warnings."]
        ),
        "", "## Current Position Actions", "",
        *_markdown_table(position_headers, position_rows),
        "## New Trades to Enter", "",
        *_markdown_table(trade_headers, trade_rows),
        "Only enter trades marked Allocate. Use limit orders; "
        "do not chase above the entry limit.", "",
        "Project Stonks system recommendation. Confirm live quotes "
        "and account risk before order entry.",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")

    warning_html = "".join(
        f"<li>{escape(warning)}</li>" for warning in warnings
    ) or "<li>No run-health warnings.</li>"
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{font-family:Arial,sans-serif;color:#17202a;max-width:1100px;margin:auto;padding:24px}}
h1{{color:#123b5d}} h2{{margin-top:28px}} .summary{{background:#eef5f9;padding:14px;border-radius:6px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th{{background:#123b5d;color:white}}
th,td{{border:1px solid #ccd6dd;padding:8px;text-align:left}} tr:nth-child(even){{background:#f7f9fa}}
.warning{{background:#fff3cd;border-left:5px solid #d39e00;padding:10px}}
.footer{{margin-top:24px;color:#5d6d7e;font-size:12px}}
</style></head><body>
<h1>Project Stonks — Daily Action Brief</h1>
<div class="summary"><b>{generated:%Y-%m-%d %H:%M}</b><br>
Market: {escape(market)} | Risk: {escape(risk)} | Breadth: {escape(breadth)}<br>
Candidates: {call_count} calls | {put_count} puts | Allocated: {len(trade_rows)}</div>
<h2>Attention Required</h2><div class="warning"><ul>{warning_html}</ul></div>
<h2>Current Position Actions</h2>{_html_table(position_headers, position_rows)}
<h2>New Trades to Enter</h2>{_html_table(trade_headers, trade_rows)}
<p><b>Only enter allocated trades. Use limit orders; do not chase above the entry limit.</b></p>
<p class="footer">Project Stonks system recommendation. Confirm live quotes and account risk before order entry.</p>
</body></html>"""
    html_path.write_text(html, encoding="utf-8")
    return report_path
