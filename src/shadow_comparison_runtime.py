"""Opt-in runtime for two independent quote-driven comparison portfolios."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import sqlite3
from uuid import uuid4
from zoneinfo import ZoneInfo
import pandas as pd
from shadow_option_ledger import ComparisonLedger,VERSION,aware,clean,validate_daily_input
from six_week_release import active_settings

ROOT=Path(__file__).resolve().parent.parent
RELATIVE_DIR=Path('data/processed/configuration_comparison')
SPEC_PATH=Path('research/six_week_20261029/comparison_spec.json')


def spec(root):
    value=json.loads((Path(root)/SPEC_PATH).read_text(encoding='utf-8-sig'))
    if value['policy_version']!=VERSION or value['control']!='baseline' or value['challenger']!='moderate_delta_iv':raise ValueError('Unsupported comparison specification')
    return value


def fingerprint(root):
    root=Path(root);h=hashlib.sha256()
    from policy_evidence import RULE_FILES
    rule_names=set(RULE_FILES)|{
        'configuration_profile_shadow.py','position_review.py','portfolio_exposure.py',
        'shadow_option_ledger.py','shadow_comparison_runtime.py','intraday_option_paths.py',
        'option_observation_collector.py','weekly_scan.py','trade_journal.py',
        'market_context.py','market_breadth.py','data_loader.py','indicators.py','trade_quality.py','data_quality.py','policy_evidence.py',
        'schwab/market_data_client.py',
    }
    # Authentication helpers/token files and unrelated analyses are not policy
    # parameters: normal weekly credential renewal must not halt the experiment.
    for name in sorted(rule_names):
        p=root/'src'/name;h.update(name.encode())
        h.update(p.read_text(encoding='utf-8-sig').encode('utf-8') if p.exists() else b'MISSING')
    h.update((root/SPEC_PATH).read_text(encoding='utf-8-sig').encode('utf-8'));h.update(sys.version.encode())
    for package in ['pandas','numpy','pandas_market_calendars']:h.update((package+importlib.metadata.version(package)).encode())
    return h.hexdigest()


def enabled(root,now):return bool(active_settings(root,today=aware(now).astimezone(ZoneInfo('America/New_York')).date()).get('comparison'))


def priority_contracts(root=ROOT,now=None):
    now=now or datetime.now(timezone.utc);root=Path(root)
    if not enabled(root,now):return {}
    path=root/RELATIVE_DIR/'ledger.sqlite'
    if not path.exists():return {}
    connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=1)
    try:
        row=connection.execute('SELECT payload FROM state WHERE id=1').fetchone()
        if not row:return {}
        state=json.loads(row[0])
        return ComparisonLedger.watch(None,state)
    finally:connection.close()


def record_failure(root,stage,error,source=None):
    directory=Path(root)/RELATIVE_DIR;directory.mkdir(parents=True,exist_ok=True)
    value={'at':datetime.now(timezone.utc).isoformat(),'stage':stage,'error_type':type(error).__name__,'source':str(source) if source else None}
    with (directory/'processing_failures.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(value)+'\n')
    value['status']='FAILED_UPDATE';target=directory/'health_latest.json';tmp=target.with_name(target.name+'.'+uuid4().hex+'.tmp');tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(target)


def broker_view(root,started):
    path=Path(root)/'data/account_state_snapshots.csv'
    if not path.exists():return {'status':'UNAVAILABLE','truth':'BROKER_CONFIRMED_FILLS_AND_STATEMENTS_REMAIN_SEPARATE'}
    f=pd.read_csv(path);dates=pd.to_datetime(f.AsOfDate,errors='coerce');f=f.assign(_date=dates).dropna(subset=['_date']).sort_values('_date')
    if f.empty:return {'status':'UNAVAILABLE'}
    latest=f.iloc[-1];date=aware(started).astimezone(ZoneInfo('America/New_York')).date()
    prior=f[f._date.dt.date<date]
    result={'status':'BROKER_STATEMENT_SNAPSHOT','as_of_date':str(latest.AsOfDate),'net_liquidating_value':float(latest.NetLiquidatingValue),'cash':float(latest.CashValue),'option_market_value':float(latest.OptionMarketValue),'unrealized_pnl':float(latest.UnrealizedPnL),'source':str(latest.get('SourcePath','')),'snapshot_is_not_intraday_simulation_mark':True}
    if len(prior) and latest._date.date()>=date:
        base=prior.iloc[-1];result['period_nav_change']={'baseline_close_date':str(base.AsOfDate),'baseline_nav':float(base.NetLiquidatingValue),'latest_nav':float(latest.NetLiquidatingValue),'nav_change':float(latest.NetLiquidatingValue-base.NetLiquidatingValue),'cash_flow_adjusted_return':None,'note':'Statement-close NAV change, not matched intraday fills or a cash-flow-adjusted investment return; canonical capital-ledger reporting owns actual performance.'}
    return clean(result)


def publish(ledger,root,archive=False):
    directory=Path(root)/RELATIVE_DIR;directory.mkdir(parents=True,exist_ok=True)
    # Serialize report writers with ledger writers so latest never goes backwards.
    ledger.db.execute('BEGIN IMMEDIATE')
    try:
        value=ledger.snapshot()
        queued=ledger.db.execute('SELECT payload FROM pending_daily WHERE id=1').fetchone()
        value['deferred_daily_decision']={k:v for k,v in json.loads(queued[0]).items() if k!='candidates'} if queued else None
        value['actual_broker']=broker_view(root,value['started_at'])
        lines=['# Stonks option configuration comparison','',f"Mode: **{value['mode']}**. As of {value['as_of']}. **Simulated fills; actual broker results remain separate.**",'', '| Portfolio | Cash | Option value | NAV | Realized net | Unrealized net | Fees | Return | Max drawdown |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
        for name,p in value['portfolios'].items():
            lines.append(f"| {name} | ${p['cash']:,.2f} | ${p['option_market_value']:,.2f} | ${p['nav']:,.2f} | ${p['realized_net_pnl']:,.2f} | ${p['unrealized_net_pnl']:,.2f} | ${p['fees_paid']:,.2f} | {p['return_on_initial_capital']:.2%} | {p['max_drawdown']:.2%} |")
            if p['stale_or_missing_marks']:lines.append(f"\n{name}: stale/missing marks for {', '.join(p['stale_or_missing_marks'])}; NAV carries prior values and is not a current executable value.\n")
        if value['deferred_daily_decision']:lines+=['','**Daily allocation deferred until fresh held-contract quotes arrive.**']
        lines+=['','Challenger: recorded absolute delta >0.35 to <=0.50 and IV >20% to <=40%, followed by the existing allocator. Same accounting/fill/exit logic for both portfolios.','',f"Quote health: {json.dumps(value['health'])}",'','Actual broker snapshot: '+json.dumps(value['actual_broker']), '', 'Stop/target fills are sampled quote-touch simulations with full-size/depth assumptions, not broker-confirmed fills. Missing intervals are never interpolated.']
        for name,content in [('latest.json',json.dumps(value,indent=2,allow_nan=False)),('latest.md','\n'.join(lines)+'\n')]:
            target=directory/name;tmp=target.with_name(target.name+'.'+uuid4().hex+'.tmp');tmp.write_text(content,encoding='utf-8');tmp.replace(target)
        if archive:
            target=directory/('decision_report_'+aware(value['as_of']).strftime('%Y%m%d_%H%M%S_%f')+'.json')
            with target.open('x',encoding='utf-8') as h:json.dump(value,h,indent=2,allow_nan=False)
        target=directory/'health_latest.json';tmp=target.with_name(target.name+'.'+uuid4().hex+'.tmp');tmp.write_text(json.dumps({'status':'UPDATED_WITH_QUALITY_FLAGS' if any(p['stale_or_missing_marks'] or p['settlement_required'] for p in value['portfolios'].values()) else 'UPDATED','as_of':value['as_of'],'health':value['health']},indent=2),encoding='utf-8');tmp.replace(target)
        ledger.db.commit();return value
    except BaseException:ledger.db.rollback();raise


def queue_daily(ledger,key,frame,now,fp,source_hash):
    with ledger.db:
        state=ledger.load();ledger.check(state,now,fp)
        changed=ledger.input('DEFERRED_REQUEST',key,{'source_sha256':source_hash,'candidates':frame.to_dict('records')})
        old=ledger.db.execute('SELECT payload FROM pending_daily WHERE id=1').fetchone()
        if old and json.loads(old[0])['key']==key:return
        request={'key':key,'source_hash':source_hash,'requested_at':aware(now).isoformat(),'candidates':clean(frame.to_dict('records'))}
        ledger.db.execute('INSERT OR REPLACE INTO pending_daily VALUES(1,?)',(json.dumps(request),))
        ledger.event(now,'BOTH','DAILY_DECISION_DEFERRED',source_key=key,reason='Waiting for fresh quotes for every held contract')
        state['last_at']=aware(now).isoformat();ledger.save(state)


def apply_pending(ledger,now,fp):
    row=ledger.db.execute('SELECT payload FROM pending_daily WHERE id=1').fetchone()
    if not row:return False
    request=json.loads(row[0]);frame=pd.DataFrame(request['candidates'])
    try:validate_daily_input(frame,now)
    except ValueError:
        with ledger.db:
            state=ledger.load();state['health']['deferred_decisions_expired']=state['health'].get('deferred_decisions_expired',0)+1
            ledger.event(now,'BOTH','DEFERRED_DECISION_EXPIRED',source_key=request['key'])
            ledger.db.execute('DELETE FROM pending_daily WHERE id=1');ledger.save(state)
        return False
    if any(p['stale_or_missing_marks'] for p in ledger.snapshot(at=now)['portfolios'].values()):return False
    changed=ledger.capture_daily(request['key'],frame,now,fingerprint=fp,source_hash=request['source_hash'])
    with ledger.db:ledger.db.execute('DELETE FROM pending_daily WHERE id=1')
    return changed


def capture_daily(candidates_path,root=ROOT,now=None):
    now=aware(now or datetime.now(timezone.utc));root=Path(root)
    if not enabled(root,now):return {'status':'DISABLED'}
    from intraday_option_paths import session_bounds
    bounds=session_bounds(now)
    if not bounds or not bounds[0]<=now<bounds[1]:raise ValueError('Comparison decisions need an open regular session')
    source=Path(candidates_path);raw=source.read_bytes();frame=pd.read_csv(source,low_memory=False)
    validate_daily_input(frame,now)
    fp=fingerprint(root);configuration=spec(root)
    manifest=json.loads((root/'research/six_week_20261029/release_manifest.json').read_text(encoding='utf-8-sig'))
    if manifest.get('version')!=VERSION or manifest.get('expected_initial_fingerprint')!=fp:raise ValueError('Reviewed release manifest does not match policy/dependencies')
    ledger=ComparisonLedger(root/RELATIVE_DIR/'ledger.sqlite')
    try:
        if not ledger.db.execute('SELECT 1 FROM state').fetchone():
            ledger.initialize(now,capital=configuration['initial_capital'],fee_per_contract=configuration['fee_per_contract_per_side'],market_slippage=configuration['market_slippage_per_share'],fingerprint=fp)
        if any(p['stale_or_missing_marks'] for p in ledger.snapshot(at=now)['portfolios'].values()):
            queue_daily(ledger,source.name,frame,now,fp,hashlib.sha256(raw).hexdigest())
            publish(ledger,root,archive=True)
            return {'status':'DEFERRED_FOR_FRESH_HOLDING_QUOTES'}
        changed=ledger.capture_daily(source.name,frame,now,fingerprint=fp,source_hash=hashlib.sha256(raw).hexdigest())
        report=publish(ledger,root,archive=changed)
        return {'status':'RECORDED' if changed else 'ALREADY_RECORDED','as_of':report['as_of']}
    finally:ledger.close()


def consume_bundle(path,root=ROOT,now=None):
    now=aware(now or datetime.now(timezone.utc));root=Path(root)
    if not enabled(root,now):return {'status':'DISABLED'}
    dbpath=root/RELATIVE_DIR/'ledger.sqlite'
    if not dbpath.exists():return {'status':'AWAITING_FIRST_DAILY_DECISION'}
    source=Path(path);raw=source.read_bytes();bundle=json.loads(gzip.decompress(raw));bundle['_raw_source_sha256']=hashlib.sha256(raw).hexdigest()
    ledger=ComparisonLedger(dbpath)
    try:
        fp=fingerprint(root)
        changed=ledger.process_bundle(str(source.resolve()),bundle,now,fingerprint=fp)
        apply_pending(ledger,now,fp)
        publish(ledger,root)
        return {'status':'UPDATED' if changed else 'ALREADY_PROCESSED'}
    finally:ledger.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('daily');d.add_argument('--candidates',type=Path,required=True)
    q=sub.add_parser('quote-bundle');q.add_argument('--bundle',type=Path,required=True)
    r=sub.add_parser('report')
    a=p.parse_args()
    try:
        if a.command=='daily':print(json.dumps(capture_daily(a.candidates)))
        elif a.command=='quote-bundle':print(json.dumps(consume_bundle(a.bundle)))
        else:
            if not (ROOT/RELATIVE_DIR/'ledger.sqlite').exists():
                print(json.dumps({'status':'NOT_STARTED'}));raise SystemExit(0)
            l=ComparisonLedger(ROOT/RELATIVE_DIR/'ledger.sqlite')
            try:
                value=publish(l,ROOT,archive=True)
                l.export(ROOT/RELATIVE_DIR/'exports')
                print(json.dumps(value,indent=2))
            finally:l.close()
    except Exception as error:
        record_failure(ROOT,a.command,error,getattr(a,'candidates',getattr(a,'bundle',None)))
        raise
