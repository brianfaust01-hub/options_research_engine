"""Isolated paired trade research. No portfolio, recommendation or broker writes.

Fixed-horizon executable-price studies, not funded portfolios or stop/target
simulations. Capture from the first future daily snapshot; never backfill fills.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
from uuid import uuid4
from zoneinfo import ZoneInfo
import pandas as pd
from option_observation_collector import number, normalize_quote, timestamp
from intraday_option_paths import session_bounds

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = Path('data/processed/structure_research')
SETTINGS = Path('research/structure_research/settings.json')
ET = ZoneInfo('America/New_York')


def aware(value):
    value = datetime.fromisoformat(str(value).replace('Z','+00:00'))
    return value.replace(tzinfo=ET).astimezone(timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def configuration(root):
    settings = json.loads((Path(root)/SETTINGS).read_text(encoding='utf-8-sig'))
    from importlib.metadata import version
    sources=''.join((Path(__file__).parent/name).read_text(encoding='utf-8-sig') for name in
                    ('structure_research.py','option_observation_collector.py','intraday_option_paths.py'))
    digest = hashlib.sha256((json.dumps(settings,sort_keys=True)+sources+sys.version+pd.__version__+version('pandas_market_calendars')).encode()).hexdigest()
    return settings, digest


def connect(root):
    path = Path(root)/DIRECTORY/'studies.sqlite'
    path.parent.mkdir(parents=True,exist_ok=True)
    db = sqlite3.connect(path,timeout=2)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS studies(id TEXT PRIMARY KEY, day TEXT, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS samples(study TEXT, slot INTEGER, at TEXT, payload TEXT, PRIMARY KEY(study,slot));
        CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY,at TEXT,payload TEXT);
        CREATE TABLE IF NOT EXISTS captures(day TEXT PRIMARY KEY,source_hash TEXT,payload TEXT);
    ''')
    return db


def symbol_key(symbol):
    return re.sub(r'\s+','',str(symbol)).upper()


def contract(row):
    symbol = str(row.get('contractSymbol',row.get('contract_symbol',''))).strip()
    match = re.fullmatch(r'[A-Z0-9./-]+\s*\d{6}([CP])\d{8}',symbol)
    expiry = str(row.get('Expiration',row.get('expiration','')))[:10]
    strike = number(row.get('strike'))
    if not match or not strike or not expiry:
        return None
    return {'symbol':symbol,'expiration':expiry,'strike':strike,'type':match[1],
            'delta':number(row.get('broker_delta')),'bid':number(row.get('bid')),
            'ask':number(row.get('ask')),'open_interest':number(row.get('openInterest'))}


def select_variants(row,settings,now):
    base = contract(row)
    if not base:
        return {},['MISSING_EXACT_BASE_CONTRACT']
    direction = 1 if row.get('option_strategy') == 'Long Call' else -1
    expected_type = 'C' if direction == 1 else 'P'
    if base['type'] != expected_type:
        return {},['CONTRACT_DIRECTION_MISMATCH']
    try:
        evidence = json.loads(row.get('selection_evidence_json') or '[]')
    except (ValueError,TypeError):
        evidence = []
    pool = []
    for item in evidence:
        c = contract(item)
        if not c or c['type'] != expected_type or symbol_key(c['symbol']) == symbol_key(base['symbol']):
            continue
        bid,ask,oi = c['bid'],c['ask'],c['open_interest']
        if bid is None or ask is None or bid<=0 or ask<bid or oi is None or oi<settings['min_selection_open_interest']:
            continue
        if (ask-bid)/((ask+bid)/2)>settings['max_selection_spread_pct']:
            continue
        if (datetime.fromisoformat(c['expiration']).date()-now.astimezone(ET).date()).days < 45:
            continue
        # Do not silently reuse contracts the existing selector rejected.
        if str(item.get('RejectionReason') or '').strip():
            continue
        pool.append(c)
    def leg(c,side):return {'symbol':c['symbol'],'side':side,'expiration':c['expiration'],'strike':c['strike'],'type':c['type']}
    variants = {'outright':{'legs':[leg(base,1)],'kind':'debit'}}
    missing = []
    same = [c for c in pool if c['expiration']==base['expiration']]
    high = [c for c in same if c['delta'] is not None and .55<=abs(c['delta'])<=.75
            and (base['delta'] is None or abs(c['delta'])>abs(base['delta']))]
    if high:
        chosen = min(high,key=lambda c:(abs(abs(c['delta'])-.65),c['symbol']))
        variants['higher_delta']={'legs':[leg(chosen,1)],'kind':'debit'}
    else:missing.append('HIGHER_DELTA_UNAVAILABLE')
    later = [c for c in pool if c['expiration']>base['expiration'] and c['delta'] is not None and base['delta'] is not None]
    if later:
        expiry = min(c['expiration'] for c in later)
        chosen = min((c for c in later if c['expiration']==expiry),key=lambda c:(abs(abs(c['delta'])-abs(base['delta'])),c['symbol']))
        variants['later_expiry']={'legs':[leg(chosen,1)],'kind':'debit'}
    else:missing.append('LATER_EXPIRY_UNAVAILABLE')
    further = [c for c in same if direction*(c['strike']-base['strike'])>0]
    if further:
        short = min(further,key=lambda c:(abs(c['strike']-base['strike']),c['symbol']))
        variants['debit_vertical']={'legs':[leg(base,1),leg(short,-1)],'kind':'debit',
                                    'width':abs(short['strike']-base['strike'])}
    else:missing.append('DEBIT_SHORT_LEG_UNAVAILABLE')
    if settings['credit_spreads_enabled']:
        # Opposite option type, same directional view: bullish put / bearish call.
        credit_pool = []
        for item in evidence:
            c = contract(item)
            if c and c['type'] != expected_type and c['expiration']==base['expiration']:
                credit_pool.append(c)
        # Standard selector evidence is one-sided. Never synthesize missing legs.
        eligible = [c for c in credit_pool if c['delta'] is not None and .20<=abs(c['delta'])<=.40
                    and c['bid'] and c['ask'] and c['ask']>=c['bid'] and c['open_interest'] is not None
                    and c['open_interest']>=settings['min_selection_open_interest']
                    and (c['ask']-c['bid'])/((c['ask']+c['bid'])/2)<=settings['max_selection_spread_pct']]
        if eligible:
            short = min(eligible,key=lambda c:(abs(abs(c['delta'])-.30),c['symbol']))
            wings = [c for c in eligible if direction*(short['strike']-c['strike'])>0]
            if wings:
                wing = min(wings,key=lambda c:(abs(c['strike']-short['strike']),c['symbol']))
                variants['credit_vertical']={'legs':[leg(wing,1),leg(short,-1)],'kind':'credit',
                                             'width':abs(wing['strike']-short['strike'])}
            else:missing.append('CREDIT_WING_UNAVAILABLE')
        else:missing.append('CREDIT_OPPOSITE_SIDE_EVIDENCE_UNAVAILABLE')
    return variants,missing


def due_date(now,sessions):
    import pandas_market_calendars as calendars
    schedule = calendars.get_calendar('NYSE').schedule(now.date(),now.date()+timedelta(days=40))
    future = schedule[schedule.index.date>now.astimezone(ET).date()]
    if len(future)<sessions:raise ValueError('Insufficient calendar')
    return future.iloc[sessions-1].market_close.to_pydatetime()-timedelta(minutes=5)


def fetch_chain(ticker):
    """Bounded, cached-authorization-only read; never print provider bodies."""
    import requests
    from schwab.market_token_manager import get_cached_access_token
    response=requests.get('https://api.schwabapi.com/marketdata/v1/chains',
        headers={'Authorization':'Bearer '+get_cached_access_token()},
        params={'symbol':ticker.replace('-','/'),'contractType':'ALL','strategy':'SINGLE'},timeout=5)
    response.raise_for_status()
    return response.json()


def chain_evidence(chain):
    """Persist only contract selection fields, not account/provider metadata."""
    rows=[]
    for side in ('callExpDateMap','putExpDateMap'):
        for expiry,strikes in chain.get(side,{}).items():
            for contracts in strikes.values():
                for c in contracts:
                    if c.get('nonStandard') is True:continue
                    if c.get('multiplier',100)!=100:continue
                    rows.append({'contractSymbol':c.get('symbol'), 'Expiration':expiry.split(':')[0],
                        'strike':number(c.get('strikePrice')),'bid':number(c.get('bid')),'ask':number(c.get('ask')),
                        'openInterest':number(c.get('openInterest')),'broker_delta':number(c.get('delta'))})
    return rows


def capture(source,root=ROOT,now=None,preview=False,chain_fetch=None):
    fixed=now is not None
    now = now or datetime.now(timezone.utc)
    settings,fp = configuration(root)
    if not settings['enabled']:return {'status':'DISABLED'}
    source=Path(source);frame=pd.read_csv(source,low_memory=False).fillna('')
    day=now.astimezone(ET).date().isoformat()
    if not preview:
        bounds=session_bounds(now)
        if not bounds or not bounds[0]<=now<bounds[1]:return {'status':'OUTSIDE_SESSION'}
        dates=frame.RecommendationDate.map(aware)
        if not all(d.astimezone(ET).date().isoformat()==day and timedelta(0)<=now-d<=timedelta(minutes=20) for d in dates):
            raise ValueError('Only fresh same-session committed recommendations allowed')
        ids=frame.RecommendationID.astype(str)
        if ids.eq('').any() or ids.duplicated().any():raise ValueError('Unique recommendation IDs required')
        existing=Path(root)/DIRECTORY/'studies.sqlite'
        if existing.exists():
            db=sqlite3.connect(existing.resolve().as_uri()+'?mode=ro',uri=True)
            try:
                if db.execute('select 1 from captures where day=?',(day,)).fetchone():return {'status':'ALREADY_CAPTURED','day':day}
            finally:db.close()
    eligible=frame[frame.allocation_decision.eq('Allocate') & frame.option_strategy.isin(['Long Call','Long Put'])].copy()
    eligible['_rank']=pd.to_numeric(eligible.get('portfolio_forward_score',eligible.get('allocation_score')),errors='coerce')
    eligible=eligible.sort_values(['_rank','ticker'],ascending=[False,True]).drop_duplicates('ticker').head(settings['max_signals_per_session'])
    studies=[]
    for _,row in eligible.iterrows():
        row=row.to_dict();evidence_status='SAVED_METADATA_ONLY_NO_NEW_MARKET_DATA'
        evidence=[]
        if not preview:
            try:
                evidence=chain_evidence((chain_fetch or fetch_chain)(str(row['ticker'])))
                row['selection_evidence_json']=json.dumps(evidence)
                evidence_status='FORWARD_CHAIN_REFERENCE_NOT_FILL'
            except Exception as exc:
                row['selection_evidence_json']='[]'
                evidence_status='CHAIN_FETCH_FAILED_'+type(exc).__name__
        selected_at=now if fixed else datetime.now(timezone.utc)
        variants,missing=select_variants(row,settings,selected_at)
        if not variants:continue
        rid=str(row['RecommendationID'])
        studies.append({'id':hashlib.sha256((rid+fp).encode()).hexdigest()[:24],
            'recommendation_id':rid,'ticker':str(row['ticker']),'direction':1 if row['option_strategy']=='Long Call' else -1,
            'source_name':source.name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'source_policy_fingerprint':str(row.get('PolicyEvidenceFingerprint','')),
            'production_risk_version':str(row.get('ProductionRiskPolicyVersion','')),
            'policy_fingerprint':fp,'settings':settings,'decided_at':selected_at.isoformat(),
            'selection_evidence_status':evidence_status,'selection_contracts':evidence,
            'entry_deadline':(selected_at+timedelta(minutes=settings['entry_wait_minutes'])).isoformat(),
            'due_at':due_date(selected_at,settings['holding_sessions']).isoformat(),
            'variants':variants,'unavailable':missing,'state':'WAITING','last_sample_at':None,
            'stock_definition':'Direction-adjusted underlying price return; bearish is diagnostic, not a funded short sale; no borrow/dividend model.'})
    result={'status':'PREVIEW_NOT_STARTED' if preview else 'CAPTURED','day':day,'studies':studies,
            'credit_status':'ENABLED' if settings['credit_spreads_enabled'] else 'STAGED_DISABLED'}
    if preview:return result
    committed_at=now if fixed else datetime.now(timezone.utc)
    bounds=session_bounds(committed_at)
    if not bounds or not bounds[0]<=committed_at<bounds[1]:return {'status':'OUTSIDE_SESSION_COMMIT'}
    # A family cannot use observations preceding the durable capture batch.
    for study in studies:
        study['decided_at']=committed_at.isoformat()
        study['entry_deadline']=(committed_at+timedelta(minutes=settings['entry_wait_minutes'])).isoformat()
    db=connect(root)
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('select 1 from captures where day=?',(day,)).fetchone():return {'status':'ALREADY_CAPTURED','day':day}
            for study in studies:db.execute('insert into studies values(?,?,?)',(study['id'],day,json.dumps(study)))
            db.execute('insert into captures values(?,?,?)',(day,hashlib.sha256(source.read_bytes()).hexdigest(),json.dumps(result)))
    finally:db.close()
    return {'status':'CAPTURED','day':day,'studies':len(studies),'credit_status':result['credit_status']}


def valid_quote(raw,now,decided,settings):
    q=normalize_quote(raw,now)
    at=timestamp(q.get('quote_at'))
    if q['quote_status']!='OBSERVED' or at is None or not decided<=at<=now or (now-at).total_seconds()>settings['max_quote_age_seconds'] or not q['bid']:
        return None
    return q


def entry_variant(variant,quotes,settings):
    fee=settings['fee_per_contract_per_side']*len(variant['legs'])
    slip=settings['slippage_per_share_per_leg']
    premium=sum(l['side']*(quotes[l['symbol']]['ask']+slip if l['side']==1 else quotes[l['symbol']]['bid']-slip) for l in variant['legs'])
    width=variant.get('width')
    if variant['kind']=='debit':
        if premium<=0 or (width and premium>=width):return {'status':'INVALID_EXECUTABLE_DEBIT'}
        risk=premium*100+2*fee
    else:
        if premium>=0 or -premium>=width:return {'status':'INVALID_EXECUTABLE_CREDIT'}
        risk=(width+premium)*100+2*fee
    quantity=math.floor(settings['max_risk_dollars_per_variant']/risk)
    if quantity<=0:return {'status':'UNAFFORDABLE'}
    return {'status':'OPEN','quantity':quantity,'entry_premium':premium,'entry_fee':fee*quantity,
            'roundtrip_fees':2*fee*quantity,'max_loss_including_fees':risk*quantity,
            'entry_net_debit':premium*100*quantity+fee*quantity,'worst_sampled_net_pnl':-2*fee*quantity}


def advance(study,raw,now):
    """A synchronized family observation; absent legs never become fake fills."""
    settings=study['settings'];decided=aware(study['decided_at']);due=aware(study['due_at'])
    symbols={study['ticker']} | {l['symbol'] for v in study['variants'].values() for l in v['legs']}
    qs={s:valid_quote(raw.get(s),now,decided,settings) for s in symbols}
    missing=[s for s,q in qs.items() if q is None]
    sample={'at':now.isoformat(),'missing_symbols':missing,'status':'UNUSABLE' if missing else 'USABLE'}
    if study['last_sample_at'] and now<=aware(study['last_sample_at']):
        return {**sample,'status':'OUT_OF_ORDER_IGNORED'}
    study['last_sample_at']=now.isoformat()
    if study['state']=='WAITING' and (now>aware(study['entry_deadline']) or now.astimezone(ET).date()!=decided.astimezone(ET).date()):
        study['state']='ENTRY_WINDOW_MISSED';return {**sample,'status':'ENTRY_WINDOW_MISSED'}
    if now>due+timedelta(minutes=5):
        study['state']='EXIT_WINDOW_MISSED';return {**sample,'status':'EXIT_WINDOW_MISSED'}
    if missing:return sample
    times=[timestamp(q['quote_at']) for q in qs.values()]
    if (max(times)-min(times)).total_seconds()>settings['max_leg_timestamp_skew_seconds']:
        sample['status']='LEG_TIMESTAMP_SKEW';return sample
    if study['state']=='WAITING':
        study['entered_at']=now.isoformat();study['stock_entry_mid']=(qs[study['ticker']]['bid']+qs[study['ticker']]['ask'])/2
        study['stock_entry_bid']=qs[study['ticker']]['bid'];study['stock_entry_ask']=qs[study['ticker']]['ask']
        for v in study['variants'].values():v.update(entry_variant(v,qs,settings))
        study['state']='OPEN'
    stock=qs[study['ticker']]
    study['stock_directional_mid_return']=study['direction']*((stock['bid']+stock['ask'])/2/study['stock_entry_mid']-1)
    # Bid/ask-aware diagnostic price move, not a short-stock portfolio return.
    study['stock_executable_directional_return']=(stock['bid']/study['stock_entry_ask']-1 if study['direction']==1 else
        (study['stock_entry_bid']-stock['ask'])/study['stock_entry_bid'])
    slip=settings['slippage_per_share_per_leg']
    for name,v in study['variants'].items():
        if v.get('status')!='OPEN':continue
        exit_value=sum(l['side']*(qs[l['symbol']]['bid']-slip if l['side']==1 else qs[l['symbol']]['ask']+slip) for l in v['legs'])
        # Negative bids or vertical prices outside width are unusable, never clamped into a fill.
        if any(qs[l['symbol']]['bid']<=slip for l in v['legs'] if l['side']==1):
            sample['status']='UNUSABLE_EXECUTABLE_EXIT';continue
        width=v.get('width')
        if width and (exit_value<0 if v['kind']=='debit' else exit_value>0) :
            sample['status']='INVALID_VERTICAL_EXIT';continue
        if width and abs(exit_value)>width:
            sample['status']='INVALID_VERTICAL_EXIT';continue
        pnl=(exit_value-v['entry_premium'])*100*v['quantity']-v['roundtrip_fees']
        v.update(net_pnl=pnl,return_on_max_loss=pnl/v['max_loss_including_fees'],
                 return_on_risk_budget=pnl/settings['max_risk_dollars_per_variant'],marked_at=now.isoformat())
        v['worst_sampled_net_pnl']=min(v['worst_sampled_net_pnl'],pnl)
        if now>=due:v.update(status='CLOSED',closed_at=now.isoformat(),exit_premium=exit_value)
    if now>=due and all(v.get('status')!='OPEN' for v in study['variants'].values()):study['state']='CLOSED'
    sample['variant_pnl']={n:v.get('net_pnl') for n,v in study['variants'].items()}
    sample['quote_times']={s:q['quote_at'] for s,q in qs.items()}
    return sample


def collect(root=ROOT,now=None,fetch=None):
    fixed=now is not None;now=now or datetime.now(timezone.utc)
    bounds=session_bounds(now)
    if not bounds or not bounds[0]<=now<bounds[1]:return {'status':'OUTSIDE_SESSION'}
    settings,fp=configuration(root)
    if not settings['enabled']:return {'status':'DISABLED'}
    if not (Path(root)/DIRECTORY/'studies.sqlite').exists():return {'status':'NOT_STARTED'}
    db=connect(root)
    try:
        studies=[json.loads(p) for (p,) in db.execute('select payload from studies')]
        active=sorted((s for s in studies if s['state'] in ('WAITING','OPEN')),key=lambda s:(s['last_sample_at'] or '',s['id']))
        if any(s['policy_fingerprint']!=fp for s in active):raise ValueError('Active research policy changed; review/version separately')
        selected=[];symbols=set()
        for s in active:
            extra={s['ticker']} | {l['symbol'] for v in s['variants'].values() for l in v['legs']}
            if len(symbols|extra)>50:continue
            selected.append(s['id']);symbols|=extra
        if not selected:return {'status':'NO_ACTIVE_STUDIES'}
        if fetch is None:
            from schwab.market_data_client import get_option_quotes
            def fetch(syms,timeout_seconds):
                aliases={s:(s.replace('-','/') if s in {study['ticker'] for study in active} else s) for s in syms}
                response=get_option_quotes(list(aliases.values()),timeout_seconds,cached_auth_only=True)
                return {s:response.get(alias) for s,alias in aliases.items()}
        error=None
        try:raw=fetch(sorted(symbols),timeout_seconds=4)
        except Exception as exc:raw={};error=type(exc).__name__
        receipt=now if fixed else datetime.now(timezone.utc)
        if not bounds[0]<=receipt<bounds[1]:return {'status':'OUTSIDE_SESSION_RECEIPT'}
        raw=raw if isinstance(raw,dict) else {}
        slot=int(receipt.timestamp()//60);counts={}
        with db:
            db.execute('BEGIN IMMEDIATE')
            batch_id=uuid4().hex
            db.execute('insert into batches values(?,?,?)',(batch_id,receipt.isoformat(),json.dumps({
                'symbols':sorted(symbols),'error_type':error,'quotes':{s:normalize_quote(raw.get(s),receipt) for s in symbols}})))
            for sid in selected:
                if db.execute('select 1 from samples where study=? and slot=?',(sid,slot)).fetchone():continue
                s=json.loads(db.execute('select payload from studies where id=?',(sid,)).fetchone()[0])
                if s['state'] not in ('WAITING','OPEN'):continue
                sample=advance(s,raw,receipt)
                sample['batch_id']=batch_id
                db.execute('insert into samples values(?,?,?,?)',(sid,slot,receipt.isoformat(),json.dumps(sample)))
                db.execute('update studies set payload=? where id=?',(json.dumps(s),sid))
                counts[sample['status']]=counts.get(sample['status'],0)+1
        return {'status':'UPDATED' if error is None else 'FETCH_FAILED','at':receipt.isoformat(),'samples':counts,
                'not_sampled_budget':len(active)-len(selected)}
    finally:db.close()


def report(root=ROOT,now=None):
    now=now or datetime.now(timezone.utc);path=Path(root)/DIRECTORY/'studies.sqlite'
    result={'status':'NOT_STARTED','as_of':now.isoformat(),'mode':'PAIRED_FIXED_HORIZON_RESEARCH_NOT_FUNDED_PORTFOLIOS',
            'variants':{},'paired_differences':{},'studies':[],'credit_status':'STAGED_DISABLED'}
    if not path.exists():return result
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        db.execute('BEGIN')
        studies=[json.loads(p) for (p,) in db.execute('select payload from studies order by day,id')]
        samples=[(sid,json.loads(p)) for sid,p in db.execute('select study,payload from samples')]
    finally:db.close()
    config,current_fp=configuration(root)
    result['credit_status']='ENABLED' if config['credit_spreads_enabled'] else 'STAGED_DISABLED'
    all_studies=studies
    studies=[s for s in all_studies if s['policy_fingerprint']==current_fp and aware(s['decided_at'])<=now]
    current_ids={s['id'] for s in studies}
    by_study={sid:[p for s,p in samples if s==sid and aware(p['at'])<=now] for sid in current_ids}
    samples=[p for sid,p in samples if sid in current_ids and aware(p['at'])<=now]
    result['policy_fingerprint']=current_fp
    result['archived_other_policy_studies']=[s['id'] for s in all_studies if s['policy_fingerprint']!=current_fp]
    result['coverage']=[]
    if studies:
        import pandas_market_calendars as calendars
        schedule=calendars.get_calendar('NYSE').schedule(min(aware(s['decided_at']).date() for s in studies),now.date())
        for s in studies:
            begin=aware(s['decided_at']);end=min(now,aware(s['due_at'])+timedelta(minutes=5))
            if s['state']=='ENTRY_WINDOW_MISSED':end=min(end,aware(s['entry_deadline']))
            if s['state']=='CLOSED':end=min(end,max(aware(v['closed_at']) for v in s['variants'].values() if v.get('closed_at')))
            expected=set()
            for _,session in schedule.iterrows():
                left=max(begin,session.market_open.to_pydatetime());right=min(end,session.market_close.to_pydatetime())
                if left<right:expected.update(range(int(left.timestamp()//60),int(right.timestamp()//60)))
            observed={int(aware(p['at']).timestamp()//60) for p in by_study[s['id']]}
            usable={int(aware(p['at']).timestamp()//60) for p in by_study[s['id']] if p['status']=='USABLE'}
            result['coverage'].append({'study':s['id'],'expected_elapsed_market_minutes':len(expected),
                'sampled_elapsed_minutes':len(expected & observed),'usable_elapsed_minutes':len(expected & usable),
                'absent_elapsed_minutes':len(expected-observed)})
    result.update(status='COLLECTING' if studies else 'NO_ELIGIBLE_SIGNALS',studies=studies,
        last_sample_at=max((s['last_sample_at'] for s in studies if s['last_sample_at']),default=None),
        sample_count=len(samples),unusable_samples=sum(s['status']!='USABLE' for s in samples),
        completed_families=sum(s['state']=='CLOSED' for s in studies),
        open_families=sum(s['state']=='OPEN' for s in studies))
    result['family_states']=dict(Counter(s['state'] for s in studies))
    result['unavailable_reasons']=dict(Counter(reason for s in studies for reason in s.get('unavailable',[])))
    result['variant_states']=dict(Counter(v.get('status','NOT_ENTERED') for s in studies for v in s['variants'].values()))
    closed_stock=[s['stock_executable_directional_return'] for s in studies if s['state']=='CLOSED']
    result['underlying_diagnostic']={'closed_families':len(closed_stock),
        'mean_directional_bid_ask_return':sum(closed_stock)/len(closed_stock) if closed_stock else None,
        'positive_fraction':sum(r>0 for r in closed_stock)/len(closed_stock) if closed_stock else None}
    for name in ('outright','higher_delta','later_expiry','debit_vertical','credit_vertical'):
        closed=[s['variants'][name] for s in studies if name in s['variants'] and s['variants'][name].get('status')=='CLOSED']
        result['variants'][name]={'closed':len(closed),'net_pnl':sum(v['net_pnl'] for v in closed),
            'mean_return_on_max_loss':sum(v['return_on_max_loss'] for v in closed)/len(closed) if closed else None}
        pairs=[s for s in studies if s['state']=='CLOSED' and name in s['variants'] and
               s['variants'][name].get('status')=='CLOSED' and s['variants']['outright'].get('status')=='CLOSED' and
               s['variants'][name]['closed_at']==s['variants']['outright']['closed_at']]
        result['paired_differences'][name]={'matched_families':len(pairs),'net_pnl_difference':sum(s['variants'][name]['net_pnl']-s['variants']['outright']['net_pnl'] for s in pairs)}
    return result


def markdown(value):
    lines=['## Signal and option-structure research','',f"Status: **{value['status']}**.",
        '', 'Separate fixed-five-session paired trade studies, not portfolio returns. No broker orders. Credit status: '+value.get('credit_status','STAGED_DISABLED')+'.',
        'Underlying direction is a diagnostic benchmark, not a funded bearish stock strategy. Prices and fills begin prospectively; no historical spread returns are inferred.']
    if value['status'] not in ('COLLECTING','NO_ELIGIBLE_SIGNALS'):return '\n'.join(lines)
    lines+=['',f"Families: {len(value['studies'])}; completed {value['completed_families']}; open {value['open_families']}. Last sample: {value['last_sample_at']}. Unusable samples: {value['unusable_samples']} / {value['sample_count']}.",
            '', '| Variant | Closed trades | Net P/L | Matched vs outright | Paired dollar difference |','|---|---:|---:|---:|---:|']
    for name,v in value['variants'].items():
        p=value['paired_differences'][name]
        lines.append(f"| {name} | {v['closed']} | {'$'+format(v['net_pnl'],'.2f') if v['closed'] else 'Unavailable'} | {p['matched_families']} | {'$'+format(p['net_pnl_difference'],'.2f') if p['matched_families'] else 'Unavailable'} |")
    stock=value['underlying_diagnostic']
    if stock['closed_families']:
        lines+=['',f"Underlying diagnostic: {stock['closed_families']} completed families; mean direction-adjusted bid/ask price return {stock['mean_directional_bid_ask_return']:.2%}. No short borrow/dividend costs modeled."]
    lines+=['',f"Coverage across current-policy families: {sum(c['expected_elapsed_market_minutes'] for c in value['coverage'])} expected elapsed market minutes; {sum(c['absent_elapsed_minutes'] for c in value['coverage'])} absent minutes. Scheduled samples are not continuous market coverage."]
    lines+=['',f"Family states: {value['family_states']}. Variant states: {value['variant_states']}. Unavailable alternatives: {value['unavailable_reasons']}. Other-policy families excluded: {len(value['archived_other_policy_studies'])}."]
    lines+=['','Option sizes use a $1,000 maximum-loss budget per variant, integer contracts, fees and adverse slippage. Dollar totals are independent research trades, not a cash-constrained account. Missing legs, stale quotes, unaffordable variants, missed entry/exit windows and between-sample moves limit conclusions. No automatic promotion.']
    return '\n'.join(lines)


def publish_report(root):
    value=report(root);directory=Path(root)/DIRECTORY;directory.mkdir(parents=True,exist_ok=True)
    for name,payload in [('latest.json',json.dumps(value,indent=2)),('latest.md',markdown(value))]:
        path=directory/name;temporary=path.with_name(name+'.'+uuid4().hex+'.tmp')
        temporary.write_text(payload,encoding='utf-8');temporary.replace(path)
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['capture','collect','report','preview'])
    parser.add_argument('--source',type=Path)
    parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    try:
        if args.command in ('capture','preview'):
            if args.source is None:raise ValueError('Source required')
            value=capture(args.source,args.root,preview=args.command=='preview')
            if args.command=='capture':publish_report(args.root)
            print(json.dumps(value));return
        if args.command=='collect':
            value=collect(args.root);publish_report(args.root);print(json.dumps(value));return
        value=publish_report(args.root)
        print(json.dumps({k:v for k,v in value.items() if k!='studies'}))
    except Exception as exc:
        print(json.dumps({'status':'FAILED','error_type':type(exc).__name__}))
        raise SystemExit(1)


if __name__=='__main__':main()
