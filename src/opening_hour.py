"""Production entry confirmation using complete 09:30-10:30 ET minute bars.

Daily research is retained. Frozen shadow allocators never import this guard.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd
from intraday_option_paths import session_bounds

ROOT=Path(__file__).resolve().parent.parent
ET=ZoneInfo('America/New_York')
VERSION='OPENING-HOUR-ENTRY-2026-11-05-v1'
DIRECTORY=Path('data/processed/opening_hour')
MAX_CANDIDATES=30
MAX_HOLDINGS=10


def number(value):
    try:
        value=float(value)
        return value if math.isfinite(value) else None
    except (TypeError,ValueError):return None


def window(now):
    if now.tzinfo is None:raise ValueError('Aware decision timestamp required')
    bounds=session_bounds(now)
    if not bounds:return None
    start=bounds[0];end=start+timedelta(hours=1)
    if now<end or now>=bounds[1]:return None
    return start,end


def fetch_history(ticker,start,end,token):
    """Read-only request; preflight already renewed access. No shared refresh."""
    import requests
    response=requests.get('https://api.schwabapi.com/marketdata/v1/pricehistory',
        headers={'Authorization':'Bearer '+token},
        params={'symbol':ticker.replace('-','/'),'frequencyType':'minute','frequency':1,
            'startDate':int(start.timestamp()*1000),'endDate':int(end.timestamp()*1000),
            'needExtendedHoursData':'false'},timeout=3)
    response.raise_for_status()
    return response.json()


def summarize(payload,start,end):
    """Require all 60 distinct bars; 10:30 and later bars are excluded.

    Bar timestamps label interval starts; the 10:29 bar ends at 10:30.
    VWAP uses minute typical price, not exchange trade-by-trade VWAP.
    """
    expected=set(range(int(start.timestamp()//60),int(end.timestamp()//60)))
    rows={};invalid=0;duplicates=False
    for raw in payload.get('candles',[]):
        stamp=number(raw.get('datetime'))
        if stamp is None:invalid+=1;continue
        at=datetime.fromtimestamp(stamp/1000,timezone.utc)
        if not start<=at<end:continue
        slot=int(at.timestamp()//60)
        if at.second or at.microsecond:invalid+=1;continue
        if slot in rows:duplicates=True
        vals={k:number(raw.get(k)) for k in ('open','high','low','close','volume')}
        o,h,l,c,v=[vals[k] for k in ('open','high','low','close','volume')]
        if any(x is None for x in (o,h,l,c,v)) or min(o,h,l,c)<=0 or v<0 or h<max(o,l,c) or l>min(o,h,c):
            invalid+=1;continue
        rows[slot]={**vals,'datetime':at.isoformat()}
    missing=sorted(expected-set(rows))
    result={'status':'COMPLETE' if not missing and not invalid and not duplicates else 'INCOMPLETE',
        'bars':len(rows),'expected_bars':len(expected),'missing_bars':len(missing),
        'invalid_bars':invalid,'duplicate_bars':duplicates,
        'start':start.isoformat(),'end_exclusive':end.isoformat(),
        'last_bar_at':rows[max(rows)]['datetime'] if rows else None,
        'source':'SCHWAB_MINUTE_HISTORY','vwap_definition':'VOLUME_WEIGHTED_MINUTE_TYPICAL_PRICE'}
    if result['status']!='COMPLETE':return result
    ordered=[rows[k] for k in sorted(rows)];volume=sum(r['volume'] for r in ordered)
    if volume<=0:return {**result,'status':'NO_VALID_VOLUME'}
    opening=ordered[0]['open'];close=ordered[-1]['close']
    vwap=sum((r['high']+r['low']+r['close'])/3*r['volume'] for r in ordered)/volume
    result.update(open=opening,close=close,high=max(r['high'] for r in ordered),
        low=min(r['low'] for r in ordered),volume=volume,bar_vwap=vwap,
        return_from_open=close/opening-1,close_vs_bar_vwap=close/vwap-1)
    return result


def evaluate(summary,strategy,market):
    if summary.get('status')!='COMPLETE':return 'DATA_UNAVAILABLE','First-hour stock data incomplete or unavailable'
    if market.get('status')!='COMPLETE':return 'DATA_UNAVAILABLE','First-hour SPY context incomplete or unavailable'
    if strategy not in ('Long Call','Long Put'):return 'NOT_APPLICABLE','Not a directional long-option entry'
    sign=1 if strategy=='Long Call' else -1
    move=sign*summary['return_from_open'];vwap=sign*summary['close_vs_bar_vwap']
    if move<0 and vwap<0:
        return 'CONTRADICTED','First-hour stock move and price versus bar-VWAP both oppose the daily thesis'
    if move>0 and vwap>0:
        return 'CONFIRMED','First-hour stock move and price versus bar-VWAP support the daily thesis'
    return 'MIXED','First-hour confirmation is mixed or flat; original qualification and risk checks still apply'


def collect_context(candidates,positions,root=ROOT,now=None,fetch=None):
    fixed=now is not None;now=now or datetime.now(timezone.utc)
    bounds=window(now)
    pool=candidates[candidates.get('action',pd.Series(index=candidates.index,dtype=str)).eq('Evaluate Options')].copy()
    if 'earnings_status' in pool:
        pool=pool[pool.earnings_status.fillna('NOT_CHECKED').ne('NOT_CHECKED')]
    if 'portfolio_score' in pool:
        pool['_score']=pd.to_numeric(pool.portfolio_score,errors='coerce')
        pool=pool.sort_values(['_score','ticker'],ascending=[False,True])
    tickers=list(dict.fromkeys(str(t).upper() for t in pool.get('ticker',[])))[:MAX_CANDIDATES]
    held=list(dict.fromkeys(str(t).upper() for t in positions.get('ticker',[])))[:MAX_HOLDINGS]
    symbols=sorted(set(tickers+held+['SPY']))
    results={};raws={}
    if not bounds:
        results={s:{'status':'OPENING_WINDOW_NOT_READY_OR_SESSION_CLOSED'} for s in symbols}
    else:
        start,end=bounds
        if fetch is None:
            try:
                from schwab.market_token_manager import get_cached_access_token
                token=get_cached_access_token()
                fetch=lambda s,a,b:fetch_history(s,a,b,token)
            except Exception as exc:
                results={s:{'status':'AUTH_UNAVAILABLE','error_type':type(exc).__name__} for s in symbols}
        if fetch is not None:
            # <=41 symbols, <=8 concurrent requests, each <=3 sec, no retries.
            # Existing daily/option collectors continue to own OAuth refresh.
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures={executor.submit(fetch,s,start,end):s for s in symbols}
                for future in as_completed(futures):
                    symbol=futures[future]
                    try:
                        payload=future.result()
                        if not isinstance(payload,dict):raise ValueError('Invalid minute history')
                        results[symbol]=summarize(payload,start,end)
                        # Only public market candles enter the local archive.
                        raws[symbol]=payload.get('candles',[])
                    except Exception as exc:
                        results[symbol]={'status':'FETCH_FAILED','error_type':type(exc).__name__}
    receipt=now if fixed else datetime.now(timezone.utc)
    if bounds and window(receipt)!=bounds:
        results={s:{'status':'SESSION_CHANGED_DURING_REQUEST'} for s in symbols}
    market=results.get('SPY',{'status':'MISSING'})
    records={}
    for i,row in candidates.iterrows():
        strategy=row.get('option_strategy','')
        s=results.get(str(row.get('ticker','')).upper(),{'status':'OUTSIDE_BOUNDED_POOL'})
        status,reason=evaluate(s,strategy,market)
        if s.get('status')=='OUTSIDE_BOUNDED_POOL':
            status,reason='NOT_REVIEWED_POOL','Outside bounded first-hour entry review pool'
        records[i]={'summary':s,'status':status,'reason':reason,
                    'blocked':status in ('CONTRADICTED','DATA_UNAVAILABLE','NOT_REVIEWED_POOL') and row.get('action')=='Evaluate Options'}
    payload={'version':VERSION,'requested_at':now.isoformat(),'received_at':receipt.isoformat(),
        'window_start':bounds[0].isoformat() if bounds else None,'window_end':bounds[1].isoformat() if bounds else None,
        'candidate_tickers':tickers,'holding_tickers':held,'summaries':results,'candles':raws,
        'purpose':'PRODUCTION_ENTRY_CONFIRMATION_ONLY_NOT_DAILY_INDICATOR_REPLACEMENT',
        'policy_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    directory=Path(root)/DIRECTORY;directory.mkdir(parents=True,exist_ok=True)
    path=directory/(now.strftime('%Y%m%d_%H%M%S_')+uuid4().hex+'.json')
    encoded=json.dumps(payload,sort_keys=True,allow_nan=False)
    # Persist evidence before using it; atomic rename avoids partial archives.
    tmp=path.with_suffix('.tmp');tmp.write_text(encoded,encoding='utf-8');tmp.rename(path)
    return records,results,str(path.relative_to(root)),hashlib.sha256(encoded.encode()).hexdigest(),payload['policy_sha256']


def arbitrate_with_opening_hour(base,candidates,positions,account_nav,*,root=ROOT,now=None,fetch=None,**kwargs):
    records,summaries,evidence_path,evidence_hash,policy_hash=collect_context(candidates,positions,root,now,fetch)
    screened=candidates.copy(deep=True)
    blocked=[i for i,r in records.items() if r['blocked']]
    screened.loc[blocked,'action']='Watch'
    result=base(screened,positions.copy(deep=True),account_nav,**kwargs)
    market=summaries.get('SPY',{})
    for frame in (result.candidates,result.positions):
        frame['OpeningHourPolicyVersion']=VERSION
        frame['OpeningHourPolicySHA256']=policy_hash
        frame['OpeningHourEvidencePath']=evidence_path
        frame['OpeningHourEvidenceSHA256']=evidence_hash
        frame['OpeningHourSPYReturn']=market.get('return_from_open')
        frame['OpeningHourSPYStatus']=market.get('status')
    for name in ('OpeningHourStatus','OpeningHourReason','OpeningHourBlocked','OpeningHourOpen',
                 'OpeningHourClose','OpeningHourReturn','OpeningHourBarVWAP','OpeningHourCloseVsBarVWAP',
                 'OpeningHourBarCount','OpeningHourLastBarAt'):
        result.candidates[name]=pd.Series(None,index=result.candidates.index,dtype=object)
    for i,record in records.items():
        s=record['summary']
        result.candidates.at[i,'OpeningHourStatus']=record['status']
        result.candidates.at[i,'OpeningHourReason']=record['reason']
        result.candidates.at[i,'OpeningHourBlocked']=record['blocked']
        for field,value in [('Open',s.get('open')),('Close',s.get('close')),('Return',s.get('return_from_open')),
            ('BarVWAP',s.get('bar_vwap')),('CloseVsBarVWAP',s.get('close_vs_bar_vwap')),
            ('BarCount',s.get('bars')),('LastBarAt',s.get('last_bar_at'))]:
            result.candidates.at[i,'OpeningHour'+field]=value
        # Research eligibility remains unchanged for the frozen shadows.
        result.candidates.at[i,'action']=candidates.at[i,'action']
        if record['blocked']:
            result.candidates.at[i,'portfolio_action_reason']=record['reason']
    for i,row in result.positions.iterrows():
        summary=summaries.get(str(row.get('ticker','')).upper(),{'status':'OUTSIDE_BOUNDED_HOLDINGS'})
        result.positions.at[i,'OpeningHourStatus']=summary['status']
        result.positions.at[i,'OpeningHourReturn']=summary.get('return_from_open')
    print(f"First-hour entry review: {len(blocked)} deferred/contradicted candidates; evidence {evidence_path}")
    return result
