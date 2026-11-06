import copy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import structure_research as m

NOW=datetime(2026,11,4,15,40,tzinfo=timezone.utc)


def c(strike,delta,expiry='2027-01-15',side='C',bid=3,ask=3.1):
    return {'contractSymbol':f"TEST {expiry[2:].replace('-','')}{side}{int(strike*1000):08}",
        'Expiration':expiry,'strike':strike,'bid':bid,'ask':ask,'broker_delta':delta,
        'openInterest':1000,'RejectionReason':''}


def row():
    base=c(100,.4)
    return {'ticker':'TEST','option_strategy':'Long Call','contract_symbol':base['contractSymbol'],
        'expiration':base['Expiration'],'strike':100,'broker_delta':.4,'allocation_decision':'Allocate',
        'portfolio_forward_score':90,'RecommendationID':'rec-1','RecommendationDate':NOW.isoformat(),
        'selection_evidence_json':json.dumps([c(95,.65),c(105,.3,bid=1,ask=1.05),c(100,.42,'2027-02-19'),
            c(95,-.3,side='P'),c(90,-.2,side='P',bid=1,ask=1.05)])}


def quote(now,bid,ask=None,age=0):
    return {'realtime':True,'quote':{'bidPrice':bid,'askPrice':ask if ask is not None else bid+.1,
        'quoteTime':(now-timedelta(seconds=age)).timestamp()*1000}}


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/m.SETTINGS).parent.mkdir(parents=True)
        shutil.copy2(m.ROOT/m.SETTINGS,self.root/m.SETTINGS)
        self.settings,self.fp=m.configuration(self.root)

    def tearDown(self):self.tmp.cleanup()

    def study(self):
        variants,missing=m.select_variants(row(),self.settings,NOW)
        return {'id':'id','ticker':'TEST','direction':1,'settings':self.settings,'decided_at':NOW.isoformat(),
            'entry_deadline':(NOW+timedelta(minutes=30)).isoformat(),'due_at':m.due_date(NOW,5).isoformat(),
            'variants':variants,'state':'WAITING','last_sample_at':None}

    def quotes(self,s,now):
        result={'TEST':quote(now,100,100.05)}
        for name,v in s['variants'].items():
            for l in v['legs']:
                bid=1 if l['strike']==105 else 3
                result[l['symbol']]=quote(now,bid,bid+.05)
        return result

    def test_exact_same_side_and_later_contracts_and_vertical(self):
        variants,missing=m.select_variants(row(),self.settings,NOW)
        self.assertEqual(set(variants),{'outright','higher_delta','later_expiry','debit_vertical'})
        self.assertEqual(variants['debit_vertical']['width'],5)
        self.assertEqual(variants['debit_vertical']['legs'][1]['side'],-1)
        self.assertEqual(missing,[])

    def test_no_fabricated_legs_from_old_metadata_missing_oi(self):
        r=row();ev=json.loads(r['selection_evidence_json'])
        for e in ev:e.pop('openInterest')
        r['selection_evidence_json']=json.dumps(ev)
        variants,missing=m.select_variants(r,self.settings,NOW)
        self.assertEqual(set(variants),{'outright'})
        self.assertIn('DEBIT_SHORT_LEG_UNAVAILABLE',missing)

    def test_directional_bearish_debit_and_credit_pair(self):
        r=row();r.update(option_strategy='Long Put',contract_symbol=c(100,-.4,side='P')['contractSymbol'],broker_delta=-.4,
            selection_evidence_json=json.dumps([c(95,-.3,side='P'),c(105,-.65,side='P'),c(105,.3),c(110,.2,bid=1,ask=1.05)]))
        settings={**self.settings,'credit_spreads_enabled':True}
        variants,_=m.select_variants(r,settings,NOW)
        self.assertEqual(variants['debit_vertical']['legs'][1]['strike'],95)
        self.assertEqual(variants['credit_vertical']['legs'][0]['strike'],110)

    def test_fresh_synchronous_entry_risk_and_fixed_session_exit(self):
        s=self.study();t=NOW+timedelta(minutes=1)
        m.advance(s,self.quotes(s,t),t)
        self.assertEqual(s['state'],'OPEN')
        for v in s['variants'].values():
            self.assertLessEqual(v['max_loss_including_fees'],1000)
            self.assertEqual(v['status'],'OPEN')
        due=m.aware(s['due_at']);m.advance(s,self.quotes(s,due),due)
        self.assertEqual(s['state'],'CLOSED')
        self.assertTrue(all(v['status']=='CLOSED' for v in s['variants'].values()))
        self.assertEqual(s['variants']['outright']['net_pnl'],s['variants']['higher_delta']['net_pnl'])
        self.assertLess(s['variants']['outright']['net_pnl'],0) # spread/fees/slippage matter on flat quotes

    def test_missing_stale_zero_future_and_skew_block_entire_family(self):
        for bad in ('missing','stale','zero','future','skew'):
            s=self.study();t=NOW+timedelta(minutes=2);qs=self.quotes(s,t)
            sym=s['variants']['outright']['legs'][0]['symbol']
            if bad=='missing':qs.pop(sym)
            elif bad=='stale':qs[sym]=quote(t,3,3.1,age=61)
            elif bad=='zero':qs[sym]=quote(t,0,.1)
            elif bad=='future':qs[sym]=quote(t,3,3.1,age=-1)
            else:qs[sym]=quote(t,3,3.1,age=10)
            m.advance(s,qs,t)
            self.assertEqual(s['state'],'WAITING',bad)

    def test_no_retroactive_entry_or_exit_after_deadline(self):
        s=self.study();t=NOW+timedelta(minutes=31)
        m.advance(s,self.quotes(s,t),t)
        self.assertEqual(s['state'],'ENTRY_WINDOW_MISSED')
        s=self.study();m.advance(s,self.quotes(s,NOW),NOW)
        t=m.aware(s['due_at'])+timedelta(minutes=6)
        m.advance(s,self.quotes(s,t),t)
        self.assertEqual(s['state'],'EXIT_WINDOW_MISSED')
        self.assertEqual(s['variants']['outright']['status'],'OPEN')

    def test_no_spread_sizing_using_credit_received(self):
        v={'kind':'credit','width':5,'legs':[{'symbol':'L','side':1},{'symbol':'S','side':-1}]}
        qs={'L':{'bid':1,'ask':1.05},'S':{'bid':2,'ask':2.05}}
        out=m.entry_variant(v,qs,self.settings)
        self.assertEqual(out['quantity'],2) # ~407 risk per spread, not ~93 premium
        self.assertGreater(out['max_loss_including_fees'],800)

    def test_capture_no_backfill_and_preview_never_writes(self):
        path=self.root/'source.csv';pd.DataFrame([row()]).to_csv(path,index=False)
        before=path.read_bytes()
        out=m.capture(path,self.root,now=NOW,preview=True)
        self.assertEqual(out['status'],'PREVIEW_NOT_STARTED')
        self.assertFalse((self.root/m.DIRECTORY).exists())
        out=m.capture(path,self.root,now=NOW,chain_fetch=lambda _: {})
        self.assertEqual(out['studies'],1)
        repeat=m.capture(path,self.root,now=NOW,chain_fetch=lambda _: {})
        self.assertEqual(repeat['status'],'ALREADY_CAPTURED')
        self.assertEqual(path.read_bytes(),before)
        with self.assertRaises(ValueError):m.capture(path,self.root,now=NOW+timedelta(days=1),chain_fetch=lambda _: {})

    def test_collection_idempotence_cached_fetch_and_report_readonly(self):
        path=self.root/'source.csv';pd.DataFrame([row()]).to_csv(path,index=False)
        m.capture(path,self.root,now=NOW,chain_fetch=lambda _: {})
        def fetch(symbols,timeout_seconds):
            self.assertLessEqual(timeout_seconds,4)
            return {sym:quote(NOW+timedelta(minutes=1),100 if sym=='TEST' else 3) for sym in symbols}
        for _ in range(2):m.collect(self.root,now=NOW+timedelta(minutes=1),fetch=fetch)
        dbpath=self.root/m.DIRECTORY/'studies.sqlite';before=dbpath.read_bytes()
        report=m.report(self.root,now=NOW+timedelta(minutes=2))
        self.assertEqual(report['sample_count'],1)
        self.assertEqual(report['open_families'],1)
        self.assertEqual(dbpath.read_bytes(),before)
        self.assertIn('Unavailable',m.markdown(report))

    def test_offhours_never_fetches(self):
        self.assertEqual(m.collect(self.root,now=NOW.replace(hour=23),fetch=lambda *_:self.fail())['status'],'OUTSIDE_SESSION')
        self.assertFalse((self.root/m.DIRECTORY).exists())

    def test_exit_calendar_accounts_for_holiday_and_early_close(self):
        # Five sessions after Nov 19: 20, 23, 24, 25, 27 (Thanksgiving skipped).
        due=m.due_date(datetime(2026,11,19,16,tzinfo=timezone.utc),5)
        self.assertEqual(due,datetime(2026,11,27,17,55,tzinfo=timezone.utc))

    def test_forward_chain_supplies_metadata_absent_in_history(self):
        r=row();ev=json.loads(r['selection_evidence_json']);chain={'callExpDateMap':{}}
        for e in ev:
            if 'P' in e['contractSymbol'].split()[-1][6:7]:continue
            chain['callExpDateMap'].setdefault(e['Expiration']+':72',{}).setdefault(str(e['strike']),[]).append({
                'symbol':e['contractSymbol'],'strikePrice':e['strike'],'bid':e['bid'],'ask':e['ask'],
                'openInterest':e['openInterest'],'delta':e['broker_delta'],'multiplier':100})
        path=self.root/'source.csv';pd.DataFrame([r]).to_csv(path,index=False)
        m.capture(path,self.root,now=NOW,chain_fetch=lambda _:chain)
        report=m.report(self.root,now=NOW)
        self.assertEqual(len(report['studies'][0]['variants']),4)
        self.assertEqual(report['studies'][0]['selection_evidence_status'],'FORWARD_CHAIN_REFERENCE_NOT_FILL')

    def test_source_failure_and_leg_quality_never_fabricate_variants(self):
        r=row();ev=json.loads(r['selection_evidence_json'])
        for e in ev:e['ask']=20
        r['selection_evidence_json']=json.dumps(ev)
        self.assertEqual(set(m.select_variants(r,self.settings,NOW)[0]),{'outright'})
        path=self.root/'source.csv';pd.DataFrame([row()]).to_csv(path,index=False)
        def failure(_):raise RuntimeError('fixture')
        m.capture(path,self.root,now=NOW,chain_fetch=failure)
        s=m.report(self.root,now=NOW)['studies'][0]
        self.assertEqual(set(s['variants']),{'outright'})
        self.assertIn('FAILED',s['selection_evidence_status'])

    def test_report_never_pools_new_settings_and_collection_fails_closed(self):
        path=self.root/'source.csv';pd.DataFrame([row()]).to_csv(path,index=False)
        m.capture(path,self.root,now=NOW,chain_fetch=lambda _: {})
        settings={**self.settings,'credit_spreads_enabled':True}
        (self.root/m.SETTINGS).write_text(json.dumps(settings))
        result=m.report(self.root,now=NOW)
        self.assertEqual(len(result['studies']),0)
        self.assertEqual(len(result['archived_other_policy_studies']),1)
        with self.assertRaises(ValueError):m.collect(self.root,now=NOW+timedelta(minutes=1),fetch=lambda *_:self.fail())

    def test_report_pairs_only_synchronized_completed_exits(self):
        s=self.study();s.update(policy_fingerprint=self.fp,day='2026-11-04')
        m.advance(s,self.quotes(s,NOW),NOW)
        due=m.aware(s['due_at']);m.advance(s,self.quotes(s,due),due)
        db=m.connect(self.root)
        with db:db.execute('insert into studies values(?,?,?)',('id','2026-11-04',json.dumps(s)))
        db.close()
        result=m.report(self.root,now=due)
        self.assertEqual(result['paired_differences']['debit_vertical']['matched_families'],1)
        self.assertEqual(result['underlying_diagnostic']['closed_families'],1)
        s['variants']['debit_vertical']['closed_at']=(due+timedelta(minutes=1)).isoformat()
        db=m.connect(self.root)
        with db:db.execute('update studies set payload=? where id=?',(json.dumps(s),'id'))
        db.close()
        self.assertEqual(m.report(self.root,now=due+timedelta(minutes=1))['paired_differences']['debit_vertical']['matched_families'],0)


if __name__=='__main__':unittest.main()
