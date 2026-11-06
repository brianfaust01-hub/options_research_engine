"""Observational VIX/SPY context, isolated from frozen SPY decisions/orders."""
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from zoneinfo import ZoneInfo
from intraday_option_paths import session_bounds
from option_observation_collector import number,timestamp

ROOT=Path(__file__).resolve().parent.parent
DIRECTORY=Path('data/processed/spy_vix_context')
ET=ZoneInfo('America/New_York')
VERSION='SPY-VIX-CONTEXT-2026-11-05-v1'
VIX_SYMBOL='$VIX'


def aware(value):
    value=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if value.tzinfo is None:raise ValueError('Aware context timestamp required')
    return value


def connect(root):
    path=Path(root)/DIRECTORY/'context.sqlite'
    path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=1)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,at TEXT,phase TEXT,payload TEXT);
        CREATE TABLE IF NOT EXISTS slots(slot INTEGER PRIMARY KEY,sample_id TEXT);
        CREATE TABLE IF NOT EXISTS bindings(day TEXT PRIMARY KEY,payload TEXT);
    ''')
    return db


def normalize(security,now):
    security=security if isinstance(security,dict) else {}
    q=security.get('quote') or {}
    q=q if isinstance(q,dict) else {}
    # Cash indices do not necessarily publish a bid/ask. Use timestamped last.
    price=number(q.get('lastPrice'));previous=number(q.get('closePrice'));opening=number(q.get('openPrice'))
    at=timestamp(q.get('tradeTime')) or timestamp(q.get('quoteTime'))
    if at and at.year<2000:at=timestamp(q.get('quoteTime'))
    age=(now-at).total_seconds() if at else None
    if price is None or price<=0:status='MISSING_LEVEL'
    elif security.get('realtime') is not True:status='DELAYED_OR_UNKNOWN_FEED'
    elif at is None:status='MISSING_TIMESTAMP'
    elif age<0:status='FUTURE_TIMESTAMP'
    elif age>120:status='STALE'
    else:status='OBSERVED'
    return {'status':status,'level':price,'quote_at':at.isoformat() if at else None,'age_seconds':age,
        'previous_close':previous,'open':opening,
        'change_points':price-previous if price and previous and previous>0 else None,
        'change_fraction':price/previous-1 if price and previous and previous>0 else None,
        'change_from_open_fraction':price/opening-1 if price and opening and opening>0 else None}


def enabled(root,now):
    path=Path(root)/'research/spy_option_research/settings.json'
    if not path.exists():return False
    config=json.loads(path.read_text(encoding='utf-8-sig'))
    return config.get('enabled',False) and now.astimezone(ET).date().isoformat()>=config.get('start_date','9999-12-31')


def capture(root=ROOT,now=None,phase='SAMPLE',fetch=None):
    fixed=now is not None;now=now or datetime.now(timezone.utc)
    if not enabled(root,now):return {'status':'DISABLED'}
    bounds=session_bounds(now)
    if not bounds or not bounds[0]<=now<bounds[1]:return {'status':'OUTSIDE_SESSION'}
    db=connect(root)
    slot=int(now.timestamp()//300)
    try:
        if phase=='SAMPLE' and db.execute('select 1 from slots where slot=?',(slot,)).fetchone():
            return {'status':'ALREADY_SAMPLED'}
        if fetch is None:
            from schwab.market_data_client import get_option_quotes
            fetch=lambda symbols,timeout_seconds:get_option_quotes(symbols,timeout_seconds,cached_auth_only=True)
        error=None
        try:
            raw=fetch([VIX_SYMBOL,'SPY'],timeout_seconds=3)
            if not isinstance(raw,dict):raise ValueError('Invalid quotes')
        except Exception as exc:raw={};error=type(exc).__name__
        receipt=now if fixed else datetime.now(timezone.utc)
        receipt_bounds=session_bounds(receipt)
        if not receipt_bounds or not receipt_bounds[0]<=receipt<receipt_bounds[1]:return {'status':'OUTSIDE_SESSION_RECEIPT'}
        vix=normalize(raw.get(VIX_SYMBOL),receipt);spy=normalize(raw.get('SPY'),receipt)
        result={'id':uuid4().hex,'version':VERSION,'observed_at':receipt.isoformat(),'phase':phase,
            'vix':vix,'spy':spy,'error_type':error,'source':'SCHWAB_QUOTES',
            'status':'OBSERVED' if vix['status']==spy['status']=='OBSERVED' else 'UNAVAILABLE_OR_PARTIAL',
            'policy':'OBSERVATION_ONLY_NO_VIX_ALLOCATION_OR_EXIT_OVERRIDE','rates':{}}
        prior=[json.loads(p) for (p,) in db.execute('select payload from observations')]
        for minutes in (5,15,60):
            target=receipt-timedelta(minutes=minutes)
            # Nearest five-minute sample, within half a cadence; retain actual
            # elapsed time rather than labeling a three-minute move as five.
            # Every reference is genuinely in the past, never interpolation.
            candidates=[p for p in prior if abs((aware(p['observed_at'])-target).total_seconds())<=150
                and aware(p['observed_at'])<receipt
                and p['vix']['status']=='OBSERVED'
                and aware(p['observed_at']).astimezone(ET).date()==receipt.astimezone(ET).date()]
            previous=min(candidates,key=lambda p:abs((aware(p['observed_at'])-target).total_seconds())) if candidates else None
            result['rates'][str(minutes)+'m']={'change_points':vix['level']-previous['vix']['level'],
                'change_fraction':vix['level']/previous['vix']['level']-1,
                'points_per_minute':(vix['level']-previous['vix']['level'])/((receipt-aware(previous['observed_at'])).total_seconds()/60),
                'elapsed_seconds':(receipt-aware(previous['observed_at'])).total_seconds(),
                'reference_sample_id':previous['id']} if previous and vix['status']=='OBSERVED' else None
        with db:
            db.execute('BEGIN IMMEDIATE')
            if phase=='SAMPLE' and db.execute('select 1 from slots where slot=?',(slot,)).fetchone():return {'status':'ALREADY_SAMPLED'}
            db.execute('insert into observations values(?,?,?,?)',(result['id'],receipt.isoformat(),phase,json.dumps(result)))
            if phase=='SAMPLE':db.execute('insert into slots values(?,?)',(slot,result['id']))
        return result
    finally:db.close()


def bind_selection(context,root=ROOT):
    """Bind only a sample genuinely observed before the immutable selection."""
    if not context or not context.get('id'):return {'status':'NO_PREDECISION_CONTEXT'}
    db=connect(root)
    try:
        persisted=db.execute('select payload from observations where id=?',(context['id'],)).fetchone()
    finally:db.close()
    if not persisted:return {'status':'NO_PERSISTED_CONTEXT'}
    context=json.loads(persisted[0])
    at=aware(context['observed_at']);day=at.astimezone(ET).date().isoformat()
    path=Path(root)/'data/processed/spy_option_research/selections'/f'{day}.json'
    if not path.exists():return {'status':'SELECTION_NOT_CAPTURED'}
    raw=path.read_bytes();selection=json.loads(raw)
    selected=aware(selection['selected_at'])
    timely=timedelta(0)<=selected-at<=timedelta(seconds=120)
    result={'day':day,'selection_at':selected.isoformat(),'selection_path':str(path.relative_to(root)),
        'selection_sha256':hashlib.sha256(raw).hexdigest(),'context_sample_id':context['id'] if timely else None,
        'status':'AS_OF_CONTEXT' if timely and context['status']=='OBSERVED' else 'UNAVAILABLE_AS_OF_DECISION',
        'signal_direction':selection.get('signal',{}).get('Direction'),
        'candidate_actions':[{'recommendation_id':r.get('RecommendationID'),'action':r.get('action'),
            'allocation_decision':r.get('allocation_decision')} for r in selection.get('candidates',[])]}
    db=connect(root)
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('select payload from bindings where day=?',(day,)).fetchone()
            if previous:
                if json.loads(previous[0])['selection_sha256']!=result['selection_sha256']:raise ValueError('Immutable SPY selection changed')
                return {'status':'ALREADY_BOUND'}
            db.execute('insert into bindings values(?,?)',(day,json.dumps(result)))
        return result
    finally:db.close()


def report(root=ROOT,now=None):
    now=now or datetime.now(timezone.utc);path=Path(root)/DIRECTORY/'context.sqlite'
    result={'status':'NOT_STARTED','mode':'OBSERVATIONAL_SPY_VIX_CONTEXT','observations':0,'decisions':[],
        'note':'VIX is expected 30-day volatility, not SPY direction. No thresholds, optimization or trading override.'}
    if not path.exists():return result
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        db.execute('BEGIN')
        samples=[json.loads(p) for (p,) in db.execute('select payload from observations')]
        bindings=[json.loads(p) for (p,) in db.execute('select payload from bindings order by day')]
    finally:db.close()
    samples=[s for s in samples if aware(s['observed_at'])<=now]
    by_id={s['id']:s for s in samples}
    latest=max(samples,key=lambda s:aware(s['observed_at'])) if samples else None
    result.update(status='OBSERVING' if samples else 'NOT_STARTED',observations=len(samples),
        valid_observations=sum(s['status']=='OBSERVED' for s in samples),latest=latest)
    lots=[]
    ledger=Path(root)/'data/processed/spy_option_research/ledger.sqlite'
    if ledger.exists():
        db=sqlite3.connect(ledger.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            db.execute('BEGIN')
            row=db.execute('select payload from state where id=1').fetchone()
            if row:
                state=json.loads(row[0]);book=state['portfolios']['baseline']
                if not state.get('last_at') or aware(state['last_at'])<=now:
                    lots=list(book['lots'].values())
        finally:db.close()
    for b in bindings:
        if aware(b['selection_at'])>now:continue
        ids={a['recommendation_id'] for a in b['candidate_actions']}
        closed=[lot for lot in lots if lot.get('recommendation_id') in ids and lot.get('status')=='CLOSED']
        result['decisions'].append({**b,'context':by_id.get(b['context_sample_id']),
            'closed_trades':len(closed),'closed_net_pnl':sum(l.get('closed_net_pnl',0) for l in closed) if closed else None})
    return result


def markdown(value):
    lines=['### VIX context for SPY (observation only)','',f"Status: **{value['status']}**. {value['note']}"]
    if value['status']!='OBSERVING':
        return '\n'.join(lines+['No forward observations yet; earlier SPY decisions are not retrospectively labeled.'])
    latest=value.get('latest')
    if latest:
        lines+=['',f"Latest receipt: {latest['observed_at']}; VIX data {latest['vix']['status']}; SPY data {latest['spy']['status']}. Valid paired observations: {value['valid_observations']} / {value['observations']}."]
    lines+=['','| Decision date | VIX | VIX vs prior close | VIX approx 5m change | SPY vs prior close | Closed trades | Closed net P/L | Context |','|---|---:|---:|---:|---:|---:|---:|---|']
    def percent(x):return 'Unavailable' if x is None else f'{x:+.2%}'
    for b in value['decisions']:
        c=b.get('context') if b['status']=='AS_OF_CONTEXT' else None
        v=c['vix'] if c else {};s=c['spy'] if c else {};rate=(c.get('rates',{}).get('5m') or {}) if c else {}
        level=v.get('level')
        pnl=b.get('closed_net_pnl')
        rate_text=percent(rate.get('change_fraction'))
        if rate.get('elapsed_seconds') is not None:rate_text+=f" ({rate['elapsed_seconds']/60:.1f}m)"
        lines.append(f"| {b['day']} | {format(level,'.2f') if level is not None else 'Unavailable'} | {percent(v.get('change_fraction'))} | {rate_text} | {percent(s.get('change_fraction'))} | {b['closed_trades']} | {'Unavailable' if pnl is None else '$'+format(pnl,'.2f')} | {b['status']} |")
    lines+=['','Decision context must be captured before selection. VIX changes are changes in implied volatility, not stock returns. Missing/stale data is unavailable, not zero. Outcome comparisons by VIX conditions require matured trades and enough independent entry dates; no regime edge is claimed.']
    return '\n'.join(lines)


def publish(root=ROOT,now=None):
    value=report(root,now);directory=Path(root)/DIRECTORY;directory.mkdir(parents=True,exist_ok=True)
    for name,text in [('latest.json',json.dumps(value,indent=2)),('latest.md',markdown(value))]:
        target=directory/name;temporary=target.with_name(name+'.'+uuid4().hex+'.tmp')
        temporary.write_text(text,encoding='utf-8');temporary.replace(target)
    return value


if __name__=='__main__':
    print(json.dumps(publish(),indent=2))
