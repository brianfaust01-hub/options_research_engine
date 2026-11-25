"""Read-only paired sensitivity analysis of target extensions and profit stops."""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from broker_performance_attribution import build
from exit_path_review import coverage, schedule, stamp, symbol
from short_term_rule_test import EXIT_FEE, load_quotes, order_history, select_bracket


def rules():
    result = [{'name': 'original', 'activation': None, 'multiple': 1., 'lock': None, 'gate': 'always'}]
    for activation in (.75, .90):
        for gate in ('always', 'rising'):
            for multiple in (1.25, 1.50):
                result.append(dict(name=f'extend_{activation}_{multiple}_{gate}',
                                   activation=activation, multiple=multiple, lock=None, gate=gate))
                for lock in (.50, .75):
                    result.append(dict(name=f'paired_{activation}_{multiple}_{lock}_{gate}',
                                       activation=activation, multiple=multiple, lock=lock, gate=gate))
            for lock in (.50, .75):
                result.append(dict(name=f'protect_{activation}_{lock}_{gate}',
                                   activation=activation, multiple=1., lock=lock, gate=gate))
    return result


def rising(points, index, slippage):
    """Only quotes known by the current observation may establish momentum."""
    observed, quoted, bid, ask = points[index]
    for previous_index in range(index-1, -1, -1):
        previous = points[previous_index]
        age = quoted-previous[1]
        if age > 300:
            break
        if age >= 180:
            return bid > previous[2]+slippage and (ask-bid)/bid <= .10
    return False


def replay(points, entry, quantity, stop, target, rule, delay, slippage,
           max_per_quote=None, amendments=(), start_index=0):
    remaining = quantity
    initial_target = target
    threshold = entry + (rule['activation'] or 0)*(target-entry)
    ready = None
    active = False
    amendment_index = 0
    protection = 0.
    pending_stop = False
    fills = []
    for index, (observed, quoted, bid, ask) in enumerate(points):
        while amendment_index < len(amendments) and amendments[amendment_index][0] <= quoted:
            _, size, kind, price = amendments[amendment_index]
            amendment_index += 1
            if size == remaining:
                if kind == 'STP':
                    stop = max(price, protection)
                elif not active:
                    target = price
        if index < start_index:
            continue
        # Existing orders remain effective during replacement latency. A stop
        # amendment made using this sample can only trigger on a later sample.
        pending_stop = pending_stop or bid <= stop
        if pending_stop:
            price, reason = max(0., bid-slippage), 'stop'
        elif bid >= target+slippage:
            price, reason = target, 'target'
        else:
            if remaining == quantity and rule['activation'] is not None and not active:
                gate = rule['gate'] == 'always' or rising(points, index, slippage)
                if ready is None and bid >= threshold and gate:
                    ready = observed+delay
                if ready is not None and observed >= ready and quoted >= ready:
                    # Recheck the same observable conditions when the replacement
                    # becomes effective, rather than act on an expired signal.
                    if bid >= threshold and gate:
                        active = True
                        target = max(target, entry+rule['multiple']*(initial_target-entry))
                    else:
                        ready = None
            if active and rule['lock'] is not None:
                recent = [p[2] for p in points[max(0, index-5):index+1]]
                buffer = max(2*(ask-bid), max(recent)-min(recent), .01)
                candidate = math.floor(100*min(entry+rule['lock']*(bid-entry), bid-buffer))/100
                protection = max(protection, candidate)
                stop = max(stop, protection)
            continue
        size = min(remaining, max_per_quote) if max_per_quote else remaining
        fills.append((observed, price, size, reason))
        remaining -= size
        if not remaining:
            break
    if remaining:
        observed, _, bid, _ = points[-1]
        fills.append((observed, max(0., bid-slippage), remaining, 'terminal_mark'))
    net = sum((price-entry)*100*size-EXIT_FEE*size for _, price, size, _ in fills)
    average_exit_at = sum(at*size for at, _, size, _ in fills)/quantity
    return dict(net=net, active=active, fills=fills, average_exit_at=average_exit_at,
                terminal_contracts=sum(size for _, _, size, why in fills if why == 'terminal_mark'))


def intervention_index(points, entry, quantity, stop, target, rule, delay, slippage,
                       first_exit, amendments):
    """Find a feasible replacement while broker evidence shows the lot intact."""
    threshold = entry+rule['activation']*(target-entry)
    ready = None
    amendment_index = 0
    for index, (observed, quoted, bid, ask) in enumerate(points):
        if observed >= first_exit or quoted >= first_exit:
            break
        while amendment_index < len(amendments) and amendments[amendment_index][0] <= quoted:
            _, size, kind, price = amendments[amendment_index]
            amendment_index += 1
            if size == quantity:
                if kind == 'STP':
                    stop = price
                else:
                    target = price
        # A sampled touch of an existing order during the replacement window
        # prevents an assumed successful cancel/replace.
        if bid <= stop or bid >= target+slippage:
            ready = None
            continue
        gate = rule['gate'] == 'always' or rising(points, index, slippage)
        if ready is None and bid >= threshold and gate:
            ready = observed+delay
        if ready is not None and observed >= ready and quoted >= ready:
            if bid >= threshold and gate:
                return index
            ready = None
    return None


def analyze(args):
    actual = build(args.statements, args.journal, args.beginning, args.ending)
    if actual['bridge']['status'] != 'RECONCILED':
        raise ValueError('Broker account bridge failed reconciliation')
    groups = defaultdict(list)
    for unit in actual['units']:
        if unit['side'] == 1 and unit.get('entry_at'):
            groups[(symbol(unit), unit['entry_at'])].append(unit)
    sessions = schedule(actual['start'], (datetime.fromisoformat(actual['end'])+timedelta(days=12)).date())
    cutoff = stamp(actual['end']+'T16:00:00')
    if args.quote_cache.exists():
        raw = args.quote_cache.read_bytes()
        meta = json.loads(args.quote_cache.with_suffix('.manifest.json').read_text())
        if hashlib.sha256(raw).hexdigest() != meta['sha256'] or meta['through'] != actual['end']:
            raise ValueError('Quote cache checksum/date mismatch')
        quotes = json.loads(raw)
        if set(groups_key for groups_key, _ in groups)-set(quotes):
            raise ValueError('Quote cache does not cover requested contracts')
    else:
        quotes, manifest, corrupt = load_quotes(args.archive, args.projection,
                                               {key for key, _ in groups},
                                               [day for day, _, _ in sessions if day <= actual['end']])
        # Persist even missing contracts so a cache is an exact, auditable extract.
        quotes = {key: quotes.get(key, []) for key, _ in groups}
        raw = json.dumps(quotes).encode()
        args.quote_cache.parent.mkdir(parents=True, exist_ok=True)
        with args.quote_cache.open('xb') as handle:
            handle.write(raw)
        meta = dict(sha256=hashlib.sha256(raw).hexdigest(), through=actual['end'],
                    new_manifest=manifest, corrupt_new_bundles=corrupt,
                    prior_projection=str(args.projection))
        args.quote_cache.with_suffix('.manifest.json').write_text(json.dumps(meta), encoding='utf-8')
    brackets, other, changes = order_history(args.statements, actual['start'], actual['end'])
    definitions = rules()
    models = [(0, .01, None), (60, .01, None), (60, .05, None), (60, .05, 1)]
    trades, excluded = [], defaultdict(int)
    for (key, entered), units in sorted(groups.items()):
        start = stamp(entered)
        later = [cl for day, _, cl in sessions if day > entered[:10]]
        deadline = later[4]-60
        if deadline > cutoff:
            excluded['not_mature_five_subsequent_sessions'] += 1
            continue
        quantity = len(units)
        entry = sum(u['entry'] for u in units)/quantity
        stop, target, source, parent = select_bracket(key, start, entry, quantity, brackets[key],
                                                      units[0].get('original_stop'), units[0].get('original_target'))
        points = sorted(tuple(p) for p in quotes.get(key, []) if start <= p[1] <= p[0] <= deadline
                        and any(op <= p[1] <= p[0] < cl for _, op, cl in sessions))
        quality = coverage(points, start, deadline, sessions)
        if stop is None or not points or quality['endpoint_delay_seconds'] > 300:
            excluded['missing_levels_or_endpoint'] += 1
            continue
        first_exit = min((stamp(u['exit_at']) for u in units if u.get('exit_at')), default=cutoff)
        amendments = sorted((*k, next(iter(prices))) for k, prices in changes[(key, parent)].items()
                            if start < k[0] < min(deadline, first_exit) and len(prices) == 1)
        resolved = {a[0] for a in amendments}
        ambiguous = any(start < at < min(deadline, first_exit) and (p != parent or at not in resolved)
                        for at, p in other[key])
        actual_net = sum(u['net_period_contribution'] for u in units)
        fee = sum(u['entry_fee'] for u in units)
        trade = dict(symbol=key, ticker=units[0]['ticker'], entry_at=entered, deadline=deadline,
                     quantity=quantity, entry=entry, initial_stop=stop, initial_target=target,
                     actual_net=actual_net, actual_closed=all(u['status']=='CLOSED' for u in units),
                     bracket_source=source, ambiguous_changes=ambiguous, coverage=quality,
                     period='early' if deadline <= stamp('2026-10-21T16:00:00') else
                     'later' if entered[:10] > '2026-10-21' else 'boundary', outcomes={})
        # Keep the actual comparison on a common ending window and a single,
        # quantity-consistent actual exit. No winner-only selection is made.
        actual_comparable = (trade['actual_closed'] and
                             len({(u['exit_at'], u['exit']) for u in units}) == 1 and
                             stamp(units[0]['exit_at']) <= deadline)
        trade['actual_comparable'] = actual_comparable
        for delay, slip, cap in models:
            model = f'{delay}s_{slip:.2f}_{cap or "full"}'
            outcomes = {}
            for rule in definitions:
                value = replay(points, entry, quantity, stop, target, rule, delay, slip, cap, amendments)
                value['net'] -= fee
                value['holding_hours'] = (value['average_exit_at']-start)/3600
                if actual_comparable and rule['activation'] is not None:
                    index = intervention_index(points, entry, quantity, stop, target, rule,
                                               delay, slip, first_exit, amendments)
                    anchored = None
                    if index is not None:
                        anchored = replay(points, entry, quantity, stop, target, rule,
                                          0, slip, cap, amendments, start_index=index)
                    value['actual_intervention_delta'] = anchored['net']-fee-actual_net if anchored else 0.
                    value['actual_intervention_triggered'] = anchored is not None
                    value['actual_intervention_extra_hours'] = (anchored['average_exit_at']-first_exit)/3600 if anchored else 0.
                    value['actual_intervention_terminal_contracts'] = anchored['terminal_contracts'] if anchored else 0
                outcomes[rule['name']] = value
            trade['outcomes'][model] = outcomes
        trades.append(trade)
    tables = []
    for cohort in ('broad', 'strict', 'broker_brackets'):
        for period in ('all', 'early', 'later'):
            eligible = []
            for trade in trades:
                q = trade['coverage']
                broad = q['coverage'] >= .8 and q['longest_missing_market_minutes'] <= 30 and q['first_delay_seconds'] <= 300
                match = q['qualified_sampled_path'] if cohort == 'strict' else broad
                if cohort == 'broker_brackets':
                    match = match and trade['bracket_source'] == 'BROKER_INITIAL_BRACKET_INFERRED' and not trade['ambiguous_changes']
                if match and (period == 'all' or period == trade['period']):
                    eligible.append(trade)
            for delay, slip, cap in models:
                model = f'{delay}s_{slip:.2f}_{cap or "full"}'
                for rule in definitions[1:]:
                    deltas, by_date = [], defaultdict(float)
                    holding, activations, terminal = [], 0, 0
                    for trade in eligible:
                        outcomes = trade['outcomes'][model]
                        base, candidate = outcomes['original'], outcomes[rule['name']]
                        delta = candidate['net']-base['net']
                        deltas.append(delta)
                        by_date[trade['entry_at'][:10]] += delta
                        holding.append(candidate['holding_hours']-base['holding_hours'])
                        activations += candidate['active']
                        terminal += candidate['terminal_contracts']
                    tables.append(dict(cohort=cohort, period=period, model=model, rule=rule['name'],
                        groups=len(eligible), dates=len(by_date), activations=activations,
                        actual_net=sum(t['actual_net'] for t in eligible),
                        control_net=sum(t['outcomes'][model]['original']['net'] for t in eligible),
                        candidate_net=sum(t['outcomes'][model][rule['name']]['net'] for t in eligible),
                        delta=sum(deltas), improved=sum(max(0, d) for d in deltas),
                        sacrificed=-sum(min(0, d) for d in deltas),
                        without_best_group=sum(deltas)-max([0]+deltas),
                        without_best_date=sum(deltas)-max([0]+list(by_date.values())),
                        extra_holding_hours=sum(holding)/len(holding) if holding else None,
                        terminal_contracts=terminal))
    intervention_tables = []
    for row in tables:
        eligible = [t for t in trades if t['actual_comparable'] and
                    (row['period']=='all' or t['period']==row['period']) and
                    (t['coverage']['qualified_sampled_path'] if row['cohort']=='strict' else
                     t['coverage']['coverage'] >= .80 and
                     t['coverage']['longest_missing_market_minutes'] <= 30 and
                     t['coverage']['first_delay_seconds'] <= 300 and
                     (row['cohort'] != 'broker_brackets' or
                      (t['bracket_source']=='BROKER_INITIAL_BRACKET_INFERRED' and not t['ambiguous_changes'])))]
        deltas = [t['outcomes'][row['model']][row['rule']]['actual_intervention_delta'] for t in eligible]
        by_date = defaultdict(float)
        for t, delta in zip(eligible, deltas):
            by_date[t['entry_at'][:10]] += delta
        intervention_tables.append(dict(cohort=row['cohort'], period=row['period'], model=row['model'],
            rule=row['rule'], groups=len(eligible), actual_net=sum(t['actual_net'] for t in eligible),
            delta=sum(deltas), improved=sum(max(0, d) for d in deltas),
            sacrificed=-sum(min(0, d) for d in deltas),
            without_best_group=sum(deltas)-max([0]+deltas),
            without_best_date=sum(deltas)-max([0]+list(by_date.values())),
            extra_holding_hours=sum(t['outcomes'][row['model']][row['rule']]['actual_intervention_extra_hours'] for t in eligible)/len(eligible) if eligible else None,
            terminal_contracts=sum(t['outcomes'][row['model']][row['rule']]['actual_intervention_terminal_contracts'] for t in eligible),
            activations=sum(t['outcomes'][row['model']][row['rule']]['actual_intervention_triggered'] for t in eligible)))
    return dict(through=actual['end'], bridge=actual['bridge'], rules=definitions,
                replayable_groups=len(trades), excluded=dict(excluded), quote_provenance=meta,
                journal_sha256=actual['journal_sha256'], statements=actual['source_manifest'],
                tables=tables, actual_intervention_tables=intervention_tables, trades=trades)


def markdown(result):
    featured = [r for r in result['tables'] if r['cohort']=='broad' and r['period']=='all'
                and r['model']=='60s_0.01_full']
    lines = ['# Target extension sensitivity review', '',
             f"Statement cutoff {result['through']}. Actual account bridge reconciles. {result['replayable_groups']} mature groups have levels and endpoint quotes.", '',
             'All entries with sufficient evidence are considered, including losers. Every rule uses the same actual entry, quantity and five-subsequent-session endpoint. The live engine and frozen experiments were not changed.', '',
             '| Rule | Groups | Activated | Net change vs modeled original | Extra gains | Gains sacrificed | Change without best date | Extra holding hours/group |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in featured:
        lines.append(f"| {row['rule']} | {row['groups']} | {row['activations']} | ${row['delta']:+,.2f} | ${row['improved']:,.2f} | ${row['sacrificed']:,.2f} | ${row['without_best_date']:+,.2f} | {row['extra_holding_hours'] or 0:+.2f} |")
    lines += ['', '## Interpretation and execution assumptions', '',
        '- Activation is 75% or 90% of the distance from actual entry to the recovered initial target. Target distance becomes 1.25 or 1.50 times that initial distance. Separate extension-only and protection-only rules isolate each contribution.',
        '- Protected rules ratchet a stop to retain 50% or 75% of observed gains, with breathing room of two spreads or the last six sampled bids\' range. The stop never moves downward. New protection takes effect for later observations.',
        '- The rising gate requires the current bid to exceed a sampled bid from three to five minutes earlier by more than modeled slippage, with spread at most 10% of bid. Both checks use already observed quotes. It is an exploratory momentum condition.',
        '- Original stops/targets remain active during zero/60-second replacement latency. A target reached before replacement sells at its existing level. Stops sell at the triggering bid less $0.01/$0.05; a one-contract-per-quote sensitivity is included. Quotes cannot establish executable size or intraminute event order.',
        '- Entry fees are actual; modeled exits cost $0.70/contract. One exit per contract under either policy means no additional transaction fee solely for replacing an order. Overnight gaps remain in the next observed bid.',
        '- Terminal values are bid marks less liquidation costs, not claimed fills. No reinvestment or profits on freed capital are assumed. Holding hours include nights and weekends.',
        '- Broad paths require 80% coverage, no gap over 30 market minutes, and endpoints within five minutes. Strict paths require 95%, no gap over five minutes and endpoints within two minutes. Missing quotes can hide stop crossings.',
        '- Initial brackets and linked amendments are recovered from exports with inferred fill associations. Amendments are applied only before the first actual reduction; later modeled holdings retain their simulated orders. A broker-bracket cohort excludes ambiguous order changes.',
        '- Actual profit on identical groups is recorded separately from the modeled original-order control. A control mismatch limits any translation of paired differences into account returns. No actual-portfolio improvement is established by these comparisons alone.',
        '- Early outcomes end by October 21; later entries start after October 21, with boundary entries excluded from the split. This is a retrospective stability check on previously inspected history, not a pristine holdout. Full grid results, failed variants and outlier sensitivity remain in JSON.',
        '- No parameters were fitted, probability scores calibrated or policy promoted. Raw source files remain immutable.', '']
    if featured:
        row = featured[0]
        lines += [f"Main cohort actual net ${row['actual_net']:+,.2f}; modeled original net ${row['control_net']:+,.2f}. Difference ${row['control_net']-row['actual_net']:+,.2f}.", '']
    lines += ['## Intervention compared with actual exits', '',
        'This second sensitivity starts with the broker-confirmed intact lot. Before intervention, it preserves actual trading even where sampled bids would have stopped the modeled control. A candidate must become effective before the first actual sale, with its gate still satisfied and existing sampled orders untriggered at replacement. After intervention it owns the exit through the common endpoint. Missing intraminute events and the bid-stop model still limit inferred execution.', '',
        'Only simultaneous, fully closed actual groups exiting by the common endpoint enter this comparison. Selection is independent of profit and of the rule. Unactivated groups retain actual net P/L. Later manual decisions are superseded after a candidate activates. The measured effect combines extension/protection with those displaced decisions.', '',
        '| Rule | Groups | Activated | Change vs actual | Extra gains | Gains sacrificed | Extra hours/group | Terminal contracts |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in result['actual_intervention_tables']:
        if row['cohort']=='broad' and row['period']=='all' and row['model']=='60s_0.01_full':
            lines.append(f"| {row['rule']} | {row['groups']} | {row['activations']} | ${row['delta']:+,.2f} | ${row['improved']:,.2f} | ${row['sacrificed']:,.2f} | {row['extra_holding_hours'] or 0:+.2f} | {row['terminal_contracts']} |")
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('statements', 'journal', 'archive', 'projection', 'quote-cache', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('beginning', 'ending'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix('.md').exists():
        raise FileExistsError('Use a new report path')
    result = analyze(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle)
    args.output.with_suffix('.md').write_text(markdown(result), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('through', 'bridge', 'replayable_groups', 'excluded')}, indent=2))
