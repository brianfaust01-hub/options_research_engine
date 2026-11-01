"""Independent, quote-driven control/challenger paper accounts. No broker orders.

Inputs/events are immutable SQLite records. State, cash and fills commit together.
All times are timezone-aware; fills occur only after recorded decision availability.
"""
from __future__ import annotations
import hashlib
import json
import math
import sqlite3
from functools import lru_cache
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

ET=ZoneInfo('America/New_York')
VERSION='OPTION-CONFIG-COMPARISON-2026-10-29-v1'
POLICIES=('baseline','moderate_delta_iv')


def aware(value):
    d=datetime.fromisoformat(str(value).replace('Z','+00:00')) if not isinstance(value,datetime) else value
    if d.tzinfo is None:raise ValueError('Explicit timezone required')
    return d.astimezone(timezone.utc)


def number(value,default=None):
    try:n=float(value)
    except (TypeError,ValueError):return default
    return n if math.isfinite(n) else default


def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if hasattr(value,'item'):return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def encode(value):return json.dumps(clean(value),sort_keys=True,separators=(',',':'),allow_nan=False)


def symbol(value):return ''.join(str(value).split())


@lru_cache(maxsize=256)
def session_intervals(first,last):
    import pandas_market_calendars as calendars
    schedule=calendars.get_calendar('NYSE').schedule(first,last)
    return tuple((r.market_open.to_pydatetime(),r.market_close.to_pydatetime()) for _,r in schedule.iterrows())


def trading_gap_seconds(start,end):
    start=aware(start);end=aware(end)
    return sum(max(0.,(min(closing,end)-max(opening,start)).total_seconds()) for opening,closing in session_intervals(str(start.astimezone(ET).date()),str(end.astimezone(ET).date())))


def validate_daily_input(candidates,at):
    from intraday_option_paths import session_bounds
    at=aware(at);bounds=session_bounds(at)
    if not bounds or not bounds[0]<=at<bounds[1]:raise ValueError('Daily decision requires an open regular session')
    if candidates.empty or not {'RecommendationDate','RecommendationID'}.issubset(candidates):raise ValueError('Candidate snapshot schema is incomplete')
    parsed=[]
    for value in candidates.RecommendationDate:
        d=pd.Timestamp(value)
        if pd.isna(d):raise ValueError('Candidate decision timestamp is missing')
        parsed.append(d.tz_localize(ET) if d.tzinfo is None else d)
    if any(d.tz_convert(ET).date()!=at.astimezone(ET).date() for d in parsed):raise ValueError('Candidate snapshot mixes session dates')
    newest=max(parsed)
    if newest>pd.Timestamp(at) or pd.Timestamp(at)-newest>pd.Timedelta(minutes=30):raise ValueError('Missing, future or stale candidate set')
    if candidates.RecommendationID.isna().any() or candidates.RecommendationID.duplicated().any():raise ValueError('Missing or duplicate recommendation IDs')
    return bounds


class ComparisonLedger:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,timeout=20)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS inputs(kind TEXT,key TEXT,payload TEXT,PRIMARY KEY(kind,key));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at TEXT,portfolio TEXT,kind TEXT,payload TEXT);
            CREATE TABLE IF NOT EXISTS coverage(symbol TEXT,day TEXT,slot INTEGER,PRIMARY KEY(symbol,slot));
            CREATE TABLE IF NOT EXISTS pending_daily(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT);
            CREATE TABLE IF NOT EXISTS valuations(id INTEGER PRIMARY KEY,at TEXT,source TEXT,portfolio TEXT,payload TEXT,UNIQUE(source,portfolio));
        ''')
        self.db.commit()

    def close(self):self.db.close()
    def load(self):
        r=self.db.execute('SELECT payload FROM state WHERE id=1').fetchone()
        if not r:raise ValueError('Comparison has not been initialized')
        return json.loads(r[0])
    def save(self,s):self.db.execute('INSERT OR REPLACE INTO state VALUES(1,?)',(encode(s),))
    def event(self,at,portfolio,kind,**payload):
        self.db.execute('INSERT INTO events(at,portfolio,kind,payload) VALUES(?,?,?,?)',(aware(at).isoformat(),portfolio,kind,encode(payload)))
    def input(self,kind,key,payload):
        text=encode(payload);prior=self.db.execute('SELECT payload FROM inputs WHERE kind=? AND key=?',(kind,key)).fetchone()
        if prior:
            if prior[0]!=text:raise ValueError('Immutable comparison input changed: '+key)
            return False
        self.db.execute('INSERT INTO inputs VALUES(?,?,?)',(kind,key,text));return True

    def initialize(self,at,*,capital=15000,fee_per_contract=.70,market_slippage=.01,fingerprint='fixture',mode='FORWARD_SHADOW',portfolio_names=None):
        at=aware(at)
        if capital<=0 or fee_per_contract<0 or market_slippage<0:raise ValueError('Invalid accounting assumptions')
        if self.db.execute('SELECT 1 FROM state').fetchone():raise ValueError('Never reset an existing comparison')
        names=tuple(POLICIES if portfolio_names is None else portfolio_names)
        if not names or len(set(names))!=len(names) or not set(names).issubset(POLICIES):raise ValueError('Invalid portfolio names')
        portfolio=lambda:{'cash':float(capital),'realized_net':0.,'fees':0.,'lots':{},'orders':{},'peak_nav':float(capital),'max_drawdown':0.,'traded_premium':0.}
        s={'version':VERSION,'mode':mode,'started_at':at.isoformat(),'last_at':at.isoformat(),'capital':float(capital),'fee':fee_per_contract,'slippage':market_slippage,'fingerprint':fingerprint,'marks':{},'portfolios':{p:portfolio() for p in names},'health':{'invalid_quotes':0,'missing_quotes':0,'late_bundles':0,'intraday_gaps':0,'max_gap_seconds':0,'zero_bid_observations':0}}
        with self.db:self.event(at,'BOTH','INITIALIZED',capital=capital,fee=fee_per_contract,slippage=market_slippage,fingerprint=fingerprint,mode=mode);self.save(s)

    def check(self,s,at,fingerprint):
        if fingerprint!=s['fingerprint']:raise ValueError('Frozen policy source changed; new version/review required')
        if aware(at)<aware(s['last_at']):raise ValueError('Cannot process decisions or quotes backwards in time')

    def expire(self,s,at):
        for name,p in s['portfolios'].items():
            for oid,o in p['orders'].items():
                if o['status']=='PENDING' and o['side']=='BUY' and aware(at)>=aware(o['expires_at']):
                    o['status']='EXPIRED_NO_FILL_OBSERVED';self.event(at,name,'ORDER_EXPIRED',order_id=oid,symbol=o['symbol'],classification='NO_GUARANTEED_FILL_IN_UNOBSERVED_INTERVALS')

    def pending_reserve(self,s,p):
        return sum((o['limit']*100+2*s['fee'])*o['quantity'] for o in p['orders'].values() if o['status']=='PENDING' and o['side']=='BUY' and o.get('funding_status','RESERVED')=='RESERVED')

    def exit_fee_reserve(self,s,p):
        return sum(l['quantity']*s['fee'] for l in p['lots'].values() if l['status']=='OPEN')

    def watch(self,s=None):
        s=s or self.load();found={}
        for p in s['portfolios'].values():
            for o in list(p['orders'].values())+list(p['lots'].values()):
                if o.get('status') in {'PENDING','OPEN'}:
                    found[o['symbol']]={'contract_symbol':o['raw_symbol'],'ticker':o['ticker'],'expiration':o['expiration'],'strategy':o['strategy'],'recommendations':[]}
        return found

    def snapshot(self,s=None,at=None):
        s=s or self.load();at=aware(at or s['last_at']);result={}
        for name,p in s['portfolios'].items():
            market=liquidation=unrealized=entry_debits=0.;stale=[];positions=[];settlements=[]
            for lid,l in p['lots'].items():
                if l['status']!='OPEN':continue
                if at.astimezone(ET).date()>datetime.fromisoformat(l['expiration']).date():settlements.append(l['symbol'])
                mark=s['marks'].get(l['symbol']);fresh=mark and 0<=(at-aware(mark['at'])).total_seconds()<=90
                if not fresh:stale.append(l['symbol'])
                mid=mark['mark'] if mark else l['entry'];bid=mark['bid'] if mark else l['entry']
                qty=l['quantity'];entry_debits+=(l['entry']*100+s['fee'])*qty;market+=mid*100*qty;liquidation+=(max(0,bid-s['slippage'])*100-s['fee'])*qty
                unrealized+=(mid-l['entry'])*100*qty-s['fee']*qty
                positions.append({**l,'position_id':lid,'mark':mid,'mark_at':mark['at'] if mark else None,'mark_stale':not fresh})
            nav=p['cash']+market;peak=max(p['peak_nav'],nav)
            closed=[l for l in p['lots'].values() if l['status']=='CLOSED'];wins=sum(l.get('closed_net_pnl',0)>0 for l in closed)
            gains=sum(max(0,l.get('closed_net_pnl',0)) for l in closed);losses=-sum(min(0,l.get('closed_net_pnl',0)) for l in closed)
            result[name]={'cash':p['cash'],'option_market_value':market,'nav':nav,'liquidation_nav':p['cash']+liquidation,'realized_net_pnl':p['realized_net'],'unrealized_net_pnl':unrealized,'total_net_pnl':nav-s['capital'],'return_on_initial_capital':nav/s['capital']-1,'fees_paid':p['fees'],'open_entry_debits':entry_debits,'closed_round_trips':len(closed),'closed_trade_win_rate':wins/len(closed) if closed else None,'closed_trade_profit_factor':gains/losses if losses else None,'gross_turnover_on_initial_capital':p['traded_premium']/s['capital'],'reserved_for_entries':self.pending_reserve(s,p),'reserved_for_open_exit_fees':self.exit_fee_reserve(s,p),'stale_or_missing_marks':stale,'settlement_required':settlements,'positions':positions,'peak_nav':peak,'max_drawdown':max(p['max_drawdown'],1-nav/peak),'traded_premium':p['traded_premium'],'pending_orders':[dict(o,order_id=k) for k,o in p['orders'].items() if o['status']=='PENDING']}
            if abs((p['realized_net']+unrealized)-(nav-s['capital']))>1e-5:raise AssertionError('Accounting reconciliation failed')
        return {'version':VERSION,'mode':s['mode'],'as_of':at.isoformat(),'started_at':s['started_at'],'portfolios':result,'health':s['health'],'assumptions':{'fills':'SIMULATED_QUOTE_TOUCH_FULL_SIZE_NO_DEPTH_OR_QUEUE','fee_per_contract_per_side':s['fee'],'market_exit_slippage_per_share':s['slippage'],'nav_basis':'cash plus option midpoint/mark; liquidation NAV uses bid less costs','true_between_sample_crossings':'UNKNOWN','actual_broker_fills':'SEPARATE_AUTHORITATIVE_LEDGER'}}

    def valuation(self,s,at,source):
        snapshot=self.snapshot(s,at)
        for name,p in snapshot['portfolios'].items():
            payload={key:value for key,value in p.items() if key not in {'positions','pending_orders'}}
            self.db.execute('INSERT INTO valuations(at,source,portfolio,payload) VALUES(?,?,?,?)',(aware(at).isoformat(),source,name,encode(payload)))

    def close_lot(self,s,name,lid,qty,price,at,reason,source):
        p=s['portfolios'][name];l=p['lots'][lid]
        if qty<=0 or qty>l['quantity']:raise ValueError('Invalid closing quantity; shorts prohibited')
        fee=s['fee']*qty;p['cash']+=100*qty*price-fee;p['fees']+=fee
        net=100*qty*(price-l['entry'])-2*s['fee']*qty;l['closed_net_pnl']=l.get('closed_net_pnl',0)+net;p['realized_net']+=net;p['traded_premium']+=price*100*qty
        l['quantity']-=qty
        if not l['quantity']:
            l['status']='CLOSED'
            for order in p['orders'].values():
                if order['side']=='SELL' and order['status']=='PENDING' and order['position_id']==lid:order['status']='CANCELLED_POSITION_CLOSED'
        self.event(at,name,'SIMULATED_SELL',position_id=lid,quantity=qty,price=price,fee=fee,net_pnl=net,reason=reason,source=source)

    def process_bundle(self,key,bundle,available_at,*,fingerprint):
        at=aware(available_at)
        with self.db:
            s=self.load()
            # Duplicate delivery is a no-op even when a later invocation has a later clock.
            if not self.input('QUOTE_BUNDLE',key,{'sha256':hashlib.sha256(encode(bundle).encode()).hexdigest()}):return False
            self.check(s,at,fingerprint);self.expire(s,at)
            from intraday_option_paths import session_bounds
            bounds=session_bounds(at)
            watched=self.watch(s);seen=set();valid=[]
            for point in bundle.get('observations',[]):
                sym=symbol(point.get('contract_symbol'))
                if sym not in watched:continue
                try:
                    obs=aware(point.get('observed_at'));qt=aware(point.get('quote_at'));bid=number(point.get('bid'));ask=number(point.get('ask'))
                    ok=point.get('quote_status')=='OBSERVED' and point.get('realtime') is True and bid is not None and ask is not None and 0<bid<=ask and ask>0 and qt<=obs<=at and 0<=(at-qt).total_seconds()<=60 and bounds and bounds[0]<=qt<=obs<bounds[1] and bounds[0]<=at<bounds[1]
                except (ValueError,TypeError):ok=False
                if not ok:
                    s['health']['invalid_quotes']+=1
                    if number(point.get('bid'))==0:s['health']['zero_bid_observations']=s['health'].get('zero_bid_observations',0)+1
                    continue
                valid.append((obs,qt,sym,point,bid,ask))
            # At most one latest valid quote per contract in a saved sample bundle.
            latest={row[2]:row for row in sorted(valid,key=lambda x:(x[0],x[1]))}
            for sym,(obs,qt,_,point,bid,ask) in sorted(latest.items()):
                seen.add(sym);old=s['marks'].get(sym)
                if old and old.get('quote_at')==qt.isoformat() and old.get('observed_at')==obs.isoformat():continue
                if old:
                    gap=trading_gap_seconds(old['at'],at)
                    if gap>90:s['health']['intraday_gaps']+=1;s['health']['max_gap_seconds']=max(s['health']['max_gap_seconds'],gap)
                mark=number(point.get('mark'))
                if mark is None or not bid<=mark<=ask:mark=(bid+ask)/2
                s['marks'][sym]={'bid':bid,'ask':ask,'mark':mark,'at':at.isoformat(),'quote_at':qt.isoformat(),'observed_at':obs.isoformat(),'source':key}
                self.db.execute('INSERT OR IGNORE INTO coverage VALUES(?,?,?)',(sym,str(at.astimezone(ET).date()),int(obs.timestamp()//60)))
                source={'bundle':key,'quote_at':qt.isoformat(),'observed_at':obs.isoformat(),'available_at':at.isoformat(),'bid':bid,'ask':ask}
                for name,p in s['portfolios'].items():
                    for lid,l in list(p['lots'].items()):
                        if l['status']!='OPEN' or l['symbol']!=sym:continue
                        # No invented expiry settlement; it needs actual settlement evidence.
                        if at.astimezone(ET).date()>datetime.fromisoformat(l['expiration']).date():
                            self.event(at,name,'SETTLEMENT_REQUIRED',position_id=lid);continue
                        sells=[(oid,o) for oid,o in p['orders'].items() if o['status']=='PENDING' and o['side']=='SELL' and o['position_id']==lid and obs>=aware(o['decided_at'])]
                        reason=None;price=max(0,bid-s['slippage']);qty=l['quantity']
                        if sells:
                            oid,o=sells[0];qty=min(qty,o['quantity']);reason=o['reason'];o['status']='FILLED'
                        elif bid<=l['stop']:reason='STOP_BID_OBSERVED'
                        elif bid>=l['target']:reason='TARGET_LIMIT_OBSERVED';price=l['target']
                        if reason:self.close_lot(s,name,lid,qty,price,at,reason,source)
                    for oid,o in list(p['orders'].items()):
                        if o['status']!='PENDING' or o['side']!='BUY' or o['symbol']!=sym or obs<aware(o['decided_at']):continue
                        # Rebalancing exits must actually fill before replacement
                        # entries; neither prospective proceeds nor freed slots are assumed.
                        if any(x['status']=='PENDING' and x['side']=='SELL' for x in p['orders'].values()):continue
                        # Limit orders cannot pay above their limit, even under slippage stress.
                        if ask>o['limit']+1e-9:continue
                        price=min(o['limit'],ask+s['slippage'])
                        cost=(price*100+s['fee'])*o['quantity']
                        own_reserve=(o['limit']*100+2*s['fee'])*o['quantity'] if o.get('funding_status','RESERVED')=='RESERVED' else 0
                        other_reserve=max(0,self.pending_reserve(s,p)-own_reserve)
                        if cost+s['fee']*o['quantity']+other_reserve+self.exit_fee_reserve(s,p)>p['cash']+1e-9:continue
                        held_qty=sum(l['quantity'] for l in p['lots'].values() if l['status']=='OPEN' and l['ticker']==o['ticker'])
                        from config import MAX_CONTRACTS_PER_POSITION
                        if held_qty and o.get('allocation_action')!='ADD':continue
                        if held_qty+o['quantity']>MAX_CONTRACTS_PER_POSITION:continue
                        p['cash']-=cost;p['fees']+=s['fee']*o['quantity'];p['traded_premium']+=price*100*o['quantity'];o['status']='FILLED';o['funding_status']='FILLED_CASH_DEBITED'
                        lid=oid;p['lots'][lid]={**o,'status':'OPEN','entry':price,'entry_at':at.isoformat(),'entry_quantity':o['quantity'],'peak':price}
                        self.event(at,name,'SIMULATED_BUY',position_id=lid,quantity=o['quantity'],price=price,fee=s['fee']*o['quantity'],source=source)
                        if bid<=o['stop']:self.close_lot(s,name,lid,o['quantity'],max(0,bid-s['slippage']),at,'IMMEDIATE_SPREAD_STOP',source)
            missing=set(watched)-seen;s['health']['missing_quotes']+=len(missing)
            if missing:self.event(at,'BOTH','QUOTE_COVERAGE_MISSING',symbols=sorted(missing),bundle=key)
            s['last_at']=at.isoformat()
            snap=self.snapshot(s,at)
            for name,p in s['portfolios'].items():
                p['peak_nav']=snap['portfolios'][name]['peak_nav'];p['max_drawdown']=snap['portfolios'][name]['max_drawdown']
            self.valuation(s,at,'BUNDLE:'+key);self.save(s)
        return True

    def capture_daily(self,key,candidates,at,*,fingerprint,source_hash):
        """Freeze both decisions at actual availability, using independent holdings."""
        from configuration_profile_shadow import allocate_profile
        from position_review import _review_single_position
        at=aware(at);bounds=validate_daily_input(candidates,at)
        candidates=candidates.copy(deep=True)
        with self.db:
            s=self.load()
            # A rerun of the same source does not replenish an already-used daily portfolio.
            if not self.input('DAILY_DECISION',key,{'source_sha256':source_hash,'candidates':candidates.to_dict('records')}):return False
            self.check(s,at,fingerprint);self.expire(s,at)
            for name,p in s['portfolios'].items():
                # Cancel prior unfilled entry orders before making new independent decisions.
                for oid,o in p['orders'].items():
                    if o['status']=='PENDING':o['status']='CANCELLED_BY_NEW_DECISION';self.event(at,name,'ORDER_CANCELLED',order_id=oid)
                snap=self.snapshot(s,at)['portfolios'][name]
                reviews=[];ids=[]
                for lid,l in p['lots'].items():
                    if l['status']!='OPEN':continue
                    mark=s['marks'][l['symbol']]
                    position={'PositionID':lid,'Ticker':l['ticker'],'OptionStrategy':l['strategy'],'Expiration':l['expiration'],'Strike':l['strike'],'Contracts':l['quantity'],'EntryPremium':l['entry'],'EntryDate':l['entry_at'],'ProfitTarget':l['target'],'StopLoss':l['original_stop'],'TimeStopDTE':l['time_stop_dte'],'RecommendedStop':l['stop'],'PeakPremium':l['peak']}
                    review=_review_single_position(position,candidates,quote_override={'current_price':mark['bid'] if l['symbol'] not in snap['stale_or_missing_marks'] else None},as_of=at.astimezone(ET),allow_network=False)
                    l['stop']=max(l['stop'],number(review['stop_loss'],l['stop']));l['peak']=number(review['peak_premium'],l['peak'])
                    review['latest_allocation_score']=number(review['latest_allocation_score'],0.)
                    reviews.append(review);ids.append(lid)
                    self.event(at,name,'POSITION_REVIEW',position_id=lid,review=review)
                if snap['stale_or_missing_marks']:
                    # Time/event exits remain actionable once a fresh bid arrives,
                    # but unavailable marks cannot fund new allocations.
                    for lid,review in zip(ids,reviews):
                        if review['position_recommendation'] in {'SELL','CLOSE'}:
                            l=p['lots'][lid];oid=name+':SELL:'+key+':'+lid
                            p['orders'][oid]={'side':'SELL','status':'PENDING','position_id':lid,'symbol':l['symbol'],'raw_symbol':l['raw_symbol'],'ticker':l['ticker'],'expiration':l['expiration'],'strategy':l['strategy'],'quantity':l['quantity'],'decided_at':at.isoformat(),'reason':review['position_reason']}
                            self.event(at,name,'SELL_ORDER',order_id=oid,order=p['orders'][oid])
                    self.event(at,name,'ALLOCATION_SKIPPED_STALE_HOLDINGS',symbols=snap['stale_or_missing_marks']);continue
                row=candidates.iloc[0];context={k:row.get(k) for k in ['market_regime','risk_mode','allocation_bias']}
                result=allocate_profile(candidates,pd.DataFrame(reviews),policy=name,account_nav=snap['nav'],market_context=context,market_breadth={'breadth_regime':row.get('breadth_regime')})
                for i,review in result.positions.iterrows():
                    lid=ids[i];l=p['lots'][lid];target=int(review['portfolio_target_contracts']);qty=max(0,l['quantity']-target)
                    if qty:
                        oid=name+':SELL:'+key+':'+lid
                        p['orders'][oid]={'side':'SELL','status':'PENDING','position_id':lid,'symbol':l['symbol'],'raw_symbol':l['raw_symbol'],'ticker':l['ticker'],'expiration':l['expiration'],'strategy':l['strategy'],'quantity':qty,'decided_at':at.isoformat(),'reason':str(review['portfolio_action_reason'])}
                        self.event(at,name,'SELL_ORDER',order_id=oid,order=p['orders'][oid])
                candidates_out=result.candidates
                self.event(at,name,'ALLOCATION_DECISIONS',source_hash=source_hash,rows=candidates_out.to_dict('records'),summary=result.summary)
                held={l['ticker'] for l in p['lots'].values() if l['status']=='OPEN'}
                for _,r in candidates_out[candidates_out.portfolio_action.isin(['OPEN','ADD'])].iterrows():
                    # Do not create duplicate same-ticker entry lots while a position/exit remains.
                    if str(r['ticker']) in held and r['portfolio_action']!='ADD':continue
                    qty=int(r['contracts']);limit=number(r.get('execution_entry_price'));stop=number(r.get('stop_loss_price'));target=number(r.get('profit_target_price'))
                    rawsym=str(r.get('contract_symbol') or '')
                    if not rawsym or rawsym.casefold()=='nan' or any(v is None for v in [limit,stop,target]) or not 0<stop<limit<target or qty<=0:
                        self.event(at,name,'ENTRY_REJECTED_INVALID_PLAN',recommendation_id=r['RecommendationID']);continue
                    reserve=(limit*100+2*s['fee'])*qty
                    funding='RESERVED' if reserve+self.pending_reserve(s,p)+self.exit_fee_reserve(s,p)<=p['cash']+1e-9 else 'WAITING_FOR_CASH'
                    if funding=='WAITING_FOR_CASH':self.event(at,name,'ENTRY_AWAITS_FILLED_SALES',recommendation_id=r['RecommendationID'])
                    oid=name+':BUY:'+key+':'+str(r['RecommendationID'])
                    o={'side':'BUY','status':'PENDING','funding_status':funding,'allocation_action':str(r['portfolio_action']),'recommendation_id':str(r['RecommendationID']),'symbol':symbol(rawsym),'raw_symbol':rawsym,'ticker':str(r['ticker']),'expiration':str(r['expiration']),'strategy':str(r['option_strategy']),'strike':number(r.get('strike')),'quantity':qty,'limit':limit,'stop':stop,'original_stop':stop,'target':target,'time_stop_dte':int(number(r.get('time_stop_dte'),14)),'decided_at':at.isoformat(),'expires_at':bounds[1].isoformat()}
                    p['orders'][oid]=o;held.add(o['ticker']);self.event(at,name,'BUY_LIMIT_ORDER',order_id=oid,order=o)
            s['last_at']=at.isoformat();self.valuation(s,at,'DECISION:'+key);self.save(s)
        return True

    def export(self,output,at=None):
        output=Path(output);output.mkdir(parents=True,exist_ok=True);snap=self.snapshot(at=at)
        tag=aware(at or snap['as_of']).strftime('%Y%m%d_%H%M%S_%f')
        report=output/f'comparison_{tag}.json'
        with report.open('x',encoding='utf-8') as f:json.dump(snap,f,indent=2,allow_nan=False)
        events=pd.read_sql_query('SELECT * FROM events ORDER BY id',self.db);events.to_csv(output/'events.csv',index=False)
        fills=[]
        for _,e in events[events.kind.isin(['SIMULATED_BUY','SIMULATED_SELL'])].iterrows():fills.append({'at':e['at'],'portfolio':e['portfolio'],'kind':e['kind'],**json.loads(e['payload'])})
        pd.DataFrame(fills).to_csv(output/'simulated_fills.csv',index=False)
        history=[]
        for at,source,name,payload in self.db.execute('SELECT at,source,portfolio,payload FROM valuations ORDER BY id'):
            history.append({'at':at,'source':source,'portfolio':name,**json.loads(payload)})
        pd.DataFrame(history).to_csv(output/'nav_history.csv',index=False)
        pd.read_sql_query('SELECT symbol,day,count(*) AS valid_sample_minutes FROM coverage GROUP BY symbol,day',self.db).to_csv(output/'quote_coverage.csv',index=False)
        return report
