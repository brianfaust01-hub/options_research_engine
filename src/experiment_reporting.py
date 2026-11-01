"""Read-only, date-aligned views of the option comparison for human reports."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import sqlite3

ET = ZoneInfo('America/New_York')
BOOKS = ('baseline', 'moderate_delta_iv')


def instant(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Comparison timestamps must have a timezone')
    return result


def period(rows, start, end, capital):
    before = [r for r in rows if r[0] <= start]
    inside = [r for r in rows if start < r[0] <= end]
    base = before[-1][1] if before else {'nav': capital, 'fees_paid': 0, 'closed_round_trips': 0, 'open_entry_debits': 0}
    last = inside[-1][1] if inside else base
    seconds = (end-start).total_seconds()
    cursor = start
    deployed = float(base.get('open_entry_debits', 0))
    area = 0
    peak = float(base['nav'])
    drawdown = 0
    for at, item in inside:
        area += deployed * (at-cursor).total_seconds()
        deployed = float(item.get('open_entry_debits', 0))
        cursor = at
        peak = max(peak, float(item['nav']))
        drawdown = max(drawdown, 1-float(item['nav'])/peak)
    area += deployed * (end-cursor).total_seconds()
    return {'start': start.isoformat(), 'end': end.isoformat(),
            'net_pnl': last['nav']-base['nav'],
            'realized_net_change': last.get('realized_net_pnl', 0)-base.get('realized_net_pnl', 0),
            'unrealized_net_change': last.get('unrealized_net_pnl', 0)-base.get('unrealized_net_pnl', 0),
            'return_on_starting_nav': last['nav']/base['nav']-1,
            'fees': last.get('fees_paid', 0)-base.get('fees_paid', 0),
            'completed_trades': last.get('closed_round_trips', 0)-base.get('closed_round_trips', 0),
            'average_entry_premium_including_entry_fees': area/seconds if seconds else deployed,
            'sampled_drawdown': drawdown,
            'cash': last.get('cash', capital), 'ending_nav': last['nav'],
            'stale_or_missing_marks': last.get('stale_or_missing_marks', []),
            'settlement_required': last.get('settlement_required', [])}


def build_comparison(root, now=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    result = {'status': 'NOT_STARTED', 'policy': 'Moderate delta/IV entry filter; shared sizing and exits',
              'actual_broker': {'status': 'UNAVAILABLE'},
              'simulation': 'Sampled quote-touch fills; full-size assumption; fees and slippage modeled. No broker orders.'}
    try:
        from spy_option_research import research_status
        result['spy_research'] = research_status(root, now)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        result['spy_research'] = {'status': 'UNAVAILABLE', 'error_type': type(error).__name__}
    path = root/'data/processed/configuration_comparison/ledger.sqlite'
    if not path.exists():
        return result
    try:
        db = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=2)
        try:
            db.execute('BEGIN')
            row = db.execute('SELECT payload FROM state WHERE id=1').fetchone()
            if not row:
                return result
            state = json.loads(row[0])
            if state.get('mode') != 'FORWARD_SHADOW':
                return {**result, 'status': 'NON_FORWARD_DATA_NOT_COMPARABLE'}
            raw = db.execute('SELECT at,portfolio,payload FROM valuations ORDER BY id').fetchall()
            histories = {name: [(instant(at), json.loads(payload)) for at, book, payload in raw
                                 if book == name and instant(at) <= now] for name in BOOKS}
            common = set(at for at, _ in histories[BOOKS[0]]) & set(at for at, _ in histories[BOOKS[1]])
            if not common:
                return {**result, 'status': 'AWAITING_MATCHED_VALUATIONS'}
            end = max(common)
            start = instant(state['started_at'])
            local = now.astimezone(ET)
            monday = (local-timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = max(start, monday)
            result.update(status='OBSERVING', started_at=start.isoformat(), as_of=end.isoformat(),
                          version=state['version'], periods={})
            for label, boundary in [('this_week', week_start), ('since_start', start)]:
                if label == 'this_week' and end < boundary:
                    result['current_week_status'] = 'AWAITING_CURRENT_WEEK_OBSERVATIONS'
                    continue
                values = {name: period(histories[name], boundary, end, state['capital']) for name in BOOKS}
                values['challenger_minus_control'] = {
                    'net_pnl': values[BOOKS[1]]['net_pnl']-values[BOOKS[0]]['net_pnl'],
                    'return_percentage_points': 100*(values[BOOKS[1]]['return_on_starting_nav']-values[BOOKS[0]]['return_on_starting_nav'])}
                result['periods'][label] = values
            orders = {name: {o['recommendation_id'] for o in state['portfolios'][name]['orders'].values()
                              if o.get('side') == 'BUY' and instant(o['decided_at']) <= end}
                      for name in BOOKS}
            result['selection_overlap_since_start'] = {
                'shared_recommendations': sorted(orders[BOOKS[0]] & orders[BOOKS[1]]),
                'control_only': sorted(orders[BOOKS[0]]-orders[BOOKS[1]]),
                'challenger_only': sorted(orders[BOOKS[1]]-orders[BOOKS[0]])}
            result['coverage'] = {'cumulative_health': state.get('health', {}),
                                  'valid_contract_minutes': db.execute('SELECT count(*) FROM coverage WHERE slot<=?', (int(end.timestamp()//60),)).fetchone()[0],
                                  'note': 'Valid samples are not a full-coverage percentage. Missing intervals and stale marks limit fill and drawdown interpretation.'}
            differences = []
            for at, book, payload in db.execute("SELECT at,portfolio,payload FROM events WHERE kind='ALLOCATION_DECISIONS' ORDER BY id"):
                if instant(at) > end:
                    continue
                decision = json.loads(payload)
                for item in decision.get('rows', []):
                    differences.append({'at': at, 'portfolio': book,
                                        'recommendation_id': item.get('RecommendationID'),
                                        'ticker': item.get('ticker'), 'action': item.get('portfolio_action'),
                                        'contracts': item.get('contracts'),
                                        'reason': item.get('portfolio_action_reason')})
            result['allocation_decisions'] = differences
            result['attribution_limit'] = 'Selection overlap and costs/exposure describe differences; they do not isolate a causal selection-only return.'
        finally:
            db.close()
        import pandas as pd
        snapshots = root/'data/account_state_snapshots.csv'
        if snapshots.exists():
            f = pd.read_csv(snapshots)
            f = f[f.AsOfDate <= end.astimezone(ET).date().isoformat()].drop_duplicates('AsOfDate', keep='last')
            f = f[f.DataQualityStatus.ne('QUARANTINED')].sort_values('AsOfDate')
            if not f.empty:
                latest = f.iloc[-1]
                result['actual_broker'] = {'status': 'DATED_STATEMENT_CONTEXT_ONLY', 'as_of_date': latest.AsOfDate,
                                          'nav': float(latest.NetLiquidatingValue), 'cash': float(latest.CashValue),
                                          'option_value': float(latest.OptionMarketValue),
                                          'note': 'Actual fills and statement dates differ from shadow. Not an equal-capital or matched-execution benchmark.'}
        return result
    except (ValueError, KeyError, TypeError, sqlite3.Error, OSError) as error:
        return {**result, 'status': 'COMPARISON_UNAVAILABLE', 'error_type': type(error).__name__}


def spy_markdown(value):
    quote = value.get('latest_quote_health') or {}
    lines = ['### Independent SPY shadow', '',
             f"Status: **{value.get('status', 'UNAVAILABLE')}**. Selection sessions: {value.get('selection_sessions', 0)}; contracts watched: {value.get('contracts_watched', 0)}.", '',
             'Separate $15,000 simulated portfolio. Technical rules select call, put or no trade; both sides can be observed for research.']
    portfolio = value.get('portfolio')
    if portfolio:
        lines += ['', f"Own inception: {portfolio['started_at']}. Last valuation: {portfolio['as_of']}.", '',
                  '| SPY period | Net P/L | Return | Fees | Average deployed | Cash | Closed trades | Sampled drawdown |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|']
        for name in ('this_week', 'since_start'):
            p = portfolio.get(name)
            if p:
                lines.append(f"| {name.replace('_', ' ')} | ${p['net_pnl']:,.2f} | {p['return_on_starting_nav']:.2%} | ${p['fees']:,.2f} | ${p['average_entry_premium_including_entry_fees']:,.2f} | ${p['cash']:,.2f} | {p['completed_trades']} | {p['sampled_drawdown']:.2%} |")
        if portfolio.get('this_week') is None:
            lines += ['', 'SPY current week: awaiting observations; prior-week returns are not carried forward as this week\'s result.']
        p = portfolio['since_start']
        lines += ['', f"SPY since-start P/L: realized ${p['realized_net_change']:+,.2f}; open ${p['unrealized_net_change']:+,.2f}. Stale/missing marks: {p['stale_or_missing_marks']}; settlement required: {p['settlement_required']}."]
    else:
        lines += ['', 'No forward SPY portfolio observations yet. No return is inferred.']
    lines += ['', 'SPY uses its own inception and a different universe. It is not the matched delta/IV challenger; compare only aligned windows and explain different cash exposure.']
    capture = value.get('last_capture_health') or {}
    if capture.get('status') not in (None, 'CAPTURED'):
        lines += ['', '**Selection health:** '+str(capture.get('status'))+'.']
    processing = value.get('last_processing_health') or {}
    if processing.get('status') not in (None, 'UPDATED'):
        lines += ['', '**SPY execution-data health:** '+str(processing.get('status'))+'.']
    if quote:
        lines += ['', f"Latest quote session: {quote['date']}; {quote['valid_contract_minutes']} valid contract-minutes across {quote['contracts_sampled']} contracts; {quote['failed_observation_records']} failed observation records. Last valid quote: {quote['last_valid_observation']}."]
    else:
        lines += ['', 'No SPY quote samples recorded yet.']
    return lines+['']


def comparison_markdown(value, detailed=False):
    lines = ['## Forward option configuration comparison', '',
             '**Actual paper account:** broker fills, holdings and fees. **Control and challenger:** separate simulated portfolios.', '',
             'Test: '+value['policy']+'.', '', 'Status: **'+value['status']+'**.']
    if value['status'] != 'OBSERVING':
        return '\n'.join(lines+['', 'No matched forward return is available. No zero return or historical backfill is inferred.', '',
                                 *spy_markdown(value.get('spy_research', {}))])
    lines += ['', f"Common inception: {value['started_at']}. Last matched valuation: {value['as_of']}."]
    if value.get('current_week_status'):
        lines += ['', '**This week: awaiting observations.** Prior-week marks are not reported as current-week performance.']
    for label, window in value['periods'].items():
        lines += ['', '### '+label.replace('_', ' ').title(), '',
                  '| Simulated book | Net P/L | Return | Fees | Avg deployed* | Ending cash | Closed trades | Sampled drawdown |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|']
        for name in BOOKS:
            p = window[name]
            lines.append(f"| {name} | ${p['net_pnl']:,.2f} | {p['return_on_starting_nav']:.2%} | ${p['fees']:,.2f} | ${p['average_entry_premium_including_entry_fees']:,.2f} | ${p['cash']:,.2f} | {p['completed_trades']} | {p['sampled_drawdown']:.2%} |")
        for name in BOOKS:
            p = window[name]
            lines += ['', f"{name} P/L components: realized net change ${p['realized_net_change']:+,.2f}; open net P/L change ${p['unrealized_net_change']:+,.2f}."]
            if p['stale_or_missing_marks'] or p['settlement_required']:
                lines += ['', f"**{name} valuation warning:** stale/missing {p['stale_or_missing_marks']}; settlement required {p['settlement_required']}."]
        delta = window['challenger_minus_control']
        lines += ['', f"Challenger minus control: **${delta['net_pnl']:+,.2f}; {delta['return_percentage_points']:+.2f} percentage points**."]
    coverage = value['coverage']
    health = coverage['cumulative_health']
    broker = value['actual_broker']
    lines += ['', '*Average deployed is time-weighted outstanding entry premium including entry fees, from sampled ledger states; return uses each window\'s starting NAV. Drawdown is sampled, not tick-complete.', '',
              f"Quote evidence since inception: {coverage['valid_contract_minutes']} valid contract-minutes; {health.get('invalid_quotes', 0)} invalid quote records; {health.get('missing_quotes', 0)} missing quote records; {health.get('intraday_gaps', 0)} recorded trading gaps. Largest recorded gap: {health.get('max_gap_seconds', 0)} trading seconds.", '', coverage['note']]
    if broker.get('status') == 'DATED_STATEMENT_CONTEXT_ONLY':
        lines += ['', f"Actual broker statement ({broker['as_of_date']}): NAV ${broker['nav']:,.2f}; cash ${broker['cash']:,.2f}; net option value ${broker['option_value']:,.2f}.", '', broker['note']]
    else:
        lines += ['', 'Actual broker statement context unavailable.']
    lines += ['', value['simulation']]
    overlap = value['selection_overlap_since_start']
    lines += ['', f"Selection overlap since inception: {len(overlap['shared_recommendations'])} shared; {len(overlap['control_only'])} control-only; {len(overlap['challenger_only'])} challenger-only.", '', value['attribution_limit']]
    if detailed:
        lines += ['', '### Selection and allocation evidence', '', '| Decision time | Book | Ticker | Action | Contracts | Reason |', '|---|---|---|---|---:|---|']
        for r in value['allocation_decisions']:
            if r['action'] in ('OPEN', 'ADD') or r['recommendation_id'] in overlap['control_only']+overlap['challenger_only']:
                safe = lambda x: str(x or '').replace('|', '/').replace('\n', ' ')
                lines.append('| '+' | '.join(safe(r[k]) for k in ['at','portfolio','ticker','action','contracts','reason'])+' |')
    return '\n'.join(lines+['', 'Ticker-specialization research remains deferred. The independent SPY portfolio is reported separately.', '',
                             *spy_markdown(value.get('spy_research', {}))])
