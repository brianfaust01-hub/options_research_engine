from __future__ import annotations

from datetime import datetime
from html import escape
import json
from pathlib import Path

import pandas as pd


REPORTS_DIR = Path("reports")
HINDSIGHT_DATA_DIR = Path("data") / "processed"


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
            str(trade.get("portfolio_action", "OPEN")),
            str(trade.get("ticker", "")),
            (
                f"{trade.get('option_strategy', '')} "
                f"{trade.get('expiration', '')} "
                f"{_money(trade.get('strike'))}"
            ),
            _whole(trade.get("contracts")),
            _money(trade.get("execution_entry_price")),
            _money(
                _number(trade.get("profit_target_price"),
                    premium * (1 + target_pct)
                    if premium is not None and target_pct is not None else None)
            ),
            _money(
                _number(trade.get("stop_loss_price"),
                    premium * (1 - stop_pct)
                    if premium is not None and stop_pct is not None else None)
            ),
            f"{_whole(trade.get('time_stop_dte'))} DTE",
            _money(trade.get("max_risk_dollars")),
            (
                f"{trade.get('institutional_trade_grade', '')} / "
                f"Exec {trade.get('execution_grade', '')}"
            ),
            (
                f"{_whole(trade.get('expected_move_window_days'))}d / "
                f"{_whole(trade.get('time_edge_score'))} "
                f"{trade.get('time_edge_grade', '')}"
            ),
            (
                str(trade.get("earnings_date"))
                if pd.notna(trade.get("earnings_date"))
                else "Unknown"
            ),
            (
                f"{_whole(trade.get('shadow_conservative_contracts'))}/"
                f"{_whole(trade.get('shadow_balanced_contracts'))}/"
                f"{_whole(trade.get('shadow_aggressive_contracts'))}"
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
            (
                f"Day {_whole(position.get('trading_days_in_position'))} / "
                f"{_whole(position.get('expected_move_window_days'))}; "
                f"deadline {position.get('thesis_deadline') or 'unknown'}"
            ),
            (
                str(position.get("earnings_date"))
                if pd.notna(position.get("earnings_date"))
                else "Unknown"
            ),
            str(position.get("position_reason", "Review required")),
        ])
    return rows


def _qualified_unfunded_rows(recommendations, limit=5):
    """Show the strongest feasible research candidates denied portfolio capital."""
    if recommendations.empty or "allocation_decision" not in recommendations:
        return []
    rows = recommendations[
        recommendations["allocation_decision"].eq("Watch")
        & recommendations.get(
            "portfolio_action_reason", pd.Series("", index=recommendations.index)
        ).astype(str).ne("")
    ].copy()
    if rows.empty:
        return []
    score_column = (
        "portfolio_forward_score"
        if "portfolio_forward_score" in rows else "portfolio_score"
    )
    rows[score_column] = pd.to_numeric(rows.get(score_column), errors="coerce")
    rows = rows.sort_values(score_column, ascending=False).head(limit)
    return [[
        str(row.get("ticker", "")),
        _whole(row.get("allocation_rank")),
        _whole(row.get(score_column)),
        str(row.get("institutional_trade_grade", "")),
        str(row.get("portfolio_action_reason", "")),
    ] for _, row in rows.iterrows()]


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


def _latest_hindsight_health(summary_path=None):
    """Load the latest precomputed research-health summary without running it."""
    if summary_path is not None:
        candidates = [Path(summary_path)]
    else:
        candidates = sorted(
            HINDSIGHT_DATA_DIR.glob("hindsight_analytics_*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    if not candidates or not candidates[0].exists():
        return None
    try:
        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    horizon = payload.get("horizons", {}).get("7D", {})
    allocation = payload.get("allocation_primary", {})
    recent = payload.get("recent_version", {})
    return {
        "generated_at": payload.get("generated_at", "Unknown"),
        "win_rate": horizon.get("win_rate"),
        "evaluated": horizon.get("evaluated", 0),
        "episodes": payload.get("counts", {}).get("thesis_episodes", 0),
        "sample_status": horizon.get("sample_status", "PRELIMINARY"),
        "all_recommendations": allocation.get("all_recommendations", horizon),
        "allocated": allocation.get("allocated", {}),
        "unallocated": allocation.get("unallocated", {}),
        "episode_performance": payload.get("episode_primary", {}),
        "recent_version": recent,
    }


def _health_line(label, metric):
    return (
        f"{label}: {_percent(metric.get('win_rate'))} "
        f"({int(metric.get('evaluated', 0)):,} evaluated; "
        f"{metric.get('sample_status', 'PRELIMINARY')})"
    )


def _portfolio_construction_summary(recommendations, positions):
    source = (
        recommendations.iloc[0] if not recommendations.empty
        else positions.iloc[0] if not positions.empty else {}
    )
    return {
        "nav": _number(source.get("portfolio_account_nav")),
        "deployed": _number(source.get("portfolio_capital_deployed")),
        "utilization": _number(source.get("portfolio_capital_utilization_pct")),
        "cash": _number(source.get("portfolio_intentional_cash")),
        "cash_pct": _number(source.get("portfolio_intentional_cash_pct")),
        "cash_reason": str(source.get("portfolio_intentional_cash_reason", "Unavailable")),
        "stop_loss": _number(source.get("portfolio_expected_loss_at_stops")),
        "stop_loss_pct": _number(source.get("portfolio_expected_loss_at_stops_pct")),
        "premium_risk": _number(source.get("portfolio_long_premium_at_risk")),
        "premium_risk_pct": _number(source.get("portfolio_long_premium_at_risk_pct")),
        "deployed_return": _number(source.get("portfolio_return_on_deployed_capital_pct")),
        "nav_return": _number(source.get("portfolio_return_on_total_nav_pct")),
        "recycled": _number(source.get("portfolio_capital_recycled")),
        "turnover": _number(source.get("portfolio_turnover_pct")),
        "opened": _number(source.get("portfolio_positions_opened"), 0),
        "value_opened": _number(source.get("portfolio_value_opened"), 0),
        "closed": _number(source.get("portfolio_positions_closed"), 0),
        "value_closed": _number(source.get("portfolio_value_closed"), 0),
        "reduced": _number(source.get("portfolio_positions_reduced"), 0),
        "active": _number(source.get("portfolio_active_positions"), 0),
        "active_limit": _number(source.get("portfolio_active_position_limit")),
    }


def build_daily_report(
    recommendations_path,
    positions_review_path=None,
    output_dir=REPORTS_DIR,
    hindsight_summary_path=None,
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
    unfunded_rows = _qualified_unfunded_rows(recommendations)
    hindsight_health = _latest_hindsight_health(hindsight_summary_path)
    construction = _portfolio_construction_summary(recommendations, positions)
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
    if "earnings_status" in recommendations:
        unknown_earnings = recommendations[
            recommendations["allocation_decision"].eq("Allocate")
            & recommendations["earnings_status"].eq("UNKNOWN")
        ]
        if not unknown_earnings.empty:
            warnings.append(
                "Earnings date unavailable for allocated trade(s): "
                + ", ".join(unknown_earnings["ticker"].astype(str))
                + ". Confirm manually before entry."
            )
    if "earnings_allocation_override" in recommendations:
        blocked = recommendations[
            recommendations["earnings_allocation_override"]
            .fillna(False).astype(bool)
        ]
        if not blocked.empty:
            warnings.append(
                "Blocked from allocation because earnings falls inside the "
                "thesis window: "
                + ", ".join(blocked["ticker"].astype(str))
            )

    position_headers = [
        "Action", "Ticker", "Contract", "Current", "P/L",
        "Target", "Stop", "DTE", "Thesis Clock", "Earnings", "Reason",
    ]
    trade_headers = [
        "Rank", "Action", "Ticker", "Contract", "Qty", "Entry Limit",
        "Target Exit", "Stop Exit", "Time Stop", "Max Risk", "Grade",
        "Hold / Time Edge", "Earnings", "Shadow C/B/A",
    ]
    unfunded_headers = ["Ticker", "Rank", "Portfolio Score", "Grade", "Why Unfunded"]
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
        "## Portfolio Construction", "",
        f"- Account NAV: {_money(construction['nav'])}",
        f"- Capital deployed: {_money(construction['deployed'])} "
        f"({_percent(construction['utilization'])})",
        f"- Intentional cash: {_money(construction['cash'])} "
        f"({_percent(construction['cash_pct'])})",
        f"- Cash rationale: {construction['cash_reason']}",
        f"- Expected loss at stops: {_money(construction['stop_loss'])} "
        f"({_percent(construction['stop_loss_pct'])} of NAV)",
        f"- Full long-premium exposure: {_money(construction['premium_risk'])} "
        f"({_percent(construction['premium_risk_pct'])} of NAV)",
        f"- Active portfolio slots: {int(construction['active'])} / "
        f"{_whole(construction['active_limit'])}",
        f"- Open-position return on deployed capital: {_percent(construction['deployed_return'])}",
        f"- Open-position return on total NAV: {_percent(construction['nav_return'])}",
        f"- Capital recycled: {_money(construction['recycled'])}; "
        f"turnover {_percent(construction['turnover'])}",
        f"- Actions: {int(construction['opened'])} opened/added "
        f"({_money(construction['value_opened'])}), {int(construction['closed'])} closed "
        f"({_money(construction['value_closed'])}), {int(construction['reduced'])} reduced",
        "",
        "## New Trades to Enter", "",
        *_markdown_table(trade_headers, trade_rows),
        "Shadow C/B/A shows research-only Conservative, Balanced, and "
        "Aggressive contract counts. Execute the production Qty until shadow "
        "sizing is validated.", "",
        "Only enter trades marked Allocate. Use limit orders; "
        "do not chase above the entry limit.", "",
        "## Qualified but Unfunded", "",
        "These candidates remain research evidence but did not earn a funded portfolio slot.", "",
        *_markdown_table(unfunded_headers, unfunded_rows),
        "## Research Health (Not Trading Guidance)", "",
        *(
            [
                "7-day directional outcomes:",
                _health_line("All recommendations", hindsight_health["all_recommendations"]),
                _health_line("Allocated recommendations", hindsight_health["allocated"]),
                _health_line("Known unallocated recommendations", hindsight_health["unallocated"]),
                _health_line("Deduplicated thesis episodes", hindsight_health["episode_performance"]),
                *(
                    [
                        f"Latest version: {hindsight_health['recent_version'].get('version')}",
                        _health_line(
                            "Latest-version allocated",
                            hindsight_health["recent_version"].get("allocation", {}).get("allocated", {}),
                        ),
                    ]
                    if hindsight_health["recent_version"].get("version") else []
                ),
                f"Analytics generated: {hindsight_health['generated_at']}",
            ]
            if hindsight_health else
            ["No fixed-horizon analytics report is available yet."]
        ), "",
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
<h2>Portfolio Construction</h2>
<ul>
<li>Account NAV: {_money(construction['nav'])}</li>
<li>Capital deployed: {_money(construction['deployed'])} ({_percent(construction['utilization'])})</li>
<li>Intentional cash: {_money(construction['cash'])} ({_percent(construction['cash_pct'])})</li>
<li>Cash rationale: {escape(construction['cash_reason'])}</li>
<li>Expected loss at stops: {_money(construction['stop_loss'])} ({_percent(construction['stop_loss_pct'])} of NAV)</li>
<li>Full long-premium exposure: {_money(construction['premium_risk'])} ({_percent(construction['premium_risk_pct'])} of NAV)</li>
<li>Active portfolio slots: {int(construction['active'])} / {_whole(construction['active_limit'])}</li>
<li>Open-position return on deployed capital: {_percent(construction['deployed_return'])}</li>
<li>Open-position return on total NAV: {_percent(construction['nav_return'])}</li>
<li>Capital recycled: {_money(construction['recycled'])}; turnover {_percent(construction['turnover'])}</li>
<li>Actions: {int(construction['opened'])} opened/added ({_money(construction['value_opened'])}), {int(construction['closed'])} closed ({_money(construction['value_closed'])}), {int(construction['reduced'])} reduced</li>
</ul>
<h2>New Trades to Enter</h2>{_html_table(trade_headers, trade_rows)}
<p><b>Shadow C/B/A is research-only.</b> Execute the production Qty until the
shadow sizing profiles are validated.</p>
<p><b>Only enter allocated trades. Use limit orders; do not chase above the entry limit.</b></p>
<h2>Qualified but Unfunded</h2>
<p>These candidates remain research evidence but did not earn a funded portfolio slot.</p>
{_html_table(unfunded_headers, unfunded_rows)}
<h2>Research Health (Not Trading Guidance)</h2>
{
    '<p><b>7-day directional outcomes</b><br>'
    + escape(_health_line('All recommendations', hindsight_health['all_recommendations']))
    + '<br>' + escape(_health_line('Allocated recommendations', hindsight_health['allocated']))
    + '<br>' + escape(_health_line('Known unallocated recommendations', hindsight_health['unallocated']))
    + '<br>' + escape(_health_line('Deduplicated thesis episodes', hindsight_health['episode_performance']))
    + (
        '<br>Latest version: ' + escape(str(hindsight_health['recent_version'].get('version')))
        + '<br>' + escape(_health_line(
            'Latest-version allocated',
            hindsight_health['recent_version'].get('allocation', {}).get('allocated', {}),
        ))
        if hindsight_health['recent_version'].get('version') else ''
    )
    + '<br>Analytics generated: ' + escape(str(hindsight_health['generated_at'])) + '</p>'
    if hindsight_health else '<p>No fixed-horizon analytics report is available yet.</p>'
}
<p class="footer">Project Stonks system recommendation. Confirm live quotes and account risk before order entry.</p>
</body></html>"""
    html_path.write_text(html, encoding="utf-8")
    return report_path
