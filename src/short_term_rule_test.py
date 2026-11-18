"""Read-only, actual-entry comparison of intraday profit protection rules."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from broker_performance_attribution import build
from exit_path_review import coverage, schedule, stamp, symbol, valid_point

THRESHOLDS = (.25, .35, .50, .65, .75, .90)
EXECUTION = ((0, .01, None), (60, .01, None), (60, .05, None),
             (60, .01, 1), (60, .05, 1))
EXIT_FEE = .70


def order_history(directory, first, last):
    brackets = defaultdict(lambda: defaultdict(set))
    filled_buys = defaultdict(set)
    other_exits = defaultdict(set)
    changes = defaultdict(lambda: defaultdict(set))
    for path in sorted(directory.glob('*AccountStatement*.csv')):
        if not first <= path.name[:10] <= last:
            continue
        with path.open(encoding='utf-8-sig', newline='') as handle:
            rows = list(csv.reader(handle))
        section = next((i for i, r in enumerate(rows) if r and r[0]=='Account Order History'), None)
        if section is None:
            continue
        current = None
        children = []

        def save(row, details):
            if row is None:
                return
            key, placed, qty, side, effect, state, kind, price = row
            if side == 'BUY' and effect == 'TO OPEN' and state == 'FILLED':
                filled_buys[key].add((placed, qty))
            if side != 'SELL' or effect != 'TO CLOSE':
                return
            parent = next((d[3] for d in details if d[3].startswith('TRG BY #')), None)
            linked = any(d[3].startswith('OCO #') for d in details)
            replacement = any(d[3].startswith('RE #') for d in details)
            if parent and replacement and state in {'WORKING','FILLED','CANCELED'}:
                for detail in details:
                    if not detail[3].startswith('RE #') or detail[13] not in {'STP','LMT'}:
                        continue
                    try: price = float(detail[12])
                    except ValueError: continue
                    if math.isfinite(price) and price > 0:
                        changes[(key,parent)][(placed,qty,detail[13])].add(price)
                other_exits[key].add((placed,parent))
            elif parent and linked and state in {'WORKING','FILLED','CANCELED'}:
                for detail in details:
                    try: price = float(detail[12])
                    except ValueError: continue
                    if detail[13] in {'STP','LMT'} and math.isfinite(price) and price > 0:
                        brackets[(key, placed, qty, parent)][detail[13]].add(price)
            elif state in {'WORKING','FILLED','CANCELED'}:
                other_exits[key].add((placed,None))

        for r in rows[section+2:]:
            if not r or r[0]=='Account Trade History':
                break
            if len(r) < 16:
                continue
            if not r[2]:
                if current:
                    children.append(r)
                continue
            save(current, children)
            current, children = None, []
            try:
                placed = stamp(datetime.strptime(r[2],'%m/%d/%y %H:%M:%S').isoformat())
                exp = datetime.strptime(r[9],'%d %b %y').date().isoformat()
                key = symbol({'ticker':r[8], 'expiration':exp, 'strike':float(r[10]), 'option_type':r[11]})
                current = (key, placed, abs(int(r[5])), r[4], r[7], r[15], r[13], r[12])
            except (ValueError, IndexError):
                continue
        save(current, children)
    candidates = defaultdict(list)
    for (key, placed, qty, parent), legs in brackets.items():
        if (placed, qty) in filled_buys[key] and len(legs['STP']) == len(legs['LMT']) == 1:
            candidates[key].append((placed, qty, next(iter(legs['STP'])), next(iter(legs['LMT'])),parent))
    return candidates, other_exits, changes


def select_bracket(key, entry_at, fill, quantity, candidates, fallback_stop, fallback_target):
    matching = [c for c in candidates if c[1] >= quantity and 0 <= entry_at-c[0] <= 1800
                and 0 < c[2] < fill < c[3]]
    if matching:
        latest = max(c[0] for c in matching)
        prices = {(c[2],c[3],c[4]) for c in matching if c[0]==latest}
        if len(prices)==1:
            stop,target,parent = next(iter(prices))
            return stop,target,'BROKER_INITIAL_BRACKET_INFERRED',parent
    if fallback_stop and fallback_target and 0 < fallback_stop < fill < fallback_target:
        return fallback_stop, fallback_target, 'RECOMMENDATION_FALLBACK',None
    return None, None, 'UNKNOWN',None


def replay(points, entry, qty, original_stop, target, fraction=None, action='keep',
           delay=0, slippage=.01, max_per_quote=None, amendments=()):
    remaining, stop = qty, original_stop
    trigger_at = ready_at = None
    pending_market_exit = False
    market_exit_due_to_rule = False
    working_stop = original_stop
    raised = False
    fills = []
    rule_fills = []
    trigger_price = entry+fraction*(target-entry) if fraction is not None else None
    amendment_index = 0
    protection_floor = 0.
    for index, (observed, quoted, bid, ask) in enumerate(points):
        while amendment_index<len(amendments) and amendments[amendment_index][0]<=quoted:
            _, size, kind, price = amendments[amendment_index]
            amendment_index += 1
            if size == remaining:
                if kind == 'STP':
                    working_stop = price
                    stop = max(price,protection_floor)
                else:
                    target = price
        if bid <= stop and not pending_market_exit:
            pending_market_exit = True
            market_exit_due_to_rule = bid > working_stop
        if pending_market_exit:
            price, reason = max(0., bid-slippage), 'stop_or_early_close'
        elif bid >= target + slippage:
            price, reason = target, 'target'
        else:
            if trigger_price is not None and trigger_at is None and bid >= trigger_price:
                trigger_at = observed
                ready_at = observed + delay
            if ready_at is None or observed < ready_at or (delay and quoted < ready_at):
                continue
            if action == 'raise' and not raised:
                # Protect half the gain at activation. Leave room for two
                # spreads or the recent sampled bid range, whichever is larger.
                recent = [p[2] for p in points[max(0,index-5):index+1]]
                buffer = max(2*(ask-bid), max(recent)-min(recent), .01)
                candidate = math.floor(100*min(entry+.5*(bid-entry),bid-buffer))/100
                if candidate>stop:
                    stop = protection_floor = candidate
                    raised = True
                ready_at = None
                continue
            if action != 'close':
                continue
            pending_market_exit = True
            market_exit_due_to_rule = True
            price, reason = max(0., bid-slippage), 'stop_or_early_close'
        size = min(remaining,max_per_quote) if max_per_quote else remaining
        fills.append((observed,price,size,reason))
        if pending_market_exit and market_exit_due_to_rule:
            rule_fills.append((observed,price,size))
        remaining -= size
        if remaining == 0:
            break
    if remaining:
        observed, _, bid, _ = points[-1]
        # A common terminal bid mark for unresolved contracts, with an exit
        # cost allowance. This is a valuation, not an assumed size fill.
        fills.append((observed,max(0.,bid-slippage),remaining,'terminal_mark'))
    net = sum((price-entry)*100*size-EXIT_FEE*size for _,price,size,_ in fills)
    return {'net_before_entry_fee':net,'fills':fills,'rule_fills':rule_fills,'triggered':trigger_at is not None,
            'raised':raised,'giveback':sum(max(0.,max(entry,max((p[2] for p in points if p[0]<=at),default=entry))-price)*100*size
                                            for at,price,size,_ in fills)}


def actual_exit_overlay(result, units, first_reduction):
    """Replace only explicitly rule-driven sells while the actual lot is intact."""
    delta = 0.
    index = 0
    for at,price,size in result['rule_fills']:
        if at >= first_reduction:
            break
        for unit in units[index:index+size]:
            actual_price = unit['exit'] if unit['status']=='CLOSED' else unit['mark']
            actual_exit_fee = unit['fees']-unit['entry_fee']
            delta += (price-actual_price)*100 - EXIT_FEE + actual_exit_fee
        index += size
    return delta,index


def load_quotes(archive, prior_dir, wanted, dates):
    raw = (prior_dir/'quote_projection.json').read_bytes()
    metadata = json.loads((prior_dir/'review.json').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=metadata['quote_projection_sha256']:
        raise ValueError('Historical quote projection failed checksum verification')
    quotes = {key:{p[1]:tuple(p) for p in rows} for key,rows in json.loads(raw).items() if key in wanted}
    manifest, corrupt = [], []
    for day in dates:
        if day <= metadata['through']:
            continue
        for path in sorted((archive/day).glob('*.gz')):
            payload = path.read_bytes()
            manifest.append((str(path),hashlib.sha256(payload).hexdigest()))
            try: rows = json.loads(gzip.decompress(payload))['observations']
            except (ValueError,OSError,EOFError,KeyError):
                corrupt.append(str(path))
                continue
            for row in rows:
                key = ''.join(row['contract_symbol'].split())
                if key not in wanted:
                    continue
                point = valid_point(row)
                if point:
                    bucket = quotes.setdefault(key,{})
                    if point[1] not in bucket or point[0] < bucket[point[1]][0]:
                        bucket[point[1]] = point
        print(f'Loaded {day} quotes',flush=True)
    return {key:sorted(points.values()) for key,points in quotes.items()}, manifest, corrupt


def run(args):
    actual = build(args.statements,args.journal,args.beginning,args.ending)
    if actual['bridge']['status'] != 'RECONCILED':
        raise ValueError('Actual account NAV does not reconcile')
    sessions = schedule(actual['start'],actual['end'])
    start_at = sessions[0][2]
    origins = defaultdict(list)
    if args.origin_statement:
        opening = build(args.statements,args.journal,args.origin_statement,args.beginning)
        if opening['bridge']['status'] != 'RECONCILED':
            raise ValueError('Starting holdings origin statement does not reconcile')
        for unit in opening['units']:
            if unit['status']=='OPEN':
                origins[symbol(unit)].append(unit)
    groups = defaultdict(list)
    passthrough = defaultdict(float)
    for unit in actual['units']:
        if unit['side']==1 and not unit['entry_at'] and origins.get(symbol(unit)):
            index = int(unit['unit_id'].rsplit('-',1)[1])
            origin = origins[symbol(unit)][index]
            if origin['side']==1 and origin.get('entry_at'):
                unit = {**origin,**unit,'entry_at':origin['entry_at'], 'entry':origin['entry'],
                        'original_stop':origin.get('original_stop'), 'original_target':origin.get('original_target')}
        if unit['side']==1 and unit['entry_at']:
            groups[(symbol(unit),unit['entry_at'])].append(unit)
        else:
            passthrough[unit['economic_origin']] += unit['net_period_contribution']
    first_export = args.origin_statement[:10] if args.origin_statement else actual['start']
    brackets, other_exits, changes = order_history(args.statements,first_export,actual['end'])
    quotes, manifest, corrupt = load_quotes(args.archive,args.projection,{key for key,_ in groups},[d for d,_,_ in sessions])
    trades = []
    for (key, entered), units in sorted(groups.items()):
        t = stamp(entered)
        qty = len(units)
        entry = sum(u['entry'] for u in units)/qty
        actual_net = sum(u['net_period_contribution'] for u in units)
        first = units[0]
        stop,target,source,parent = select_bracket(key,t,entry,qty,brackets[key],first.get('original_stop'),first.get('original_target'))
        inherited = first['economic_origin']=='INHERITED_AT_BASELINE'
        start = max(t, next((op for _,op,cl in sessions if cl>start_at),start_at)) if inherited else t
        remaining_sessions = [cl for day,_,cl in sessions if cl>start and day<=first['expiration']]
        if not remaining_sessions:
            passthrough['NO_SESSION'] += actual_net
            continue
        # Three sessions including the entry session, truncated at the common statement cutoff.
        deadline = remaining_sessions[min(2,len(remaining_sessions)-1)]
        points = [p for p in quotes.get(key,()) if start<=p[1]<=p[0]<deadline
                  and any(op<=p[1]<=p[0]<cl for _,op,cl in sessions)]
        quality = coverage(points,start,deadline,sessions)
        # Require a contemporaneous endpoint so every rule values the same window.
        if stop is None or not points or quality['endpoint_delay_seconds']>300:
            passthrough['UNREPLAYABLE_NEW_LONG'] += actual_net
            continue
        fee = sum(u['entry_fee'] for u in units)
        basis_adjustment = sum((u['entry']-u['period_basis'])*100 for u in units)
        actual_first_exit = min((stamp(u['exit_at']) for u in units if u.get('exit_at')),default=sessions[-1][2])
        amendments = sorted((*k,next(iter(values))) for k,values in changes[(key,parent)].items()
                            if t<k[0]<min(deadline,actual_first_exit) and len(values)==1)
        resolved_times = {a[0] for a in amendments}
        trade = {'symbol':key,'entry':entered,'qty':qty,'actual_net':actual_net,'entry_fee':fee,
                 'basis_adjustment':basis_adjustment,'inherited':inherited,'amendments':amendments,
                 'stop':stop,'target':target,'bracket_source':source,'coverage':quality,
                 'possible_order_change':any(t<a<min(deadline,actual_first_exit) and (p!=parent or a not in resolved_times)
                                             for a,p in other_exits[key]),
                 'observed_after_actual_exit':any(p[0]>actual_first_exit for p in points),'outcomes':{}}
        for delay, slip, cap in EXECUTION:
            model = f'{delay}s_{slip:.2f}_{cap or "full"}'
            baseline = replay(points,entry,qty,stop,target,slippage=slip,max_per_quote=cap,amendments=amendments)
            variants = {}
            for fraction in THRESHOLDS:
                for action in ('raise','close'):
                    variant = replay(points,entry,qty,stop,target,fraction,action,delay,slip,cap,amendments)
                    anchored_delta, anchored_size = actual_exit_overlay(variant,units,actual_first_exit)
                    variants[f'{action}_{fraction:.2f}'] = {**variant,'actual_exit_delta':anchored_delta,
                                                            'actual_contracts_replaced':anchored_size}
            trade['outcomes'][model] = {'control':baseline,'variants':variants}
        trades.append(trade)

    tiers = {'broad':lambda t: t['coverage']['coverage']>=.80 and t['coverage']['longest_missing_market_minutes']<=30 and t['coverage']['first_delay_seconds']<=300,
             'strict':lambda t: t['coverage']['qualified_sampled_path'],
             'broker_brackets':lambda t: t['bracket_source']=='BROKER_INITIAL_BRACKET_INFERRED' and not t['possible_order_change']
                 and t['coverage']['coverage']>=.80 and t['coverage']['longest_missing_market_minutes']<=30 and t['coverage']['first_delay_seconds']<=300}
    tables = []
    for tier, eligible in tiers.items():
        cohort = list(filter(eligible,trades))
        for model in (trades[0]['outcomes'] if trades else []):
            reference = sum(t['outcomes'][model]['control']['net_before_entry_fee']-t['entry_fee']+t['basis_adjustment'] for t in cohort)
            actual_net = sum(t['actual_net'] for t in cohort)
            for rule in trades[0]['outcomes'][model]['variants']:
                pairs = [(t['outcomes'][model]['control'],t['outcomes'][model]['variants'][rule]) for t in cohort]
                delta = [v['net_before_entry_fee']-b['net_before_entry_fee'] for b,v in pairs]
                by_date = defaultdict(float)
                for trade, difference in zip(cohort,delta):
                    by_date[max(trade['entry'][:10],actual['start'])] += difference
                gain = sum(max(d,0) for d in delta)
                loss = -sum(min(d,0) for d in delta)
                anchored = [v['actual_exit_delta'] for _,v in pairs]
                anchored_dates = defaultdict(float)
                for trade,difference in zip(cohort,anchored):
                    anchored_dates[max(trade['entry'][:10],actual['start'])] += difference
                tables.append({'coverage':tier,'execution':model,'rule':rule,'groups':len(cohort),
                               'entry_dates':len({t['entry'][:10] for t in cohort}),
                               'actual_net':actual_net,'control_net':reference,'variant_net':reference+sum(delta),
                               'account_control_with_actual_passthrough':actual['bridge']['nav_change']-actual_net+reference,
                               'account_variant_with_actual_passthrough':actual['bridge']['nav_change']-actual_net+reference+sum(delta),
                               'delta_net':sum(delta),'improved_dollars':gain,'sacrificed_dollars':loss,
                               'giveback_reduction':sum(b['giveback']-v['giveback'] for b,v in pairs),
                               'actual_exit_overlay_delta':sum(anchored),
                               'actual_exit_overlay_improved_dollars':sum(max(d,0) for d in anchored),
                               'actual_exit_overlay_sacrificed_dollars':-sum(min(d,0) for d in anchored),
                               'actual_exit_overlay_changed_groups':sum(v['actual_contracts_replaced']>0 for _,v in pairs),
                               'actual_exit_overlay_without_best_date':sum(anchored)-max([0]+list(anchored_dates.values())),
                               'activations':sum(v['triggered'] for _,v in pairs),
                               'without_best_group':sum(delta)-max([0]+delta),
                               'without_best_entry_date':sum(delta)-max([0]+list(by_date.values()))})
    if abs(sum(t['actual_net'] for t in trades)+sum(passthrough.values())-sum(u['net_period_contribution'] for u in actual['units']))>.01:
        raise ValueError('Actual entry cohorts failed accounting reconciliation')
    return {'window':[actual['start'],actual['end']],'actual_bridge':actual['bridge'],
            'actual_only_contributions':dict(passthrough),'replayable_groups':len(trades),
            'broker_bracket_groups':sum(t['bracket_source']=='BROKER_INITIAL_BRACKET_INFERRED' for t in trades),
            'starting_inventory_replayed_groups':sum(t['inherited'] for t in trades),
            'amendment_groups':sum(bool(t['amendments']) for t in trades),
            'possible_order_change_groups':sum(t['possible_order_change'] for t in trades),
            'observed_past_actual_exit_groups':sum(t['observed_after_actual_exit'] for t in trades),
            'tables':tables,'trades':trades,'new_quote_manifest':manifest,'corrupt_new_bundles':corrupt,
            'statement_manifest':actual['source_manifest'],'journal_sha256':actual['journal_sha256']}


def markdown(result):
    start,end = result['window']
    rows = result['tables']
    featured = [r for r in rows if r['coverage']=='broad' and r['execution']=='60s_0.01_full']
    lines = ['# Short-Term Rule Test','', f'Broker statements from the {start} close through the {end} close.', '',
             f"Actual account net P/L was ${result['actual_bridge']['nav_change']:+,.2f} after fees. The broker NAV bridge reconciled to the cent.",
             f"The replay used {result['replayable_groups']} groups with an initial bracket and an endpoint quote, including {result['starting_inventory_replayed_groups']} carried groups. "
             f"It recovered initial brackets for {result['broker_bracket_groups']} groups and linked amendments for {result['amendment_groups']}. "
             f"{result['possible_order_change_groups']} groups had other order placements that could not be incorporated with confidence.", '']
    if featured:
        first = featured[0]
        lines += [f"The main comparison uses {first['groups']} groups on {first['entry_dates']} entry dates, a 60-second delay on the new action, and $0.01 slippage per option share. "
                  f"Their actual net was ${first['actual_net']:+,.2f} and modeled original-order net was ${first['control_net']:+,.2f}. "
                  'The difference limits how closely the modeled control represents actual trading.', '',
                  '| Rule | Activations | Net vs modeled control | Peak giveback reduced | Dollars improved / sacrificed vs modeled control | Net vs actual exits | Dollars improved / sacrificed vs actual exits |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for row in featured:
            kind,fraction = row['rule'].split('_')
            label = ('Raise stop' if kind=='raise' else 'Close early') + f' at {float(fraction):.0%}'
            lines.append(f"| {label} | {row['activations']} | ${row['delta_net']:+,.2f} | ${row['giveback_reduction']:+,.2f} | "
                         f"${row['improved_dollars']:,.2f} / ${row['sacrificed_dollars']:,.2f} | "
                         f"${row['actual_exit_overlay_delta']:+,.2f} | ${row['actual_exit_overlay_improved_dollars']:,.2f} / "
                         f"${row['actual_exit_overlay_sacrificed_dollars']:,.2f} |")
    lines += ['', '## Execution and coverage sensitivity','',
              'All rules within a row group use the same starting contracts and entries, including positions that never trigger. Each dollar amount below is a difference from the corresponding benchmark.', '',
              '| Cohort | Execution assumption | Groups | Close 25% vs control / actual | Close 50% vs control / actual | Close 90% vs control / actual |',
              '|---|---|---:|---:|---:|---:|']
    for tier in ('broad','strict','broker_brackets'):
        for delay,slip,cap in EXECUTION:
            model = f'{delay}s_{slip:.2f}_{cap or "full"}'
            subset = {r['rule']:r for r in rows if r['coverage']==tier and r['execution']==model}
            if not subset:
                continue
            values = [subset[f'close_{x:.2f}'] for x in (.25,.50,.90)]
            desc = f'{delay}s, ${slip:.2f}, ' + ('one contract per quote' if cap else 'full size')
            lines.append(f"| {tier} | {desc} | {values[0]['groups']} | " + ' | '.join(
                f"${r['delta_net']:+,.0f} / ${r['actual_exit_overlay_delta']:+,.0f}" for r in values) + ' |')
    lines += ['', '## Replay assumptions','',
              '- The original control uses the recovered bracket and explicit replacements linked to its parent. Missing initial brackets use recorded recommendation levels where available. The association to a fill is inferred from contract, time and size. The export can leave the effective time of cancels and other changes unclear.',
              '- Thresholds use the distance from actual fill to the initial target. A raised stop seeks to protect half the bid gain when the change takes effect, with room for two spreads or the recent six-sample bid range, whichever is larger. Later broker stop amendments respect the protected floor.',
              '- The modeled replay values contracts still open at the end of three trading sessions including entry, or at the statement cutoff if sooner. An ending bid within five minutes is required. Unresolved quantities use a terminal bid mark less modeled liquidation costs. After the actual position exits, its original simulated orders can still be active.',
              '- The actual-exit overlay replaces only sales caused by the candidate before the first actual reduction. It preserves later actual outcomes for all other units and can miss opportunities after the modeled control would already have exited. This is a sensitivity check on earlier intervention.',
              '- Stops use sampled bids. Targets require bid headroom equal to the slippage assumption. Quotes are sparse and lack reliable size. One-contract execution limits are modeled per entry group, with no shared liquidity queue. Each modeled exit includes a $0.70 fee per contract.',
              '- Broad coverage requires 80% of market minutes, gaps of at most 30 market minutes, and entry and endpoint quotes within five minutes. Strict coverage requires 95%, at most five missing minutes in a row, and both endpoints within two minutes. The broker-bracket subset uses the broad standard and excludes ambiguous order changes.',
              '- The fixed entry tape holds your later entries constant. Results include actual outcomes for unsupported trades in the account bridge, and the rule comparison assigns no profit to cash freed for potential replacement trades.',
              '- The JSON includes the complete grid, group-level fills, quote and statement provenance, and sensitivity to removing the best group or entry date.']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('statements','journal','archive','projection','output'):
        parser.add_argument('--'+arg,type=Path,required=True)
    for arg in ('beginning','ending'):
        parser.add_argument('--'+arg,required=True)
    parser.add_argument('--origin-statement',help='Earlier statement for recovering the starting portfolio entry lots')
    args = parser.parse_args()
    result = run(args)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,indent=2)
    with args.output.with_suffix('.md').open('x',encoding='utf-8') as handle:
        handle.write(markdown(result))
    print(json.dumps({key:value for key,value in result.items() if key not in {'tables','trades','new_quote_manifest','statement_manifest'}},indent=2))
