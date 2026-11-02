"""Observational condition/performance monitoring. Never changes trading state."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import sqlite3
from uuid import uuid4
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = Path('data/processed/evidence_monitor')
VERSION = 'EVIDENCE-MONITOR-2026-11-02-v1'
RECENT_DATES = 5
REFERENCE_DATES = 20
MIN_REFERENCE_DATES = 8
MIN_EPISODES = 20
ET = ZoneInfo('America/New_York')


def number(value):
    try:
        value = float(value)
        return value if np.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer, np.floating)):
        return clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def alert(code, category, evidence, action):
    return {'code': code, 'category': category, 'evidence': evidence, 'review_action': action}


def compare_windows(frame, value='return'):
    """Disjoint entry-date windows; uncertainty clusters observations by date."""
    f = frame.copy()
    f[value] = pd.to_numeric(f[value], errors='coerce')
    f = f.dropna(subset=['date', value])
    dates = sorted(f.date.unique())
    recent_dates = dates[-RECENT_DATES:]
    reference_dates = dates[-(RECENT_DATES+REFERENCE_DATES):-RECENT_DATES]
    recent = f[f.date.isin(recent_dates)]
    reference = f[f.date.isin(reference_dates)]
    def describe(g):
        values = g[value]
        return {'episodes': len(g), 'entry_dates': g.date.nunique(),
                'first_date': g.date.min() if len(g) else None,
                'last_date': g.date.max() if len(g) else None,
                'mean': values.mean() if len(g) else None,
                'median': values.median() if len(g) else None,
                'positive_rate': values.gt(0).mean() if len(g) else None}
    result = {'status': 'INSUFFICIENT_EVIDENCE', 'recent': describe(recent),
              'reference': describe(reference), 'delta_date_weighted_mean': None,
              'date_cluster_95_interval': None}
    if (len(recent_dates) < RECENT_DATES or len(reference_dates) < MIN_REFERENCE_DATES
            or len(recent) < MIN_EPISODES or len(reference) < MIN_EPISODES):
        return clean(result)
    a = recent.groupby('date')[value].mean().to_numpy()
    b = reference.groupby('date')[value].mean().to_numpy()
    rng = np.random.default_rng(20261102)
    draws = rng.choice(a, (1000, len(a))).mean(axis=1)-rng.choice(b, (1000, len(b))).mean(axis=1)
    low, high = np.quantile(draws, [.025, .975])
    result.update(status='REVIEW_DETERIORATION' if high < 0 else 'NO_CLEAR_DETERIORATION',
                  delta_date_weighted_mean=a.mean()-b.mean(), date_cluster_95_interval=[low, high])
    return clean(result)


def expected_close(now):
    import pandas_market_calendars as mcal
    schedule = mcal.get_calendar('NYSE').schedule(start_date=now.date()-timedelta(days=15), end_date=now.date())
    completed = schedule[schedule.market_close <= pd.Timestamp(now)]
    return completed.index[-1].date().isoformat() if len(completed) else None


def read_daily(root, now):
    columns = {'ticker', 'option_strategy', 'action', 'market_regime', 'risk_mode', 'breadth_regime',
               'broker_delta', 'implied_volatility', 'spread_pct', 'execution_score', 'portfolio_score',
               'RecommendationDate', 'PolicyEvidenceFingerprint'}
    by_day = {}
    errors = []
    # Lexicographically last timestamp per day, not multiple reruns as new dates.
    for path in sorted((root/'data/processed').glob('trade_recommendations_*.csv')):
        date = path.stem.removeprefix('trade_recommendations_')[:8]
        try:
            day = datetime.strptime(date, '%Y%m%d').date()
        except ValueError:
            continue
        if day <= now.astimezone(ET).date() and day >= now.astimezone(ET).date()-timedelta(days=60):
            by_day[day.isoformat()] = path
    values = []
    for day, path in sorted(by_day.items()):
        try:
            f = pd.read_csv(path, usecols=lambda c: c in columns, low_memory=False)
            if f.empty:
                raise ValueError('Empty candidate file')
            if 'RecommendationDate' in f:
                times = pd.to_datetime(f.RecommendationDate, errors='coerce', format='mixed')
                if times.isna().any():
                    raise ValueError('Missing recommendation timestamps')
                times = [t.tz_localize(ET) if t.tzinfo is None else t for t in times]
                if any(t.tz_convert(ET).date().isoformat() != day or t > pd.Timestamp(now) for t in times):
                    raise ValueError('Invalid or mixed recommendation dates')
            row = f.iloc[0]
            mask = f.get('action', pd.Series('', index=f.index)).eq('Evaluate Options')
            candidates = f[mask]
            item = {'date': day, 'source': str(path),
                    'policy': str(row.get('PolicyEvidenceFingerprint')) if pd.notna(row.get('PolicyEvidenceFingerprint')) and row.get('PolicyEvidenceFingerprint') else 'UNRECORDED',
                    'market_regime': row.get('market_regime', 'UNKNOWN'),
                    'risk_mode': row.get('risk_mode', 'UNKNOWN'),
                    'breadth_regime': row.get('breadth_regime', 'UNKNOWN'),
                    'candidate_count': len(candidates)}
            for field in ('broker_delta', 'implied_volatility', 'spread_pct', 'execution_score'):
                series = pd.to_numeric(candidates.get(field, pd.Series(dtype=float)), errors='coerce')
                item['median_'+field] = number(series.abs().median() if field == 'broker_delta' else series.median())
            values.append(item)
        except (OSError, ValueError, pd.errors.ParserError) as error:
            errors.append({'source': str(path), 'error_type': type(error).__name__})
    return clean(values), errors


def outcome_reviews(frame, now):
    from config_combination_analysis import post_fix_episode_frame
    from hindsight_quality import reviewed_quality_view
    if frame is None:
        return {'status': 'UNAVAILABLE', 'comparisons': [], 'warnings': []}
    required = {'RecommendationID', 'RecommendationDate', 'Direction', 'Horizon7DDirectionalReturnPct'}
    if not required.issubset(frame):
        return {'status': 'MISSING_OUTCOME_SCHEMA', 'comparisons': [], 'warnings': []}
    frame, excluded = reviewed_quality_view(frame)
    # Preserve canonical episode boundaries BEFORE filtering to corrected policy.
    episodes = post_fix_episode_frame(frame)
    if 'Horizon7DStatus' in episodes:
        episodes = episodes[episodes.Horizon7DStatus.eq('COMPLETE')]
    episodes = episodes[pd.to_datetime(episodes.RecommendationDate, format='mixed', utc=True) <= pd.Timestamp(now)]
    future_outcomes = 0
    if 'Horizon7DEvaluationDate' in episodes:
        dates = pd.to_datetime(episodes.Horizon7DEvaluationDate, errors='coerce', utc=True, format='mixed')
        future = dates.isna() | dates.dt.date.gt(now.astimezone(ET).date())
        future_outcomes = int(future.sum())
        episodes = episodes[~future]
    episodes = episodes.copy()
    episodes['date'] = episodes._Date.dt.strftime('%Y-%m-%d')
    episodes['return'] = episodes._Return
    if 'PolicyEvidenceFingerprint' not in episodes:
        episodes['PolicyEvidenceFingerprint'] = 'UNRECORDED'
    episodes['policy'] = episodes.PolicyEvidenceFingerprint.fillna('UNRECORDED').replace('', 'UNRECORDED')
    comparisons = []
    counts = []
    for policy, group in episodes.groupby('policy'):
        counts.append({'policy': policy, 'episodes': len(group), 'entry_dates': group.date.nunique()})
        strata = [('all', 'all', group)]
        for field in ('Direction', 'MarketRegime'):
            if field in group:
                strata.extend((field, str(name), g) for name, g in group.groupby(field, dropna=False))
        if {'BrokerDelta', 'ImpliedVolatility'}.issubset(group):
            delta = pd.to_numeric(group.BrokerDelta, errors='coerce').abs()
            iv = pd.to_numeric(group.ImpliedVolatility, errors='coerce')
            labels = pd.Series('MISSING_CONTEXT', index=group.index)
            known = delta.notna() & iv.notna()
            labels.loc[known] = 'OUTSIDE_DELTA_IV_PROFILE'
            labels.loc[known & delta.gt(.35) & delta.le(.50) & iv.gt(.20) & iv.le(.40)] = 'WITHIN_DELTA_IV_PROFILE'
            strata.extend(('contract_context', name, group.loc[index]) for name, index in labels.groupby(labels).groups.items())
        for family, name, subset in strata:
            result = compare_windows(subset)
            if policy == 'UNRECORDED':
                result['status'] = 'UNKNOWN_POLICY_NOT_COMPARABLE'
            comparisons.append({'policy': policy, 'family': family, 'condition': name, **result})
        # Score-to-outcome relationship is measured within dates, not pooled
        # across a changing market. It is not probability calibration.
        if 'ResearchScore' in group:
            relations = []
            for day, g in group.groupby('date'):
                score = pd.to_numeric(g.ResearchScore, errors='coerce')
                valid = score.notna() & g['return'].notna()
                if valid.sum() >= 5 and score[valid].nunique() > 1 and g.loc[valid, 'return'].nunique() > 1:
                    relations.append({'date': day, 'return': score[valid].rank().corr(g.loc[valid, 'return'].rank())})
            # Each row here is already a date; retain the stricter date-count
            # gate but do not demand twenty independent days per five-day window.
            if relations:
                rr = pd.DataFrame(relations)
                dates = sorted(rr.date.unique())
                comparisons.append({'policy': policy, 'family': 'score_relationship',
                    'condition': 'Within-date ResearchScore rank correlation',
                    'status': 'DESCRIPTIVE_ONLY' if len(dates) >= 13 else 'INSUFFICIENT_EVIDENCE',
                    'recent_mean_correlation': number(rr[rr.date.isin(dates[-5:])]['return'].mean()),
                    'reference_mean_correlation': number(rr[rr.date.isin(dates[-25:-5])]['return'].mean()),
                    'entry_dates': len(dates)})
    return clean({'status': 'AVAILABLE', 'episodes': len(episodes),
                  'excluded_price_basis_rows': len(excluded), 'future_or_unknown_outcomes_excluded': future_outcomes,
                  'policy_cohorts': counts, 'comparisons': comparisons,
                  'warnings': ['Underlying seven-session outcomes are not option P/L or intraday prediction.',
                               'Conditional comparisons are exploratory and not adjusted for multiple testing.',
                               'No calibrated probability model is active; probability drift is not measurable.']})


def shadow_reviews(root, now):
    results = []
    for label, directory in [('broad_comparison', 'configuration_comparison'), ('SPY', 'spy_option_research')]:
        path = root/'data/processed'/directory/'ledger.sqlite'
        if not path.exists():
            health_path = root/'data/processed'/directory/'health_latest.json'
            health = json.loads(health_path.read_text()) if health_path.exists() else None
            results.append({'experiment': label, 'status': 'NOT_STARTED', 'capture_health': health})
            continue
        try:
            db = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=2)
            try:
                db.execute('BEGIN')
                row = db.execute('SELECT payload FROM state WHERE id=1').fetchone()
                if not row:
                    results.append({'experiment': label, 'status': 'NOT_INITIALIZED'})
                    continue
                state = json.loads(row[0])
                if pd.Timestamp(state['last_at']).tz_convert(ET).date() > now.astimezone(ET).date():
                    results.append({'experiment': label, 'status': 'UNAVAILABLE', 'error_type': 'FUTURE_STATE_EXCLUDED'})
                    continue
                if state['mode'] != 'FORWARD_SHADOW':
                    results.append({'experiment': label, 'status': 'NON_FORWARD_DATA_EXCLUDED'})
                    continue
                context = {}
                for payload, in db.execute("SELECT payload FROM inputs WHERE kind='DAILY_DECISION'"):
                    for candidate in json.loads(payload).get('candidates', []):
                        context[candidate['RecommendationID']] = candidate
                for name, book in state['portfolios'].items():
                    rows = []
                    for lot in book['lots'].values():
                        if lot['status'] != 'CLOSED':
                            continue
                        at = pd.Timestamp(lot['entry_at']).tz_convert(ET)
                        candidate = context.get(lot.get('recommendation_id'), {})
                        rows.append({'date': at.date().isoformat(), 'return': lot['closed_net_pnl'],
                                     'market_regime': candidate.get('market_regime', 'UNKNOWN')})
                    frame = pd.DataFrame(rows, columns=['date', 'return', 'market_regime'])
                    tests = [{'condition': 'all', **compare_windows(frame)}]
                    tests.extend({'condition': 'market regime '+str(regime), **compare_windows(g)}
                                 for regime, g in frame.groupby('market_regime'))
                    valuations = db.execute('SELECT at,payload FROM valuations WHERE portfolio=? ORDER BY id DESC LIMIT 1', (name,)).fetchone()
                    latest = json.loads(valuations[1]) if valuations else {}
                    from shadow_option_ledger import trading_gap_seconds
                    gap = trading_gap_seconds(state['last_at'], now) if pd.Timestamp(state['last_at']) <= pd.Timestamp(now) else None
                    results.append({'experiment': label, 'book': name, 'status': 'OBSERVING',
                                    'policy_fingerprint': state['fingerprint'], 'started_at': state['started_at'],
                                    'last_observation': state['last_at'], 'trading_seconds_since_update': gap,
                                    'health': state['health'], 'completed_trades': len(rows),
                                    'current_net_pnl': latest.get('total_net_pnl'),
                                    'stale_or_missing_marks': latest.get('stale_or_missing_marks', []),
                                    'settlement_required': latest.get('settlement_required', []),
                                    'performance_comparisons': tests,
                                    'return_unit': 'Net dollars per completed position; size can explain changes. Not probability or portfolio return.'})
            finally:
                db.close()
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
            results.append({'experiment': label, 'status': 'UNAVAILABLE', 'error_type': type(error).__name__})
    return clean(results)


def build_monitor(root=ROOT, hindsight_frame=None, source_path=None, now=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    result = {'version': VERSION, 'generated_at': now.isoformat(), 'mode': 'OBSERVATION_ONLY_NO_TRADING_AUTHORITY',
              'alerts': [], 'limitations': ['No signal, allocation, sizing, exit, account or experiment changes.',
              'No-clear-deterioration means no detection in this window, not proof of a durable edge.',
              'Date grouping reduces repeated-observation bias but cannot remove ticker/market dependence.',
              'This is an initial review monitor, not a validated regime-change predictor.']}
    try:
        daily, errors = read_daily(root, now)
        result['conditions'] = {'sessions': daily, 'source_errors': errors}
        if errors:
            result['alerts'].append(alert('CANDIDATE_SOURCE_ERRORS', 'DATA', errors, 'Check affected daily artifacts before interpreting changes.'))
        if len(daily) >= 2:
            changes = {k: {'previous': daily[-2][k], 'latest': daily[-1][k]}
                       for k in ('market_regime', 'risk_mode', 'breadth_regime') if daily[-2][k] != daily[-1][k]}
            result['conditions']['changed_from_previous_session'] = changes
            if changes:
                result['alerts'].append(alert('CONDITIONS_CHANGED', 'CONTEXT', changes, 'Review condition-specific outcomes; do not retune from one session.'))
        distribution_checks = []
        if daily:
            policy = daily[-1]['policy']
            compatible = [d for d in daily if d['policy'] == policy]
            reference, recent = compatible[-25:-5], compatible[-5:]
            for feature in ('median_broker_delta', 'median_implied_volatility', 'median_spread_pct', 'median_execution_score'):
                a = [d[feature] for d in recent if d[feature] is not None]
                b = [d[feature] for d in reference if d[feature] is not None]
                check = {'feature': feature, 'policy': policy, 'recent_dates': len(a), 'reference_dates': len(b),
                         'status': 'INSUFFICIENT_EVIDENCE'}
                if policy != 'UNRECORDED' and len(a) >= 5 and len(b) >= 8:
                    median = float(np.median(a))
                    low, high = float(min(b)), float(max(b))
                    changed = median < low or median > high
                    check.update(status='OUTSIDE_REFERENCE_RANGE' if changed else 'WITHIN_REFERENCE_RANGE',
                                 recent_median=median, reference_min=low, reference_max=high)
                    if changed:
                        execution_worse = ((feature == 'median_spread_pct' and median > high)
                                           or (feature == 'median_execution_score' and median < low))
                        result['alerts'].append(alert('EXECUTION_CONTEXT_CHANGED' if execution_worse else 'CANDIDATE_DISTRIBUTION_CHANGED',
                            'EXECUTION' if execution_worse else 'CONTEXT', check,
                            'Inspect liquidity/feed quality and candidate composition; reference ranges are descriptive, not validated alarm thresholds.'))
                distribution_checks.append(check)
        result['conditions']['distribution_checks'] = distribution_checks
        expected = expected_close(now)
        result['expected_latest_completed_session'] = expected
        if not daily or (expected and daily[-1]['date'] < expected):
            result['alerts'].append(alert('DAILY_CONTEXT_STALE_OR_MISSING', 'DATA', daily[-1]['date'] if daily else None, 'Verify the scheduled scan and its saved outputs.'))
        if source_path is None:
            paths = sorted((root/'data/processed').glob('research_hindsight_*.csv'), key=lambda p: p.stat().st_mtime)
            source_path = paths[-1] if paths else None
        source = Path(source_path) if source_path else None
        if hindsight_frame is None and source and source.exists():
            hindsight_frame = pd.read_csv(source, low_memory=False)
        result['hindsight_source'] = str(source) if source else None
        result['hindsight_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest() if source and source.exists() else None
        result['outcomes'] = outcome_reviews(hindsight_frame, now)
        if hindsight_frame is not None:
            evaluation_dates = []
            for horizon in (3, 5, 7, 14, 30):
                status, date = f'Horizon{horizon}DStatus', f'Horizon{horizon}DEvaluationDate'
                if status in hindsight_frame and date in hindsight_frame:
                    values = pd.to_datetime(hindsight_frame.loc[hindsight_frame[status].eq('COMPLETE'), date], errors='coerce', utc=True, format='mixed')
                    evaluation_dates.extend(v.date().isoformat() for v in values.dropna() if v <= pd.Timestamp(now))
            latest = max(evaluation_dates, default=None)
            result['outcomes']['latest_evaluated_session'] = latest
            if expected and (latest is None or latest < expected):
                result['alerts'].append(alert('OUTCOMES_NEED_REFRESH', 'DATA', {'latest_evaluated': latest, 'expected': expected}, 'Refresh hindsight before judging recent strategy deterioration.'))
        else:
            result['alerts'].append(alert('NO_OUTCOME_DATA', 'DATA', None, 'Generate hindsight; missing outcomes are not zero returns.'))
        for row in result['outcomes'].get('comparisons', []):
            if row['status'] == 'REVIEW_DETERIORATION':
                result['alerts'].append(alert('UNDERLYING_OUTCOME_DETERIORATION', 'PERFORMANCE', row, 'Inspect market mix, stock concentration and execution; preserve frozen policies pending review.'))
        latest_policy = daily[-1]['policy'] if daily else None
        result['current_recommendation_policy'] = latest_policy
        result['current_policy_matured_evidence'] = next((p for p in result['outcomes'].get('policy_cohorts', []) if p['policy'] == latest_policy), None)
        if latest_policy and not result['current_policy_matured_evidence']:
            result['alerts'].append(alert('CURRENT_POLICY_NOT_YET_MATURED', 'EVIDENCE', latest_policy, 'Accumulate outcomes; do not silently pool prior policy fingerprints.'))
        result['shadow_experiments'] = shadow_reviews(root, now)
        for book in result['shadow_experiments']:
            if book['status'] in ('UNAVAILABLE', 'NOT_INITIALIZED'):
                result['alerts'].append(alert('SHADOW_STATE_UNAVAILABLE', 'DATA', book, 'Check experiment capture/processing health without changing trading rules.'))
            if book['status'] == 'NOT_STARTED' and (book.get('capture_health') or {}).get('status') not in (None, 'NOT_STARTED', 'CAPTURED'):
                result['alerts'].append(alert('SHADOW_CAPTURE_FAILED', 'DATA', book, 'Inspect the failed sidecar; no return is inferred.'))
            if book.get('trading_seconds_since_update') is not None and book['trading_seconds_since_update'] > 300:
                result['alerts'].append(alert('SHADOW_FEED_STALE', 'DATA', book, 'Verify quote collection and authorization; do not classify stale marks as strategy weakness.'))
            if book.get('stale_or_missing_marks') or book.get('settlement_required'):
                result['alerts'].append(alert('SHADOW_VALUATION_LIMITED', 'DATA', book, 'Review quote/settlement evidence before interpreting NAV.'))
            for row in book.get('performance_comparisons', []):
                if row['status'] == 'REVIEW_DETERIORATION':
                    result['alerts'].append(alert('OPTION_OUTCOME_DETERIORATION', 'PERFORMANCE', {'experiment': book['experiment'], 'book': book['book'], **row}, 'Review exposure, costs, signals and condition mix; no automatic response.'))
        # Live broker attribution is not deterministic yet; never invent a
        # condition-level attribution from statement NAV or heuristic fills.
        result['actual_broker_attribution'] = 'Account statements remain authoritative; condition-level broker option P/L monitoring awaits deterministic recommendation/order linkage.'
        result['status'] = 'REVIEW_DATA' if any(a['category'] == 'DATA' for a in result['alerts']) else ('REVIEW_PERFORMANCE' if any(a['category'] == 'PERFORMANCE' for a in result['alerts']) else 'OBSERVING_WITH_EVIDENCE_LIMITS')
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        result.update(status='MONITOR_UNAVAILABLE', error_type=type(error).__name__)
    return clean(result)


def monitor_markdown(value):
    lines = ['## Conditions and performance monitor', '',
             f"Status: **{value['status']}**. Evidence checked: {value['generated_at']}.", '',
             '**Observation only:** flags request review; they never change recommendations or the frozen experiments.']
    for item in value.get('alerts', []):
        lines += ['', f"- **{item['category']}: {item['code'].replace('_', ' ').lower()}** — {item['review_action']}"]
    outcomes = value.get('outcomes', {})
    changes = value.get('conditions', {}).get('changed_from_previous_session', {})
    if changes:
        lines += ['', 'Latest session context changes: '+ '; '.join(f"{k.replace('_', ' ')}: {v['previous']} → {v['latest']}" for k, v in changes.items())+'.']
    comparisons = outcomes.get('comparisons', [])
    lines += ['', f"Matured post-fix directional episodes: {outcomes.get('episodes', 0)}. Latest evaluated session: {outcomes.get('latest_evaluated_session', 'unavailable')}.", '',
              '| Policy | Condition | Recent episodes / dates | Reference episodes / dates | Mean return recent / reference | Result |', '|---|---|---:|---:|---|---|']
    shown = [r for r in comparisons if r.get('family') == 'all' or r.get('status') == 'REVIEW_DETERIORATION']
    for row in shown:
        if row.get('family') == 'score_relationship':
            continue
        a, b = row['recent'], row['reference']
        fmt = lambda v: 'unavailable' if v is None else f'{v:.2%}'
        lines.append(f"| {str(row['policy'])[:12]} | {row['family']}: {row['condition']} | {a['episodes']} / {a['entry_dates']} | {b['episodes']} / {b['entry_dates']} | {fmt(a['mean'])} / {fmt(b['mean'])} | {row['status']} |")
    for book in value.get('shadow_experiments', []):
        tests = book.get('performance_comparisons', [])
        comparison_status = tests[0]['status'] if tests else 'UNAVAILABLE'
        lines += ['', f"{book['experiment']} / {book.get('book', 'not initialized')}: {book['status']}; completed positions {book.get('completed_trades', 0)}; deterioration assessment {comparison_status}."]
    lines += ['', 'Windows: five recent entry dates versus up to twenty earlier dates within each recorded policy. At least five recent/eight reference dates and twenty episodes per window are needed for a performance flag. Confidence intervals resample entry dates; they are exploratory, not multiple-testing-adjusted guarantees.', '',
              'Underlying outcomes, simulated option outcomes and actual broker returns remain separate. No-clear-deterioration is not proof of stability. Full metrics, uncertainty and review evidence are retained in the JSON report.', '']
    return '\n'.join(lines)


def publish(root=ROOT, now=None):
    root = Path(root)
    value = build_monitor(root, now=now)
    output = root/OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    previous_path = output/'latest.json'
    try:
        previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    except (OSError, ValueError):
        previous = {}
    def identities(items):
        result = set()
        for item in items:
            evidence = item.get('evidence')
            detail = evidence if isinstance(evidence, dict) else {}
            key = [item['code'], detail.get('experiment'), detail.get('book'),
                   detail.get('policy'), detail.get('family'), detail.get('condition')]
            result.add(json.dumps(key))
        return result
    old, current = identities(previous.get('alerts', [])), identities(value['alerts'])
    value['alert_changes'] = {'new_topics': sorted(current-old), 'ongoing_topics': sorted(current & old),
                             'not_present_in_latest_check': sorted(old-current) if value['status'] != 'MONITOR_UNAVAILABLE' else [],
                             'note': 'Repeated checks are not independent evidence; disappearance of a flag is not proof of recovery.'}
    tag = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    text = json.dumps(value, indent=2, allow_nan=False)
    (output/f'monitor_{tag}.json').write_text(text, encoding='utf-8')
    for name, content in [('latest.json', text), ('latest.md', monitor_markdown(value))]:
        target = output/name
        temporary = target.with_name(target.name+'.'+uuid4().hex+'.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(target)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    value = publish(args.root)
    print(json.dumps({'status': value['status'], 'alerts': len(value['alerts'])}))
    raise SystemExit(1 if value['status'] == 'MONITOR_UNAVAILABLE' else 0)
