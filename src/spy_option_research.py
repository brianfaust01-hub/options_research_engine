"""SPY-only forward simulated portfolio and quote watch set; no broker orders."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from uuid import uuid4
import hashlib
import json
import re
import sqlite3
import sys
import math
from dataclasses import asdict
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = Path('data/processed/spy_option_research')
SETTINGS = Path('research/spy_option_research/settings.json')
VERSION = 'SPY-ONLY-SHADOW-2026-11-02-v1'
ET = ZoneInfo('America/New_York')


def json_value(value):
    """Preserve missing provider metadata as null, never fabricated values."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, 'item'):
        return json_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def settings(root):
    path = Path(root)/SETTINGS
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(json_value(value), indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def publish_watch(root, record, now):
    directory = Path(root)/DIRECTORY
    path = directory/'watch.json'
    old = json.loads(path.read_text()) if path.exists() else {'contracts': {}}
    contracts = old['contracts']
    for selection in record['selections']:
        if selection['status'] != 'SELECTED':
            continue
        c = selection['contract']
        symbol = c['contractSymbol']
        contracts[symbol] = {'contract_symbol': symbol, 'ticker': 'SPY',
                             'expiration': str(c['Expiration'])[:10],
                             'strategy': selection['side'], 'research_test': VERSION,
                             'selected_at': record['selected_at'],
                             'recommendations': [{'recommendation_id': selection['selection_id'],
                                                  'recommendation_date': record['selected_at'],
                                                  'allocation_decision': 'RESEARCH_ONLY_NOT_ALLOCATED'}]}
    today = now.astimezone(ET).date().isoformat()
    contracts = {k: v for k, v in contracts.items()
                 if v['expiration'] >= today and datetime.fromisoformat(v['selected_at']) >= now-timedelta(days=60)}
    atomic_json(path, {'version': VERSION, 'updated_at': now.isoformat(), 'contracts': contracts})


def watch_contracts(root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    configuration = settings(root)
    if not configuration.get('enabled') or now.astimezone(ET).date().isoformat() < configuration['start_date']:
        return {}
    path = Path(root)/DIRECTORY/'watch.json'
    watch = json.loads(path.read_text()) if path.exists() else {'contracts': {}}
    result = {k: v for k, v in watch['contracts'].items()
            if v['expiration'] >= now.astimezone(ET).date().isoformat()
            and datetime.fromisoformat(v['selected_at']) <= now
            and now-datetime.fromisoformat(v['selected_at']) <= timedelta(days=60)}
    ledger_path = Path(root)/DIRECTORY/'ledger.sqlite'
    if ledger_path.exists():
        from shadow_option_ledger import ComparisonLedger
        db = sqlite3.connect(ledger_path.resolve().as_uri()+'?mode=ro', uri=True)
        try:
            row = db.execute('SELECT payload FROM state WHERE id=1').fetchone()
            if row:
                for item in ComparisonLedger.watch(None, json.loads(row[0])).values():
                    result.setdefault(item['contract_symbol'], {**item, 'research_test': VERSION})
        finally:
            db.close()
    return result


def policy_fingerprint(root):
    from policy_evidence import RULE_FILES
    root = Path(root)
    h = hashlib.sha256()
    for name in sorted(set(RULE_FILES) | {'spy_option_research.py', 'shadow_option_ledger.py',
                       'configuration_profile_shadow.py', 'position_review.py', 'portfolio_exposure.py',
                       'decision_enrichment.py', 'intraday_option_paths.py', 'schwab/market_data_client.py'}):
        p = root/'src'/name
        h.update(name.encode())
        h.update(p.read_text(encoding='utf-8-sig').encode() if p.exists() else b'MISSING')
    h.update((root/SETTINGS).read_text(encoding='utf-8-sig').encode())
    h.update(sys.version.encode())
    import importlib.metadata
    for package in ('pandas', 'numpy', 'pandas_market_calendars'):
        h.update((package+importlib.metadata.version(package)).encode())
    return h.hexdigest()


def build_candidate(root, record, now):
    from trade_constructor import construct_trade
    from opportunity_engine import evaluate_opportunities
    from decision_enrichment import enrich_decisions
    from portfolio_allocator import allocate_portfolio
    signal = dict(record['signal'])
    signal['HoldingPeriodDays'] = record['holding_days_for_contract_fit']
    signal['Ticker'] = 'SPY'
    by_side = {s['side']: s.get('contract') for s in record['selections']}
    def selector(**kwargs):
        return by_side['Long Put' if 'Put' in kwargs['opportunity_type'] else 'Long Call']
    trade = evaluate_opportunities(pd.Series(signal), trade_factory=lambda row: construct_trade(row, selector=selector))
    frame = pd.DataFrame([asdict(trade)])
    sources = sorted((Path(root)/'data/processed').glob('trade_recommendations_*.csv'), key=lambda p: p.stat().st_mtime)
    if not sources:
        raise ValueError('SPY needs the same-session completed broad-scan market context')
    broad = pd.read_csv(sources[-1], low_memory=False)
    if broad.empty or 'RecommendationDate' not in broad:
        raise ValueError('Broad context lacks dated lineage')
    dates = pd.to_datetime(broad.RecommendationDate, errors='coerce')
    if dates.isna().any() or any(d.date() != now.astimezone(ET).date() for d in dates):
        raise ValueError('SPY market context is from another session')
    row = broad.iloc[0]
    context = {k: row.get(k) for k in ('market_regime', 'risk_mode', 'allocation_bias')}
    frame = allocate_portfolio(frame, context, max_recommendations=1)
    frame = enrich_decisions(frame, pd.DataFrame([signal]), as_of=now.astimezone(ET).date(), earnings_provider=lambda ticker: None)
    # An ETF has no single company earnings event; constituent and macro events
    # remain risks. Do not invent a corporate earnings date for SPY.
    frame['earnings_status'] = 'NOT_APPLICABLE_ETF'
    frame['earnings_allocation_override'] = False
    for k, v in context.items():
        frame[k] = v
    frame['breadth_regime'] = row.get('breadth_regime')
    return frame


def publish_portfolio(root, ledger):
    value = ledger.snapshot()
    value['research_test'] = VERSION
    value['universe'] = 'SPY_ONLY'
    value['note'] = 'Independent SPY baseline-rules shadow, not the delta/IV challenger or actual broker.'
    atomic_json(Path(root)/DIRECTORY/'portfolio_latest.json', value)
    return value


def record_decision(root, record, now):
    from shadow_option_ledger import ComparisonLedger
    from shadow_comparison_runtime import queue_daily
    config = settings(root)
    fp = policy_fingerprint(root)
    if record['policy_fingerprint'] != fp:
        raise ValueError('Frozen SPY selection policy changed')
    manifest_path = Path(root)/'research/six_week_20261029/release_manifest.json'
    if not manifest_path.exists() or json.loads(manifest_path.read_text(encoding='utf-8-sig')).get('spy_expected_initial_fingerprint') != fp:
        raise ValueError('Reviewed SPY release fingerprint does not match')
    ledger = ComparisonLedger(Path(root)/DIRECTORY/'ledger.sqlite')
    try:
        if not ledger.db.execute('SELECT 1 FROM state').fetchone():
            ledger.initialize(now, capital=config.get('initial_capital', 15000),
                              fee_per_contract=config.get('fee_per_contract_per_side', .70),
                              market_slippage=config.get('market_slippage_per_share', .01),
                              fingerprint=fp, portfolio_names=('baseline',))
        frame = pd.DataFrame(record['candidates'])
        source = json.dumps(record['candidates'], sort_keys=True)
        source_hash = hashlib.sha256(source.encode()).hexdigest()
        key = 'SPY:'+now.astimezone(ET).date().isoformat()
        if any(p['stale_or_missing_marks'] for p in ledger.snapshot(at=now)['portfolios'].values()):
            queue_daily(ledger, key, frame, now, fp, source_hash)
            status = 'DEFERRED_FOR_FRESH_HOLDING_QUOTES'
        else:
            changed = ledger.capture_daily(key, frame, now, fingerprint=fp, source_hash=source_hash)
            status = 'RECORDED' if changed else 'ALREADY_RECORDED'
        publish_portfolio(root, ledger)
        return status
    finally:
        ledger.close()


def consume_bundle(path, root=ROOT, now=None):
    import gzip
    from shadow_option_ledger import ComparisonLedger
    from shadow_comparison_runtime import apply_pending
    now = now or datetime.now(timezone.utc)
    config = settings(root)
    database = Path(root)/DIRECTORY/'ledger.sqlite'
    if not config.get('enabled') or not database.exists():
        return {'status': 'AWAITING_FIRST_SPY_DECISION'}
    raw = Path(path).read_bytes()
    bundle = json.loads(gzip.decompress(raw))
    bundle['_raw_source_sha256'] = hashlib.sha256(raw).hexdigest()
    ledger = ComparisonLedger(database)
    try:
        fp = policy_fingerprint(root)
        changed = ledger.process_bundle(str(Path(path).resolve()), bundle, now, fingerprint=fp)
        apply_pending(ledger, now, fp)
        publish_portfolio(root, ledger)
        atomic_json(Path(root)/DIRECTORY/'processing_health_latest.json', {
            'status': 'UPDATED', 'at': now.isoformat(),
        })
        return {'status': 'UPDATED' if changed else 'ALREADY_PROCESSED'}
    finally:
        ledger.close()


def capture(root=ROOT, now=None, history=None, selector=None, evaluate=None, candidate_builder=None):
    from intraday_option_paths import session_bounds
    clean = json_value
    fixed_clock = now is not None
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    configuration = settings(root)
    if not configuration.get('enabled'):
        return {'status': 'DISABLED'}
    if now.astimezone(ET).date().isoformat() < configuration['start_date']:
        return {'status': 'AWAITING_START_DATE'}
    bounds = session_bounds(now)
    if not bounds or not bounds[0] <= now < bounds[1]:
        return {'status': 'OUTSIDE_REGULAR_SESSION'}
    directory = root/DIRECTORY
    path = directory/'selections'/f"{now.astimezone(ET).date()}.json"
    if path.exists():
        record = json.loads(path.read_text())
        publish_watch(root, record, now)
        record_decision(root, record, now)
        return {'status': 'ALREADY_CAPTURED', 'source': str(path)}
    if history is None:
        from schwab.market_data_client import get_normalized_price_history
        history = lambda: get_normalized_price_history(ticker='SPY', period_type='year', period=1,
                                                       frequency_type='daily', frequency=1,
                                                       need_extended_hours_data=False)
    if selector is None:
        from option_selector import select_best_contract
        selector = select_best_contract
    if evaluate is None:
        from indicators import calculate_indicators_for_ticker
        from research_engine import evaluate_strategies
        from opportunity_engine import calculate_directional_opportunity_scores
        def evaluate(frame):
            row = calculate_indicators_for_ticker('SPY', frame)
            row.update(evaluate_strategies(pd.Series(row)))
            row['opportunity_scores'] = calculate_directional_opportunity_scores(pd.Series(row))
            return row
    frame = pd.DataFrame(history())
    if len(frame) < 200 or not {'Close', 'High', 'Low', 'Volume'}.issubset(frame):
        raise ValueError('SPY research requires complete price history')
    if frame[['Close', 'High', 'Low', 'Volume']].tail(200).isna().any().any():
        raise ValueError('SPY history has missing measurements')
    record = {'version': VERSION, 'ticker': 'SPY', 'selected_at': now.isoformat(),
              'stage': 'SPY_ONLY_FORWARD_SHADOW',
              'signal': clean(evaluate(frame)), 'selections': [],
              'holding_days_for_contract_fit': configuration['holding_days'],
              'note': 'Both sides are observed; only the normal technical signal can qualify a trade. Simulated orders and fills live in the isolated SPY portfolio.',
              'configuration_sha256': hashlib.sha256((root/SETTINGS).read_bytes()).hexdigest()}
    for side in ('Long Call', 'Long Put'):
        selected = selector(ticker='SPY', opportunity_type=side,
                            expected_holding_days=configuration['holding_days'])
        entry = {'side': side, 'selection_id': str(uuid4()), 'status': 'NO_ELIGIBLE_CONTRACT'}
        if selected is not None:
            c = clean(dict(selected))
            required = ['contractSymbol', 'Expiration', 'bid', 'ask']
            if any(c.get(k) is None for k in required):
                raise ValueError('SPY selected contract lacks exact identity or quote')
            if not re.fullmatch(r'SPY\d{6}[CP]\d{8}', str(c['contractSymbol']).replace(' ', '')):
                raise ValueError('SPY selector returned another underlying')
            dte = (datetime.fromisoformat(str(c['Expiration'])[:10]).date()-now.astimezone(ET).date()).days
            if dte < configuration['minimum_dte'] or not 0 < float(c['bid']) <= float(c['ask']):
                raise ValueError('SPY selected contract violates DTE/quote controls')
            entry.update(status='SELECTED', contract=c)
        record['selections'].append(entry)
    frame = (candidate_builder or build_candidate)(root, record, now)
    if not fixed_clock:
        now = datetime.now(timezone.utc)
        if now >= bounds[1]:
            raise ValueError('SPY decision became available after the regular session')
        record['selected_at'] = now.isoformat()
    frame = frame.copy(deep=True)
    frame['RecommendationID'] = str(uuid4())
    frame['RecommendationDate'] = now.isoformat()
    record['candidates'] = clean(frame.to_dict('records'))
    record['policy_fingerprint'] = policy_fingerprint(root)
    # Commit an immutable complete record before publishing its derived watch set.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(clean(record), indent=2, allow_nan=False), encoding='utf-8')
    try:
        temporary.rename(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    publish_watch(root, record, now)
    decision_status = record_decision(root, record, now)
    atomic_json(directory/'health_latest.json', {'status': 'CAPTURED', 'at': now.isoformat(),
                                                'selected': sum(s['status'] == 'SELECTED' for s in record['selections']),
                                                'decision_status': decision_status})
    return {'status': 'CAPTURED', 'source': str(path)}


def record_quote_health(root, bundle, source):
    """Derived SPY-only health; original immutable quote bundle is authoritative."""
    symbols = {''.join(c['contract_symbol'].split()) for c in bundle.get('contracts', [])
               if c.get('research_test') == VERSION}
    if not symbols:
        return
    date = datetime.fromisoformat(bundle['started_at']).astimezone(ET).date().isoformat()
    path = Path(root)/DIRECTORY/'quote_health'/f'{date}.json'
    data = json.loads(path.read_text()) if path.exists() else {'date': date, 'sources': [], 'contracts': {}, 'failed_observation_records': 0}
    if str(source) in data['sources']:
        return
    data['sources'].append(str(source))
    for point in bundle.get('observations', []):
        symbol = ''.join(point['contract_symbol'].split())
        if symbol not in symbols:
            continue
        item = data['contracts'].setdefault(symbol, {'valid_sample_minutes': [], 'last_valid_observation': None})
        if point.get('quote_status') == 'OBSERVED' and point.get('eligible_for_sampled_returns'):
            slot = int(datetime.fromisoformat(point['observed_at']).timestamp()//60)
            item['valid_sample_minutes'] = sorted(set(item['valid_sample_minutes']) | {slot})
            item['last_valid_observation'] = point['observed_at']
        else:
            data['failed_observation_records'] += 1
    data['note'] = 'Sample counts, not complete path coverage or simulated trading returns.'
    atomic_json(path, data)


def research_status(root=ROOT, now=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    config = settings(root)
    directory = root/DIRECTORY
    records = sorted((directory/'selections').glob('*.json'))
    health = directory/'health_latest.json'
    processing_health = directory/'processing_health_latest.json'
    quote_files = sorted((directory/'quote_health').glob('*.json'))
    latest = json.loads(quote_files[-1].read_text()) if quote_files else None
    quote_summary = None if latest is None else {
        'date': latest['date'], 'contracts_sampled': len(latest['contracts']),
        'valid_contract_minutes': sum(len(v['valid_sample_minutes']) for v in latest['contracts'].values()),
        'failed_observation_records': latest['failed_observation_records'],
        'last_valid_observation': max((v['last_valid_observation'] for v in latest['contracts'].values()
                                       if v['last_valid_observation']), default=None)}
    portfolio = None
    database = directory/'ledger.sqlite'
    if database.exists():
        from experiment_reporting import instant, period
        db = sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True)
        try:
            db.execute('BEGIN')
            state_row = db.execute('SELECT payload FROM state WHERE id=1').fetchone()
            if state_row:
                state = json.loads(state_row[0])
                history = [(instant(at), json.loads(payload)) for at, payload in
                           db.execute("SELECT at,payload FROM valuations WHERE portfolio='baseline' ORDER BY id")
                           if instant(at) <= now]
                if history:
                    end = history[-1][0]
                    start = instant(state['started_at'])
                    local = now.astimezone(ET)
                    monday = (local-timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
                    portfolio = {'started_at': start.isoformat(), 'as_of': end.isoformat(),
                                 'since_start': period(history, start, end, state['capital']),
                                 'this_week': period(history, max(monday, start), end, state['capital']) if end >= monday else None,
                                 'health': state['health']}
        finally:
            db.close()
    return {'mode': 'SPY_ONLY_FORWARD_SHADOW',
            'status': 'AWAITING_START_DATE' if config and now.astimezone(ET).date().isoformat() < config['start_date'] else
                      ('FORWARD_SHADOW' if portfolio else 'AWAITING_FIRST_SELECTION') if config.get('enabled') else 'DISABLED',
            'selection_sessions': len(records), 'contracts_watched': len(watch_contracts(root, now)),
            'last_capture_health': json.loads(health.read_text()) if health.exists() else None,
            'last_processing_health': json.loads(processing_health.read_text()) if processing_health.exists() else None,
            'latest_quote_health': quote_summary,
            'portfolio': portfolio,
            'returns': portfolio['since_start']['return_on_starting_nav'] if portfolio else None,
            'transfer_hypothesis': 'Do stock-derived technical signals and contract/risk rules transfer to a diversified index? This is unvalidated; no-trade or weak performance is a valid finding.',
            'note': 'Independent SPY-only $15,000 simulated book using baseline rules. Different universe and inception; not a matched delta/IV comparison.'}


if __name__ == '__main__':
    try:
        print(json.dumps(capture()))
    except Exception as error:
        atomic_json(ROOT/DIRECTORY/'health_latest.json', {'status': 'FAILED_CAPTURE',
                    'at': datetime.now(timezone.utc).isoformat(), 'error_type': type(error).__name__})
        print('SPY research capture failed: '+type(error).__name__)
        raise SystemExit(1)
