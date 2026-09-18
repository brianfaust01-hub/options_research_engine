"""Read-only config-to-evidence checklist. Collection is not calibration readiness."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
import hashlib
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from uuid import uuid4

from config import POLICY_ERA_ID, POLICY_ERA_BASELINE_DATE

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = set("PROJECT_NAME VERSION CONFIG_VERSION POLICY_ERA_ID POLICY_ERA_BASELINE_DATE READINESS_TARGET_WEEKS READINESS_CONFIG_REVIEW_WEEKS READINESS_TARGET_EPISODES READINESS_CONFIG_REVIEW_EPISODES READINESS_EXECUTION_TARGET READINESS_SHADOW_MATCHED_TARGET PAPER_TRADING TEST_MODE ENABLE_JOURNAL_WRITES TEST_TICKERS LOOKBACK_PERIOD INTERVAL DEBUG_OPTION_SELECTOR OPEN_PAPER_POSITIONS BASE_DIR DATA_DIR RAW_DATA_DIR PROCESSED_DATA_DIR REPORTS_DIR JOURNAL_DIR EXECUTION_ENGINE_ENABLED EXECUTION_ENGINE_TEST_MODE SHADOW_EXIT_POLICY_ENABLED SHADOW_EXIT_POLICY_VERSION".split())

# Explicit inventory: an unknown future setting stays UNMAPPED, not silently passed.
FAMILIES = {
    "Research signal calibration": {
        "settings": "MIN_OPPORTUNITY_SCORE",
        "fields": "ResearchScore OpportunityScore DirectionalConviction Confidence ConfigVersion PolicyEraID",
        "population": "directional", "blockers": []},
    "Institutional score calibration": {
        "settings": "INSTITUTIONAL_RESEARCH_WEIGHT INSTITUTIONAL_CONTRACT_WEIGHT INSTITUTIONAL_EXECUTION_WEIGHT INSTITUTIONAL_TRADE_QUALITY_WEIGHT INSTITUTIONAL_MARKET_WEIGHT INSTITUTIONAL_DIVERSIFICATION_WEIGHT",
        "fields": "InstitutionalTradeScore institutional_research_score institutional_contract_score institutional_execution_score institutional_trade_quality_score ConfigVersion PolicyEraID",
        "population": "selected", "blockers": []},
    "Time edge and thesis window": {
        "settings": "", "fields": "time_edge_score expected_move_window_days Return1D Return3D Return5D",
        "population": "directional", "blockers": ["Time-edge weights are partly code-defined; source/version review is required before changing them."]},
    "Contract selection": {
        "settings": "MIN_EXECUTABLE_CONTRACT_SCORE MIN_OPTION_DTE MIN_LONG_PREMIUM_DTE MAX_OPTION_DTE MIN_OPTION_PREMIUM MAX_PREMIUM_PCT_OF_STOCK MIN_MONEYNESS MAX_MONEYNESS",
        "fields": "contract_symbol expiration strike premium contract_score broker_delta implied_volatility",
        "population": "selected", "blockers": ["Unselected alternative contracts and their rankings are not verified by this audit; selected-contract outcomes cannot prove a different contract would outperform.", "Contract scores may exist in legacy notes; this audit checks structured fields only. Verify recoverable note/snapshot evidence before declaring history lost."]},
    "Execution and liquidity": {
        "settings": "RESEARCH_PRICE_METHOD EXECUTION_ENTRY_METHOD EXECUTION_EXIT_METHOD EXECUTION_SPREAD_GRADE_A EXECUTION_SPREAD_GRADE_B EXECUTION_SPREAD_GRADE_C EXECUTION_SPREAD_GRADE_D EXECUTION_SPREAD_WEIGHT EXECUTION_OPEN_INTEREST_WEIGHT EXECUTION_VOLUME_WEIGHT TARGET_SPREAD_PCT MAX_ACCEPTABLE_SPREAD_PCT MIN_EXECUTION_SCORE MIN_EXECUTION_GRADE",
        "fields": "execution_entry_price execution_exit_price execution_score option_volume option_open_interest entry_execution_cost_pct",
        "population": "selected", "blockers": ["Quotes and modeled prices are not fills. Recommendation-to-order/fill/cancel linkage and slippage attribution require separate verified evidence."]},
    "Allocation and capital": {
        "settings": "PAPER_PORTFOLIO_VALUE MAX_POSITION_SIZE_PCT MAX_TRADE_RISK_PCT MAX_ALLOCATED_TRADES PORTFOLIO_ARBITRATION_CANDIDATE_POOL PORTFOLIO_MIN_FORWARD_SCORE PORTFOLIO_INCUMBENT_ADVANTAGE MAX_CAPITAL_UTILIZATION_PCT MAX_AGGREGATE_STOP_LOSS_PCT MAX_SECTOR_EXPOSURE_PCT MAX_THEME_EXPOSURE_PCT MAX_ACTIVE_PORTFOLIO_POSITIONS MIN_POSITION_VALUE_PCT MAX_CONTRACTS_PER_POSITION MAX_LONG_PREMIUM_AT_RISK_PCT DYNAMIC_CAPITAL_UTILIZATION_ENABLED DYNAMIC_UTILIZATION_MIN_PCT DYNAMIC_UTILIZATION_MAX_PCT DYNAMIC_UTILIZATION_QUALITY_FLOOR DYNAMIC_UTILIZATION_QUALITY_CEILING DYNAMIC_UTILIZATION_DIVERSIFIED_TICKERS PORTFOLIO_NEW_POSITION_PENALTY PORTFOLIO_SECTOR_REPEAT_PENALTY PORTFOLIO_THEME_REPEAT_PENALTY PORTFOLIO_SCORE_USE_EXECUTION PORTFOLIO_SCORE_USE_TRADE_QUALITY PORTFOLIO_SCORE_MARKET_MULTIPLIER",
        "fields": "allocation_decision portfolio_score portfolio_action portfolio_action_reason portfolio_account_nav portfolio_capital_deployed sector theme",
        "population": "selected", "blockers": ["Complete exposure classification, measured correlations, working-order reserves, and a replayable holdings/candidate state remain required for allocation counterfactuals."]},
    "Direction and market context": {
        "settings": "ALLOW_CALLS_IN_BEARISH_REGIME ALLOW_PUTS_IN_BULLISH_REGIME DEFENSIVE_ALLOCATION_MULTIPLIER SELECTIVE_ALLOCATION_MULTIPLIER RISK_ON_ALLOCATION_MULTIPLIER",
        "fields": "Direction market_regime risk_mode breadth_regime bullish_score bearish_score",
        "population": "directional", "blockers": ["Multiple entry weeks and market conditions are required; many same-day tickers are not independent market experiments."]},
    "Stops, targets, and profit protection": {
        "settings": "SHADOW_EXIT_MIN_SAMPLE_SIZE SHADOW_EXIT_MAX_STOP_LOSS_PCT SHADOW_EXIT_MIN_STOP_LOSS_PCT SHADOW_EXIT_MIN_TARGET_PCT SHADOW_EXIT_MAX_TARGET_PCT SHADOW_EXIT_SLIPPAGE_PCT",
        "fields": "contract_symbol stop_loss_price profit_target_price expected_move_window_days exit_reference_price",
        "population": "selected", "blockers": ["Daily quotes do not establish intraday stop-first/target-first ordering or complete entry-to-exit paths; dense timestamped bid/ask paths and gap/ambiguity handling are required.", "Production adaptive exits and profit-protection constants also live in exit_rules.py; they require a code-level policy review, not only config.py inventory."]},
    "Greeks and volatility": {
        "settings": "", "fields": "broker_delta broker_gamma broker_theta broker_vega implied_volatility theta_drag_pct_per_day gamma_per_premium vega_per_premium",
        "population": "selected", "blockers": ["Exact-contract IV is not a constant-maturity underlying benchmark. Conventional IV rank/percentile requires a defined benchmark, roll handling, and sufficient history.", "Underlying outcomes cannot establish Greek/IV effects on actual option returns."]},
    "Earnings guard": {
        "settings": "", "fields": "earnings_date earnings_status earnings_within_thesis_window",
        "population": "selected", "blockers": ["Unknown/unverified earnings dates cannot be treated as safe; event outcomes must be compared within direction and entry cohort."]},
    "Policy provenance": {
        "settings": "", "fields": "PolicyEvidenceFingerprint PolicyEvidencePath PolicyEvidenceStatus",
        "population": "directional", "blockers": ["New policy archives are forward-only. Fingerprints identify source/config state; they do not change the policy era or prove a complete portfolio replay."]},
}

ACTION_PLAN = [
    {"priority": "P0", "item": "Intraday option exit paths", "state": "SAMPLED_COLLECTOR_IMPLEMENTED_PENDING_ACTIVATION_AND_COVERAGE",
     "recovery": "Missed broker quotes cannot be reconstructed reliably later.",
     "six_week_impact": "Blocks precise stop/target challengers, not directional baseline review.",
     "next_action": "Register the independent one-minute task under the account owner; verify --health-date coverage and attributed entry alignment. Sampled quotes retain between-sample ambiguity and are not automatically admitted to empirical calibration."},
    {"priority": "P0", "item": "Contract scores and selection comparison set", "state": "FORWARD_CAPTURE_IMPLEMENTED",
     "recovery": "Some legacy scores are in notes; prior alternative sets may be unrecoverable.",
     "six_week_impact": "Supports contract-scoring review; alternative quote paths remain a separate gap.",
     "next_action": "Verify structured scores and thin selection_evidence_json in the next scan; do not infer alternative option returns from one selection snapshot."},
    {"priority": "P0", "item": "Exact policy/config provenance", "state": "FORWARD_CAPTURE_IMPLEMENTED",
     "recovery": "Committed Git versions may recover old sources; runtime state is not guaranteed.",
     "six_week_impact": "Prevents silently pooling observations from different source states.",
     "next_action": "Verify new recommendation fingerprints and immutable policy archives; keep existing policy era and baseline unchanged."},
    {"priority": "P1", "item": "Underlying IV benchmark", "state": "OPEN",
     "recovery": "Daily exact-contract IV does not reconstruct constant-maturity underlying IV.",
     "six_week_impact": "Blocks conventional IV-rank tuning; raw-IV and Greek cuts remain available.",
     "next_action": "Define a consistent maturity/moneyness benchmark and roll treatment before starting its history; do not silently label contract IV history as underlying IV rank."},
    {"priority": "P1", "item": "Earnings and exposure completeness", "state": "OPEN",
     "recovery": "Mappings and dates may be separately enriched with provenance; historical as-known context must remain immutable.",
     "six_week_impact": "Limits event and concentration cuts; does not invalidate all signal outcomes.",
     "next_action": "Measure allocated versus unallocated coverage separately, then fill forward research coverage without modifying earnings gates or exposure limits."},
    {"priority": "P1", "item": "Broker order/fill/capital attribution", "state": "OPEN",
     "recovery": "Broker exports preserve fills; missing order/cancel/reserve state may not be recoverable.",
     "six_week_impact": "Required for net option execution expectancy, not just underlying win rates.",
     "next_action": "Maintain regular statement imports and validate matched recommendation IDs, fees, exits, and daily NAV; design order/cancel linkage before live promotion."},
    {"priority": "P2", "item": "Independent weekly cohorts", "state": "ACCUMULATING",
     "recovery": "Already captured observations remain valid within their coverage boundaries.",
     "six_week_impact": "Core directional review needs more entry weeks, regimes, and matched out-of-sample support.",
     "next_action": "Continue the frozen baseline; review collection health weekly and keep unmatched or incomplete option evidence separate."},
]
NUMERIC = set("ResearchScore OpportunityScore DirectionalConviction InstitutionalTradeScore institutional_research_score institutional_contract_score institutional_execution_score institutional_trade_quality_score time_edge_score expected_move_window_days Return1D Return3D Return5D strike premium contract_score broker_delta implied_volatility execution_entry_price execution_exit_price execution_score option_volume option_open_interest entry_execution_cost_pct portfolio_score portfolio_account_nav portfolio_capital_deployed bullish_score bearish_score stop_loss_price profit_target_price exit_reference_price broker_gamma broker_theta broker_vega theta_drag_pct_per_day gamma_per_premium vega_per_premium".split())
NUMERIC.add("Confidence")
MISSING = {"", "nan", "none", "null", "n/a", "unknown", "not_checked", "unavailable_no_history"}


def key(name):
    return name.replace("_", "").casefold()


def value(row, name):
    direct = row.get(name)
    if direct is not None and str(direct).strip().casefold() not in MISSING:
        return direct
    if "__evidence_aliases__" not in row:
        aliases = {}
        for k, v in row.items():
            if v is not None and str(v).strip().casefold() not in MISSING:
                aliases.setdefault(key(k), v)
        row["__evidence_aliases__"] = aliases
    return row["__evidence_aliases__"].get(key(name))


def valid(row, name):
    v = value(row, name)
    if v is None:
        return False
    if name in NUMERIC:
        try:
            n = float(v)
            if not math.isfinite(n) or n == -999:
                return False
            if name == "broker_delta":
                return -1 <= n <= 1
            if name == "implied_volatility":
                return 0 < n < 10
            return True
        except (ValueError, TypeError):
            return False
    return True


def rows(path):
    if path is None or not Path(path).exists():
        return []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def config_inventory(path):
    names = set()
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8-sig"))):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        names.update(t.id for t in targets if isinstance(t, ast.Name) and t.id.isupper())
    mapped = {setting: family for family, spec in FAMILIES.items() for setting in spec["settings"].split()}
    return {name: mapped.get(name, "OPERATIONAL_OR_GOVERNANCE" if name in RUNTIME else "UNMAPPED")
            for name in sorted(names)}


def field_coverage(population, field):
    available = [r for r in population if valid(r, field)]
    dates = sorted({str(value(r, "RecommendationDate"))[:10] for r in available if value(r, "RecommendationDate")})
    return {"observations": len(population), "available": len(available),
        "missing": len(population) - len(available),
        "coverage_pct": len(available) / len(population) if population else None,
        "first_available_date": dates[0] if dates else None,
        "last_available_date": dates[-1] if dates else None,
        "entry_dates": len(dates)}


def audit(root=ROOT, *, policy_era=POLICY_ERA_ID, baseline=POLICY_ERA_BASELINE_DATE, now=None):
    root = Path(root)
    today = (now or datetime.now(timezone.utc)).date().isoformat()
    source = root / "data" / "trade_journal.csv"
    raw = rows(source)
    current = [r for r in raw if value(r, "PolicyEraID") == policy_era
        and baseline <= str(value(r, "RecommendationDate") or "")[:10] <= today]
    identifiers = [value(r, "RecommendationID") for r in current]
    duplicates = len([x for x in identifiers if x]) - len({x for x in identifiers if x})
    unique = {}
    for i, row in enumerate(current):
        unique.setdefault(value(row, "RecommendationID") or f"MISSING-ID-{i}", row)
    current = list(unique.values())
    directional = [r for r in current if str(value(r, "Direction")).upper() in {"BULLISH", "BEARISH"}]
    selected = [r for r in directional if str(value(r, "option_strategy")).casefold() in {"long call", "long put"}
                and valid(r, "expiration") and valid(r, "strike") and valid(r, "premium")]
    findings = []
    for family, spec in FAMILIES.items():
        population = selected if spec["population"] == "selected" else directional
        coverage = {field: field_coverage(population, field) for field in spec["fields"].split()}
        complete_rows = sum(all(valid(r, field) for field in coverage) for r in population)
        status = "NO_POPULATION" if not population else "COLLECTION_PRESENT" if complete_rows == len(population) else "PARTIAL_COLLECTION" if complete_rows else "COLLECTION_GAP"
        findings.append({"family": family, "settings": spec["settings"].split(),
            "population": spec["population"], "collection_status": status,
            "joint_complete_observations": complete_rows, "fields": coverage,
            "analysis_limitations": spec["blockers"],
            "next_action": "Keep collecting independent entry cohorts; review joint completeness and matched outcomes before tuning." if status == "COLLECTION_PRESENT" else
                "Inspect missing fields and forward capture/projection; do not backfill immutable history."})
    processed = root / "data" / "processed"
    candidates = sorted(processed.glob("research_hindsight_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    hindsight_path = candidates[0] if candidates else None
    hindsight = {value(r, "RecommendationID"): r for r in rows(hindsight_path)
                 if value(r, "RecommendationID") in unique}
    outcomes = {}
    for days in [3, 5, 7, 14, 30]:
        complete = [r for r in directional if value(hindsight.get(value(r, "RecommendationID"), {}), f"Horizon{days}DStatus") == "COMPLETE"]
        numeric = [r for r in complete if valid_numeric(value(hindsight.get(value(r, "RecommendationID"), {}), f"Horizon{days}DDirectionalReturnPct"))]
        outcomes[f"{days}D"] = {"directional_recommendations": len(directional),
            "complete_numeric": len(numeric), "complete_but_missing_return": len(complete)-len(numeric),
            "not_complete_or_not_in_latest_hindsight": len(directional)-len(complete),
            "entry_dates": len({str(value(r, 'RecommendationDate'))[:10] for r in numeric})}
    observations = []
    issues = []
    quote_dir = processed / "option_observations"
    for path in sorted(quote_dir.glob("sample_*.json")):
        try:
            observations.extend(json.loads(path.read_text(encoding="utf-8"))["observations"])
        except (ValueError, KeyError, OSError):
            issues.append(f"Unreadable quote artifact: {path.name}")
    current_ids = {value(r, "RecommendationID") for r in selected}
    linked = [o for o in observations if any(r.get("recommendation_id") in current_ids for r in o.get("recommendations", []))]
    usable = [o for o in linked if o.get("quote_status") == "OBSERVED" and o.get("eligible_for_sampled_returns") is True
              and valid_numeric(o.get("bid")) and valid_numeric(o.get("ask"))
              and 0 <= float(o['bid']) <= float(o['ask']) and float(o['ask']) > 0 and o.get("quote_at")]
    # Dates below are actual usable measurement dates, not policy-era backdates.
    quote_dates = sorted({o.get("quote_at", "")[:10] for o in usable})
    iv_usable = [o for o in usable if o.get("iv_status") == "OBSERVED" and valid_numeric(o.get("iv_decimal")) and float(o["iv_decimal"]) > 0]
    snapshot_rows = rows(root / "data" / "account_state_snapshots.csv")
    snapshots = [r for r in snapshot_rows if baseline <= str(r.get("AsOfDate", "")) <= today]
    inventory = config_inventory(root / "src" / "config.py")
    return {"generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "policy_era": policy_era, "baseline_date": baseline,
        "collection_is_not_calibration_readiness": True, "production_policy_changed": False,
        "journal_source": str(source), "hindsight_source": str(hindsight_path) if hindsight_path else None,
        "config_source_sha256": hashlib.sha256((root / 'src' / 'config.py').read_bytes()).hexdigest(),
        "population": {"current_unique_recommendations": len(current), "directional": len(directional),
            "selected_contract": len(selected), "duplicate_ids": duplicates,
            "missing_ids": sum(x is None for x in identifiers),
            "entry_dates": len({str(value(r, 'RecommendationDate'))[:10] for r in directional})},
        "config_inventory": inventory, "unmapped_settings": [k for k,v in inventory.items() if v == "UNMAPPED"],
        "prioritized_action_plan": ACTION_PLAN,
        "families": findings, "outcomes": outcomes,
        "option_quotes": {"linked_observations": len(linked), "usable_observations": len(usable),
            "usable_contracts": len({o.get('contract_symbol') for o in usable}),
            "quote_status_counts": dict(Counter(o.get('quote_status', 'UNKNOWN') for o in linked)),
            "first_usable_date": quote_dates[0] if quote_dates else None,
            "last_usable_date": quote_dates[-1] if quote_dates else None,
            "usable_quote_dates": len(quote_dates), "usable_iv_observations": len(iv_usable),
            "intraday_exit_ordering": "NOT_VERIFIED_BY_DAILY_SNAPSHOTS",
            "underlying_iv_benchmark": "NOT_VERIFIED", "artifact_issues": issues},
        "capital_evidence": {"snapshot_dates": sorted({r['AsOfDate'] for r in snapshots}),
            "quality_counts": dict(Counter(r.get('DataQualityStatus', 'UNKNOWN') for r in snapshots)),
            "ledger_events": len(rows(root / 'data' / 'capital_ledger.csv')),
            "limitation": "Event presence does not verify fill attribution, round trips, daily continuity, reserves, or capital-weighted returns."}}


def valid_numeric(v):
    try:
        return v is not None and math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def markdown(result):
    lines = ["# Config-to-Evidence Audit", "", f"Generated: {result['generated_at']}",
        f"Policy era: {result['policy_era']} (baseline {result['baseline_date']})", "",
        "Collection presence is NOT permission to tune or real-money readiness. Counts are unique recommendation observations, not deduplicated thesis episodes. No source data or policy was changed.", "",
        f"Population: {result['population']}", "", "## Config inventory", "",
        f"Unmapped settings: {', '.join(result['unmapped_settings']) or 'none'}", "",
        "Operational/governance settings are explicitly excluded; code-defined constants require manual review.", ""]
    lines.extend(["## Prioritized measurement work", "",
        "| Priority | Gap / work | State | Six-week impact |", "|---|---|---|---|"])
    for action in result['prioritized_action_plan']:
        lines.append(f"| {action['priority']} | {action['item']} | {action['state']} | {action['six_week_impact']} |")
    lines.append('')
    for action in result['prioritized_action_plan']:
        lines.extend([f"- {action['item']}: {action['recovery']} Next: {action['next_action']}"])
    lines.append('')
    for item in result["families"]:
        lines.extend([f"## {item['family']}", "", f"Collection: {item['collection_status']}; joint-complete observations: {item['joint_complete_observations']}",
            f"Settings: {', '.join(item['settings']) or 'code-defined / observation-only'}", "",
            "| Measurement | Available / expected | First available | Entry dates |",
            "|---|---:|---|---:|"])
        for field, c in item["fields"].items():
            lines.append(f"| {field} | {c['available']} / {c['observations']} | {c['first_available_date'] or 'unavailable'} | {c['entry_dates']} |")
        lines.extend(["", *[f"- {b}" for b in item["analysis_limitations"]], "", item["next_action"], ""])
    lines.extend(["## Fixed-horizon outcome coverage", "", "```json", json.dumps(result['outcomes'], indent=2), "```", "",
        "## Option quotes and IV", "", "```json", json.dumps(result['option_quotes'], indent=2), "```", "",
        "## Capital evidence", "", "```json", json.dumps(result['capital_evidence'], indent=2), "```", "",
        "Before any config experiment: verify required measurements and joint coverage, deduplicate thesis episodes, separate entry cohorts/directions/regimes, freeze a baseline, and use a matched out-of-sample challenger. Missing measurements need instrumentation; immature observations need time.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, help="Optional new timestamped JSON/Markdown reports; sources remain read-only")
    args = parser.parse_args()
    result = audit(args.root)
    gaps = [f['family'] for f in result['families'] if f['collection_status'] != 'COLLECTION_PRESENT']
    print(f"Config evidence audit: {len(result['config_inventory'])} settings inventoried; "
          f"{len(result['unmapped_settings'])} unmapped; {len(gaps)} families with incomplete structured collection.")
    if gaps:
        print("Measurement checklist: " + '; '.join(gaps))
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stem = 'config_evidence_audit_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid4().hex[:6]
        for suffix, content in [('json', json.dumps(result, indent=2)), ('md', markdown(result))]:
            path = args.output_dir / f'{stem}.{suffix}'
            with path.open('x', encoding='utf-8') as handle:
                handle.write(content)
            print(f"Evidence audit: {path}")
    else:
        print(markdown(result))


if __name__ == '__main__':
    main()
