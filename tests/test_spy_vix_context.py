from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import spy_vix_context as m

NOW=datetime(2026,11,6,15,35,tzinfo=timezone.utc)


def q(now,last=20,previous=18,opening=19,age=0):
    return {'realtime':True,'quote':{'lastPrice':last,'closePrice':previous,'openPrice':opening,
        'tradeTime':int((now-timedelta(seconds=age)).timestamp()*1000)}}


class VixContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        path=self.root/'research/spy_option_research/settings.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'enabled':True,'start_date':'2026-11-02'}))

    def tearDown(self):self.tmp.cleanup()

    def sample(self,now=NOW,last=20,phase='SAMPLE'):
        def fetch(symbols,timeout_seconds):
            self.assertEqual(symbols,[m.VIX_SYMBOL,'SPY']);self.assertLessEqual(timeout_seconds,3)
            return {m.VIX_SYMBOL:q(now,last),'SPY':q(now,700,710,705)}
        return m.capture(self.root,now=now,phase=phase,fetch=fetch)

    def selection(self,selected=NOW+timedelta(seconds=10)):
        path=self.root/'data/processed/spy_option_research/selections/2026-11-06.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'selected_at':selected.isoformat(),'signal':{'Direction':'Bearish'},
            'candidates':[{'RecommendationID':'rec','action':'Watch','allocation_decision':'No Allocation'}]}))
        return path

    def test_index_needs_last_timestamp_not_bid_ask(self):
        value=m.normalize(q(NOW),NOW)
        self.assertEqual(value['status'],'OBSERVED')
        self.assertEqual(value['change_points'],2)
        self.assertAlmostEqual(value['change_fraction'],20/18-1)
        self.assertAlmostEqual(value['change_from_open_fraction'],20/19-1)

    def test_missing_stale_delayed_future_are_not_valid_or_zero(self):
        self.assertEqual(m.normalize({},NOW)['status'],'MISSING_LEVEL')
        self.assertIsNone(m.normalize({},NOW)['change_fraction'])
        self.assertEqual(m.normalize(q(NOW,age=121),NOW)['status'],'STALE')
        self.assertEqual(m.normalize(q(NOW,age=-1),NOW)['status'],'FUTURE_TIMESTAMP')
        self.assertEqual(m.normalize({**q(NOW),'realtime':False},NOW)['status'],'DELAYED_OR_UNKNOWN_FEED')
        self.assertIsNone(m.normalize(q(NOW,previous=0),NOW)['change_fraction'])

    def test_cadence_is_idempotent_and_rates_use_only_observed_past(self):
        first=self.sample(last=20)
        self.assertEqual(self.sample()['status'],'ALREADY_SAMPLED')
        second=self.sample(NOW+timedelta(minutes=5),last=22)
        self.assertEqual(second['rates']['5m']['reference_sample_id'],first['id'])
        self.assertAlmostEqual(second['rates']['5m']['change_fraction'],.1)
        self.assertIsNone(second['rates']['15m'])
        gap=self.sample(NOW+timedelta(minutes=20),last=23)
        self.assertIsNone(gap['rates']['5m'])
        self.assertIsNotNone(gap['rates']['15m'])

    def test_decision_binding_requires_prior_valid_capture_and_preserves_source(self):
        context=self.sample(phase='DECISION');source=self.selection();original=source.read_bytes()
        binding=m.bind_selection(context,self.root)
        self.assertEqual(binding['status'],'AS_OF_CONTEXT')
        self.assertEqual(m.bind_selection(context,self.root)['status'],'ALREADY_BOUND')
        self.assertEqual(source.read_bytes(),original)
        report=m.report(self.root,NOW+timedelta(minutes=1))
        self.assertEqual(report['decisions'][0]['context']['id'],context['id'])
        self.assertIsNone(report['decisions'][0]['closed_net_pnl'])
        self.assertIn('Unavailable',m.markdown(report))

    def test_later_or_stale_sample_cannot_explain_prior_decision(self):
        context=self.sample(phase='DECISION');self.selection(selected=NOW-timedelta(seconds=1))
        self.assertEqual(m.bind_selection(context,self.root)['status'],'UNAVAILABLE_AS_OF_DECISION')
        self.assertIsNone(m.report(self.root,NOW)['decisions'][0]['context'])

    def test_not_started_disabled_and_offhours_never_fetch_or_create_database(self):
        self.assertEqual(m.report(self.root,NOW)['status'],'NOT_STARTED')
        self.assertFalse((self.root/m.DIRECTORY).exists())
        self.assertEqual(m.capture(self.root,now=NOW.replace(hour=23),fetch=lambda *_:self.fail())['status'],'OUTSIDE_SESSION')
        self.assertFalse((self.root/m.DIRECTORY).exists())

    def test_fetch_failure_is_evidence_not_trading_failure(self):
        def fail(*_,**__):raise RuntimeError('fixture')
        value=m.capture(self.root,now=NOW,phase='DECISION',fetch=fail)
        self.assertEqual(value['status'],'UNAVAILABLE_OR_PARTIAL')
        self.assertEqual(value['error_type'],'RuntimeError')
        self.assertEqual(m.report(self.root,NOW)['valid_observations'],0)

    def test_readonly_report_and_outcome_exact_recommendation_link(self):
        context=self.sample(phase='DECISION');self.selection();m.bind_selection(context,self.root)
        ledger=self.root/'data/processed/spy_option_research/ledger.sqlite';ledger.parent.mkdir(exist_ok=True)
        db=sqlite3.connect(ledger)
        db.execute('create table state(id integer primary key,payload text)')
        db.execute('insert into state values(1,?)',(json.dumps({'portfolios':{'baseline':{'lots':{
            'one':{'recommendation_id':'rec','status':'CLOSED','closed_net_pnl':25},
            'other':{'recommendation_id':'unrelated','status':'CLOSED','closed_net_pnl':999}}}}}),))
        db.commit();db.close()
        before=ledger.read_bytes();report=m.report(self.root,NOW+timedelta(minutes=1))
        self.assertEqual(report['decisions'][0]['closed_net_pnl'],25)
        self.assertEqual(report['decisions'][0]['closed_trades'],1)
        self.assertEqual(before,ledger.read_bytes())

    def test_does_not_invent_history_for_unbound_old_decisions(self):
        self.selection(selected=NOW-timedelta(days=1))
        self.sample()
        self.assertEqual(m.report(self.root,NOW)['decisions'],[])
        self.assertEqual(m.report(self.root,NOW-timedelta(seconds=1))['observations'],0)


if __name__=='__main__':unittest.main()
