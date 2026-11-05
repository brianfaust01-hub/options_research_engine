"""Production-only risk overlay; frozen research allocators never import this.

One concurrent oil-linked ticker, including actual incumbents. Conservative
shared-driver grouping, not an estimate of crude beta or a directional hedge.
"""
import hashlib
from pathlib import Path

VERSION = 'OIL-CONCURRENT-2026-11-04-v1'
MAX_OIL_TICKERS = 1
OIL_GROUPS = {
    'integrated': 'XOM CVX SHEL BP TTE EQNR SU IMO PBR EC YPF',
    'producers': 'COP EOG OXY DVN FANG APA CTRA OVV PR CHRD SM MTDR MUR CRC NOG CIVI CNQ WDS REPX VET BTE ERF',
    'refining': 'MPC PSX VLO DINO PBF DK CVI',
    'services': 'SLB HAL BKR FTI NOV CHX WFRD OII HP PTEN NBR RIG VAL NE LBRT PUMP',
    'midstream': 'KMI WMB OKE TRGP EPD ET MPLX ENB TRP PAA PAGP LNG CQP WES HESM AM',
    'energy_funds': 'XLE XOP OIH VDE IYE IEO FENY IXC USO BNO UCO SCO',
}
OIL_TICKERS = {t for group in OIL_GROUPS.values() for t in group.split()}


def oil_linked(row):
    ticker = str(row.get('ticker', row.get('Ticker', ''))).upper().strip()
    if ticker in OIL_TICKERS:
        return True
    # Catch unmapped candidates when upstream industry/theme metadata exists.
    metadata = ' '.join(str(row.get(k, '')) for k in ('industry', 'Industry', 'theme', 'Theme')).lower()
    return any(term in metadata for term in ('oil', 'petroleum', 'refin', 'drilling', 'midstream', 'pipeline'))


def arbitrate_with_oil_guard(base, candidates, positions, account_nav, **kwargs):
    """Block excess new oil names, retaining research actions for shadow reuse.

    Existing oil names consume slots even when a close is recommended: a
    recommendation is not a confirmed broker exit. No forced sale or order.
    """
    candidate_input = candidates.copy(deep=True)
    held = {str(row.get('ticker', row.get('Ticker', ''))).upper()
            for _, row in positions.iterrows() if oil_linked(row)}
    oil_rows = [i for i, row in candidates.iterrows()
                if oil_linked(row) and row.get('action') == 'Evaluate Options']
    # First find feasible oil allocations using the unmodified allocator;
    # do not let an unqualified top-scored oil name consume the sole slot.
    baseline = base(candidates.copy(deep=True), positions.copy(deep=True), account_nav, **kwargs)
    feasible = [i for i in oil_rows if baseline.candidates.at[i, 'allocation_decision'] == 'Allocate']
    allowed = set(held)
    if not held and feasible:
        best = max(feasible, key=lambda i: float(baseline.candidates.at[i, 'portfolio_forward_score']))
        allowed.add(str(candidates.at[best, 'ticker']).upper())
    blocked = [i for i in oil_rows if str(candidates.at[i, 'ticker']).upper() not in allowed]
    candidate_input.loc[blocked, 'action'] = 'Watch'
    result = base(candidate_input, positions.copy(deep=True), account_nav, **kwargs) if blocked else baseline
    fingerprint = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for frame in (result.candidates, result.positions):
        frame['ProductionRiskPolicyVersion'] = VERSION
        frame['ProductionRiskPolicySHA256'] = fingerprint
        frame['ProductionRiskPolicyScope'] = 'NORMAL_RECOMMENDATIONS_ONLY_FROZEN_SHADOWS_EXCLUDED'
    result.candidates['OilRiskBlocked'] = False
    result.candidates['OilRiskReason'] = ''
    for i in blocked:
        reason = 'Oil-linked concurrent ticker cap (1); existing holdings count until confirmed closed'
        result.candidates.at[i, 'action'] = candidates.at[i, 'action']
        result.candidates.at[i, 'OilRiskBlocked'] = True
        result.candidates.at[i, 'OilRiskReason'] = reason
        result.candidates.at[i, 'portfolio_action_reason'] = reason
    # Original executable research action remains intact. Frozen shadows
    # recompute allocation independently and never consume OilRiskBlocked.
    result.summary['oil_risk_policy'] = VERSION
    result.summary['oil_existing_tickers'] = sorted(held)
    result.summary['oil_limit_breached_in_actual_holdings'] = len(held) > MAX_OIL_TICKERS
    return result
