"""Read-only actual-entry option exit diagnostics. No optimizer or live hooks."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
RULES = ('Original levels', 'Stop distance x0.75', 'Stop distance x1.25',
         'Target distance x0.75', 'Target distance x1.25',
         'Breakeven at half target', 'Trail after three-quarter target',
         'Score-conditioned stop distance')
EARLY_RULES=('Original levels','Stop distance x0.75','Breakeven at half target','Trail after three-quarter target')


def stamp(value):
    t = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return (t.replace(tzinfo=ET) if t.tzinfo is None else t).timestamp()


def symbol(r):
    return f"{r['ticker']}{r['expiration'].replace('-', '')[2:]}{r['option_type'][0]}{round(r['strike']*1000):08d}"


def valid_point(q):
    try:
        obs, qt = stamp(q['observed_at']), stamp(q['quote_at'])
        bid, ask = float(q['bid']), float(q['ask'])
        if (q.get('quote_status') != 'OBSERVED' or q.get('realtime') is not True
            or not 0 <= obs-qt <= 60 or not math.isfinite(bid+ask)
            or not 0 < bid <= ask):
            return None
        return (obs, qt, bid, ask)
    except (ValueError, TypeError, KeyError, OverflowError):
        return None


def extract(archive, wanted, end):
    """Read every historical bundle in range; retain exact wanted contracts only."""
    paths = defaultdict(dict); manifest = []; corrupt = []; counts = Counter()
    for day in sorted(Path(archive).iterdir()):
        if not day.is_dir() or not '2026-09-25' <= day.name <= end:
            continue
        for file in sorted(day.glob('*.gz')):
            raw = file.read_bytes()
            manifest.append({'path': str(file), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
            try:
                b = json.loads(gzip.decompress(raw))
                for q in b['observations']:
                    key = ''.join(q.get('contract_symbol', '').split())
                    if key not in wanted:
                        continue
                    counts[q.get('quote_status', 'UNKNOWN')] += 1
                    p = valid_point(q)
                    if p:
                        # A repeated broker timestamp is not another market observation.
                        previous = paths[key].get(p[1])
                        if previous is None or p[0] < previous[0]:
                            paths[key][p[1]] = p
            except (ValueError, OSError, EOFError, KeyError, TypeError):
                corrupt.append(str(file))
        print(f"Scanned {day.name}: {len(manifest)} bundles", flush=True)
    return {k: sorted(v.values()) for k, v in paths.items()}, manifest, corrupt, dict(counts)


def schedule(start, end):
    import pandas_market_calendars as calendars
    s = calendars.get_calendar('NYSE').schedule(start, end)
    return [(str(d.date()), row.market_open.timestamp(), row.market_close.timestamp())
            for d, row in s.iterrows()]


def coverage(points, entry, deadline, sessions):
    expected = set()
    for _, op, cl in sessions:
        a, b = max(entry, op), min(deadline, cl)
        if a < b:
            expected.update(range(int(a//60), int((b-1e-6)//60)+1))
    slots = {int(p[0]//60) for p in points} & expected
    run = longest = 0
    for slot in sorted(expected):
        run = 0 if slot in slots else run+1
        longest = max(longest, run)
    first = points[0][0]-entry if points else None
    last = deadline-points[-1][0] if points else None
    ratio = len(slots)/len(expected) if expected else 0
    return {'expected_minutes': len(expected), 'observed_minutes': len(slots),
            'coverage': ratio, 'longest_missing_market_minutes': longest,
            'first_delay_seconds': first, 'endpoint_delay_seconds': last,
            'qualified_sampled_path': bool(points and ratio >= .95 and longest <= 5
                                           and first <= 120 and last <= 120)}


def replay(points, entry, stop, target, rule, score=None, slippage=.01):
    """First OBSERVED event, never an assumed threshold-price stop fill."""
    distance = entry-stop; gain = target-entry; peak = entry
    if rule == 'Stop distance x0.75': stop = entry-.75*distance
    if rule == 'Stop distance x1.25': stop = entry-1.25*distance
    if rule == 'Target distance x0.75': target = entry+.75*gain
    if rule == 'Target distance x1.25': target = entry+1.25*gain
    if rule == 'Score-conditioned stop distance':
        if score is None: return None
        stop = entry-distance*(1.25 if score >= 90 else .75)
    for obs, qt, bid, ask in points:
        if bid <= stop:
            return {'price': max(0, bid-slippage), 'at': obs, 'reason': 'OBSERVED_STOP'}
        if bid >= target+slippage:
            return {'price': target, 'at': obs, 'reason': 'OBSERVED_TARGET'}
        peak = max(peak, bid)
        # Ratchet from current evidence for subsequent observations only.
        if rule == 'Breakeven at half target' and peak >= entry+.5*gain:
            stop = max(stop, entry)
        if rule == 'Trail after three-quarter target' and peak >= entry+.75*gain:
            stop = max(stop, entry+.75*(peak-entry))
    if points and points[-1][0] >= points[-1][1]:
        return {'price': max(0, points[-1][2]-slippage), 'at': points[-1][0], 'reason': 'SAMPLED_ENDPOINT'}
    return None


def summarize(rows):
    values = [r['net'] for r in rows]; gains = sum(max(v, 0) for v in values)
    losses = -sum(min(v, 0) for v in values)
    # Realized-only event series; deliberately not portfolio mark-to-market DD.
    events = defaultdict(float)
    for r in rows: events[r['at']] += r['net']
    equity = peak = dd = 0
    for at in sorted(events):
        equity += events[at]; peak = max(peak, equity); dd = max(dd, peak-equity)
    return {'n': len(values), 'net': sum(values), 'win_rate': sum(v>0 for v in values)/len(values) if values else None,
            'profit_factor': gains/losses if losses else None, 'worst_trade': min(values) if values else None,
            'realized_only_drawdown_dollars': dd}


def review(value, paths):
    groups = defaultdict(list)
    for r in value['units']:
        if r['side'] == 1 and r.get('entry_at'):
            groups[(r['entry_at'], symbol(r))].append(r)
    sessions = schedule(value['start'], (datetime.fromisoformat(value['end'])+timedelta(days=15)).date())
    cutoff = stamp(value['end']+'T16:00:00')
    records = []; results = []; diagnostics = []; overlays = []
    for (at, sym), units in sorted(groups.items()):
        r = dict(units[0]); r['entry'] = sum(u['entry'] for u in units)/len(units)
        entry = stamp(at); day = at[:10]
        later = [s for s in sessions if s[0]>day]
        deadline = later[4][2]-60 if len(later)>=5 else cutoff+1
        all_points = [p for p in paths.get(sym, []) if p[0]>=entry and p[1]>=entry and p[0]<=cutoff
                  and any(op<=p[0]<cl and op<=p[1]<cl for _,op,cl in sessions)]
        points = [p for p in all_points if p[0]<=deadline]
        closed = all(u['status']=='CLOSED' for u in units)
        actual = sum(u['net_period_contribution'] for u in units) if closed else None
        base = {'entry_at': at, 'ticker': r['ticker'], 'symbol': sym, 'direction': r['option_type'],
                'quantity': len(units), 'entry': r['entry'], 'recommendation_id': r.get('recommendation_id'),
                'link_status': r['link_status'], 'actual_net': actual, 'closed': closed,
                'actual_gross_return':sum(u['gross_full_trade'] for u in units)/sum(u['entry']*100 for u in units) if closed else None,
                'mature_five_session_endpoint': deadline<=cutoff, 'deadline': datetime.fromtimestamp(deadline, timezone.utc).isoformat()}
        cov = coverage(points, entry, deadline, sessions) if deadline<=cutoff else None
        base['coverage'] = cov; base['samples'] = len(points)
        stop, target = r.get('original_stop'), r.get('original_target')
        base['valid_original_levels'] = bool(stop and target and 0<stop<r['entry']<target
            and len({(u.get('recommendation_id'),u.get('original_stop'),u.get('original_target')) for u in units})==1)
        records.append(base)
        if closed:
            exit_at = max(stamp(u['exit_at']) for u in units)
            before = [p for p in all_points if p[0]<=exit_at and p[1]<=exit_at]
            after = [p for p in points if p[0]>exit_at and p[1]>exit_at]
            avg_exit = sum(u['exit'] for u in units)/len(units)
            holding_cov = coverage(before,entry,exit_at,sessions)
            recovered = next((i for i,p in enumerate(after) if p[2]>=r['entry']+.01),None)
            diagnostics.append({**base, 'exit_order_types': sorted({u['exit_order_type'] for u in units}),
                'actual_average_exit': avg_exit,
                'actual_holding_coverage': holding_cov,
                'observed_peak_to_actual_exit_dollars': max([0]+[(p[2]-avg_exit)*100*len(units) for p in before]),
                'pre_exit_max_bid_return': max((p[2]/r['entry']-1 for p in before), default=None),
                'pre_exit_min_bid_return': min((p[2]/r['entry']-1 for p in before), default=None),
                'post_exit_samples': len(after),
                'observed_recovery_to_entry': any(p[2]>=r['entry']+.01 for p in after),
                'lowest_return_before_observed_entry_recovery':min(p[2]/r['entry']-1 for p in after[:recovered+1]) if recovered is not None else None,
                'observed_recovery_to_original_target': bool(target and any(p[2]>=target+.01 for p in after)),
                'post_exit_min_bid_return': min((p[2]/r['entry']-1 for p in after), default=None)})
            # Earlier-sale overlays have a shorter, observable question: replace
            # the actual sale only if a candidate triggers sooner. They cannot
            # test later holding, wider stops, or a higher profit target.
            if (holding_cov['qualified_sampled_path'] and base['valid_original_levels']
                and len({u['exit_at'] for u in units})==1):
                for rule in EARLY_RULES:
                    for slip in (.01,.05):
                        fill = replay(before,r['entry'],stop,target,rule,r.get('research_score'),slip)
                        changed = bool(fill and fill['reason']!='SAMPLED_ENDPOINT' and fill['at']<exit_at)
                        net = ((fill['price']-r['entry'])*100*len(units)-sum(u['entry_fee'] for u in units)-.70*len(units)) if changed else actual
                        overlays.append({'rule':rule,'slippage':slip,'entry_at':at,'exit_at':datetime.fromtimestamp(exit_at,ET).isoformat(),
                            'ticker':r['ticker'],'symbol':sym,'actual_net':actual,'net':net,'difference':net-actual,
                            'changed':changed,'actual_winner':actual>0,'quantity':len(units),'at':fill['at'] if changed else exit_at})
        # Common endpoint required for every rule, even if one rule exits early.
        if deadline>cutoff or not base['valid_original_levels'] or not points or deadline-points[-1][0]>120:
            continue
        for slip in (.01, .05):
            for rule in RULES:
                fill = replay(points, r['entry'], stop, target, rule, r.get('research_score'), slip)
                if fill:
                    results.append({'entry_at': at, 'symbol': sym, 'rule': rule, 'slippage': slip,
                        'qualified': cov['qualified_sampled_path'], 'direction': r['option_type'],
                        'net': (fill['price']-r['entry'])*100*len(units)-sum(u['entry_fee'] for u in units)-.70*len(units),
                        'at': fill['at'], 'reason': fill['reason']})
    tables = []
    for quality in ('qualified', 'sparse_diagnostic'):
        for period in ('train', 'holdout'):
            for slip in (.01, .05):
                for rule in RULES:
                    rows = [r for r in results if r['rule']==rule and r['slippage']==slip
                        and (r['qualified'] if quality=='qualified' else True)
                        and ((r['entry_at'][:10]<='2026-10-21') if period=='train' else (r['entry_at'][:10]>'2026-10-21'))
                        # Purge training paths whose endpoint is after the cutoff.
                        and (period!='train' or next(x for x in records if x['entry_at']==r['entry_at'] and x['symbol']==r['symbol'])['deadline'][:10]<='2026-10-21')]
                    baseline = {(r['entry_at'],r['symbol']):r for r in results
                                if r['rule']=='Original levels' and r['slippage']==slip}
                    pairs = [(r, baseline[(r['entry_at'],r['symbol'])]) for r in rows]
                    deltas = [r['net']-b['net'] for r,b in pairs]
                    saved = sum(max(r['net']-b['net'],0) for r,b in pairs)
                    sacrificed = sum(max(b['net']-r['net'],0) for r,b in pairs)
                    winning = sum(max(b['net'],0) for _,b in pairs)
                    protected = sum(min(max(r['net'],0),max(b['net'],0)) for r,b in pairs)
                    tables.append({'quality': quality, 'period': period, 'slippage': slip, 'rule': rule,
                        **summarize(rows), 'paired_baseline_net':sum(b['net'] for _,b in pairs),
                        'benefit_vs_same_path_baseline':sum(deltas), 'improved_trade_dollars':saved,
                        'sacrificed_trade_dollars':sacrificed,
                        'baseline_winning_dollars_preserved':protected/winning if winning else None,
                        'benefit_without_best_improvement':sum(deltas)-max([0]+deltas)})
    stops = [d for d in diagnostics if any('STP' in x.upper() or 'STOP' in x.upper() for x in d['exit_order_types'])]
    loss_stops = [d for d in stops if d['actual_net']<0]
    observed = [d for d in loss_stops if d['post_exit_samples']]
    overlay_tables=[]
    for period in ('train','holdout'):
        for rule in EARLY_RULES:
            for slip in (.01,.05):
                sample=[r for r in overlays if r['rule']==rule and r['slippage']==slip
                        and ((r['entry_at'][:10]<='2026-10-21' and r['exit_at'][:10]<='2026-10-21') if period=='train' else r['entry_at'][:10]>'2026-10-21')]
                delta=sum(r['difference'] for r in sample)
                controls={(r['entry_at'],r['symbol']):r for r in overlays if r['rule']=='Original levels' and r['slippage']==slip}
                overlay_tables.append({'period':period,'rule':rule,'slippage':slip,**summarize(sample),
                    'actual_baseline_net':sum(r['actual_net'] for r in sample),'difference':delta,
                    'difference_vs_original_level_overlay':sum(r['net']-controls[(r['entry_at'],r['symbol'])]['net'] for r in sample),
                    'benefit_without_best_improvement':delta-max([0]+[r['difference'] for r in sample]),
                    'one_contract_difference':sum(r['difference']/r['quantity'] for r in sample),
                    'improved_dollars':sum(max(r['difference'],0) for r in sample),
                    'sacrificed_dollars':-sum(min(r['difference'],0) for r in sample),
                    'actual_winner_dollars_sacrificed':sum(max(r['actual_net']-r['net'],0) for r in sample if r['actual_winner'])})
    return {'status': 'EXPLORATORY_SAMPLED_EVIDENCE_NOT_DEPLOYABLE', 'through': value['end'],
        'entry_groups': len(records), 'mature_groups': sum(r['mature_five_session_endpoint'] for r in records),
        'qualified_groups': sum(bool(r['coverage'] and r['coverage']['qualified_sampled_path']) for r in records),
        'stopped_groups': len(stops), 'stopped_loss_groups':len(loss_stops),
        'median_actual_stop_group_gross_return':median(r['actual_gross_return'] for r in stops) if stops else None,
        'actual_stop_groups_worse_than_20pct':sum(r['actual_gross_return']<-.20001 for r in stops),
        'stopped_with_post_exit_quotes': len(observed),
        'stopped_observed_recovery_to_entry': sum(r['observed_recovery_to_entry'] for r in observed),
        'stopped_observed_recovery_to_target': sum(r['observed_recovery_to_original_target'] for r in observed),
        'stopped_observed_further_decline': sum(r['post_exit_min_bid_return'] is not None and
             r['entry']*(1+r['post_exit_min_bid_return'])<r['actual_average_exit'] for r in observed),
        'recoveries_observed_below_minus20_before_entry':sum(r['lowest_return_before_observed_entry_recovery'] is not None and r['lowest_return_before_observed_entry_recovery']<-.20 for r in observed),
        'actual_holding_qualified_groups':sum(r['actual_holding_coverage']['qualified_sampled_path'] for r in diagnostics),
        'median_mature_coverage': median([r['coverage']['coverage'] for r in records if r['coverage']]) if any(r['coverage'] for r in records) else None,
        'tables': tables, 'groups': records, 'actual_exit_diagnostics': diagnostics, 'replays': results,
        'early_sale_overlays':overlays,'early_sale_summary':overlay_tables,
        'selection': 'No rule promoted; sparse paths cannot select or validate an exit policy.',
        'limits': ['Broker timestamps assumed Eastern; recommendation links inferred from contract/time.',
            'Five subsequent NYSE sessions after entry, endpoint one minute before close; not original adaptive time exits or the funded shadow lifecycle.',
            'Original levels replay is a static OCO reference, not the full production daily profit ratchet, portfolio decisions or actual broker outcome.',
            'Early-sale overlays use coverage-qualified entry-to-actual-sale paths only, with simultaneous full-quantity actual exits. If a candidate triggers earlier, replace that sale; otherwise preserve the actual outcome. These cannot test waiting longer, exclude mixed partial exits, and remain retrospective sampled diagnostics.',
            'First observed events only; between-sample crossings, intraminute order, overnight fills and execution latency unknown. Missing quotes never interpolated.',
            'Zero bids, stale/future/delayed/crossed quotes excluded; positive bid does not prove executable size.',
            'Entry actual price/quantity/fee; simulated exit fee $0.70/contract; stops and endpoints bid minus $0.01/$0.05 sensitivity. Target requires bid >= target plus slippage.',
            'Coverage qualification is >=95% expected market minutes, <=5 missing consecutive market minutes, entry/endpoint within 120 seconds; still sampled, not tick complete.',
            'Sparse replay cannot prove premature stop rates or optimal exits; observed post-stop recovery is a lower-bound occurrence, not its probability or profitability.',
            'No replacement trades, reinvestment or funded portfolio replay. Realized-only drawdown excludes open marks and is not portfolio drawdown.',
            'Research score is not calibrated confidence; score-conditioned rule is a hypothesis. No confidence algorithm fitted.',
            'Closed and still-open entries included for replay if fixed horizon mature; no selection by winner status. Rules fixed before results, exploratory multiple comparisons.']}


def markdown(v):
    lines = ['# Option stop and target review', '', '**Research only; no live or frozen-shadow rules changed.**', '',
        f"Through {v['through']}: {v['entry_groups']} actual long-entry groups; {v['mature_groups']} matured five-session windows; {v['qualified_groups']} coverage-qualified sampled paths.",
        f"Median matured contract-minute coverage: {v['median_mature_coverage']:.1%}.",
        f"Broker stop groups: {v['stopped_groups']}, including {v['stopped_loss_groups']} net losers; later quotes present for {v['stopped_with_post_exit_quotes']} of those losers. Among observed losing stop groups, bids recovered to entry in {v['stopped_observed_recovery_to_entry']} and original target in {v['stopped_observed_recovery_to_target']}. These are observed occurrences, not recovery probabilities.", '',
        f"Actual holding periods with coverage-qualified sampled paths: {v['actual_holding_qualified_groups']}.",
        f"Stopped groups with observed further decline after the sale: {v['stopped_observed_further_decline']}; recovery and further decline can both occur on one path.",
        '', v['selection'], '', '| Coverage | Period | Rule | N | Net $ | Difference vs paired original $ | Baseline winning dollars preserved | Win rate | Worst trade $ | Realized-only drawdown $ |', '|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in v['tables']:
        if r['slippage']!=.01: continue
        wr = f"{r['win_rate']:.1%}" if r['win_rate'] is not None else 'N/A'
        worst = f"{r['worst_trade']:.2f}" if r['worst_trade'] is not None else 'N/A'
        retained = f"{r['baseline_winning_dollars_preserved']:.1%}" if r['baseline_winning_dollars_preserved'] is not None else 'N/A'
        lines.append(f"| {r['quality']} | {r['period']} | {r['rule']} | {r['n']} | {r['net']:.2f} | {r['benefit_vs_same_path_baseline']:+.2f} | {retained} | {wr} | {worst} | {r['realized_only_drawdown_dollars']:.2f} |")
    lines+=['','## Earlier-sale overlays on actual holding periods','',
        'Only coverage-qualified shorter paths with simultaneous actual exits qualify. An earlier observed trigger replaces the actual sale; otherwise the actual sale is retained. These results cannot test waiting longer. The original-level overlay controls for replacing actual execution with static OCO observations.',
        '', '| Period | Rule | N | Actual net $ | Overlay net $ | Difference vs actual $ | Difference vs original-level overlay $ | Actual winner dollars sacrificed |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in v['early_sale_summary']:
        if r['slippage']==.01:
            lines.append(f"| {r['period']} | {r['rule']} | {r['n']} | {r['actual_baseline_net']:.2f} | {r['net']:.2f} | {r['difference']:+.2f} | {r['difference_vs_original_level_overlay']:+.2f} | {r['actual_winner_dollars_sacrificed']:.2f} |")
    return '\n'.join(lines+['', '## Method and limits', '', *['- '+x for x in v['limits']]])


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--attribution', type=Path, required=True)
    sources = p.add_mutually_exclusive_group(required=True)
    sources.add_argument('--archive', type=Path)
    sources.add_argument('--projection', type=Path, help='Reuse an exclusively saved extraction from this review, preserving its manifest')
    p.add_argument('--output', type=Path, required=True); args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw = args.attribution.read_bytes(); v = json.loads(raw)
    wanted = {symbol(r) for r in v['units'] if r['side']==1 and r.get('entry_at')}
    if args.projection:
        paths = json.loads(args.projection.read_bytes())
        old = json.loads((args.projection.parent/'review.json').read_bytes())
        if old['attribution_sha256'] != hashlib.sha256(raw).hexdigest():
            raise ValueError('Projection attribution mismatch')
        manifest = json.loads((args.projection.parent/'source_manifest.json').read_bytes())
        corrupt, counts = old['corrupt_bundles'], old['quote_status_counts']
    else:
        paths, manifest, corrupt, counts = extract(args.archive, wanted, v['end'])
    (args.output/'source_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (args.output/'quote_projection.json').write_text(json.dumps(paths), encoding='utf-8')
    result = review(v, paths)
    result.update(attribution_sha256=hashlib.sha256(raw).hexdigest(), archive_bundles=len(manifest), corrupt_bundles=corrupt, quote_status_counts=counts)
    result['analysis_source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['quote_projection_sha256'] = hashlib.sha256((args.output/'quote_projection.json').read_bytes()).hexdigest()
    (args.output/'review.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (args.output/'review.md').write_text(markdown(result), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('tables','groups','actual_exit_diagnostics','replays','limits','quote_status_counts','early_sale_overlays','early_sale_summary')}, indent=2))
