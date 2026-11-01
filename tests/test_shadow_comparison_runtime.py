import gzip,json,sys,tempfile,unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from test_shadow_option_ledger import AT,candidates,bundle
import shadow_comparison_runtime as runtime
import intraday_option_paths as collector
from shadow_option_ledger import ComparisonLedger


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'src').mkdir();(self.root/'src/config.py').write_text('FROZEN=1\n')
        release=self.root/'research/six_week_20261029';release.mkdir(parents=True)
        release.joinpath('activation.json').write_text(json.dumps({'enabled':True,'comparison_enabled':True,'diagnostic_forecast':False,'release_status':'READY'}))
        release.joinpath('comparison_spec.json').write_text((Path(runtime.ROOT)/runtime.SPEC_PATH).read_text(encoding='utf-8-sig'))
        release.joinpath('release_manifest.json').write_text(json.dumps({'version':runtime.VERSION,'expected_initial_fingerprint':runtime.fingerprint(self.root)}))
        self.csv=self.root/'trade_recommendations_fixture.csv';candidates(extra=True).to_csv(self.csv,index=False)
    def tearDown(self):self.tmp.cleanup()
    def write_bundle(self,at,quote_bundle):
        p=self.root/('quote_'+at.strftime('%Y%m%d_%H%M%S')+'.json.gz')
        with gzip.open(p,'wt') as f:json.dump(quote_bundle,f)
        return p

    def test_daily_quotes_priority_reports_and_restart_end_to_end(self):
        self.assertEqual(runtime.capture_daily(self.csv,self.root,AT)['status'],'RECORDED')
        watch=runtime.priority_contracts(self.root,AT);self.assertEqual(len(watch),2)
        t=AT+timedelta(minutes=1)
        q=bundle(t,bid=2.9,ask=2.98);q['observations'].append(dict(q['observations'][0],contract_symbol='OTHER 261218C00100000'))
        path=self.write_bundle(t,q)
        self.assertEqual(runtime.consume_bundle(path,self.root,t+timedelta(seconds=1))['status'],'UPDATED')
        self.assertEqual(runtime.consume_bundle(path,self.root,t+timedelta(seconds=2))['status'],'ALREADY_PROCESSED')
        report=json.loads((self.root/runtime.RELATIVE_DIR/'latest.json').read_text())
        self.assertEqual(len(report['portfolios']['baseline']['positions']),2)
        self.assertEqual(len(report['portfolios']['moderate_delta_iv']['positions']),1)
        self.assertIn('SIMULATED',report['assumptions']['fills'])
        self.assertTrue((self.root/runtime.RELATIVE_DIR/'latest.md').exists())
        # No canonical production portfolio/journal/account state is created.
        self.assertFalse((self.root/'data/paper_portfolio.csv').exists())
        self.assertFalse((self.root/'data/trade_journal.csv').exists())
        before=runtime.fingerprint(self.root)
        self.root.joinpath('src/config.py').write_bytes(b'FROZEN=1\r\n')
        self.assertEqual(runtime.fingerprint(self.root),before)
        (self.root/'src/schwab').mkdir()
        self.root.joinpath('src/schwab/manual_auth_fixture.py').write_text('AUTH_FIXTURE=True\n')
        self.assertEqual(runtime.fingerprint(self.root),before)
        self.root.joinpath('src/config.py').write_text('FROZEN=2\n')
        t+=timedelta(minutes=1);path=self.write_bundle(t,bundle(t))
        with self.assertRaises(ValueError):runtime.consume_bundle(path,self.root,t+timedelta(seconds=1))

    def test_collector_prioritizes_extra_shadow_contract_and_consumes_saved_bundle(self):
        runtime.capture_daily(self.csv,self.root,AT)
        t=AT+timedelta(minutes=1);calls=[]
        def fetch(symbols,**kwargs):
            calls.append(symbols)
            return {s:{'realtime':True,'quote':{'bidPrice':2.9,'askPrice':2.98,'quoteTime':t.timestamp()*1000,'volatility':30}} for s in symbols}
        # Existing research symbol retains coverage; an unjournaled comparison
        # contract is inserted and prioritized without dropping the universe.
        (self.root/'quotes').mkdir()
        tracked={'LEGACY':{'contract_symbol':'LEGACY','recommendations':[]}}
        with patch.object(collector,'ROOT',self.root),patch.object(collector,'tracked_contracts',return_value=(tracked,0)):
            collector._collect(self.root/'unused.csv',self.root/'quotes',fetch,t,True,collector.session_bounds(t),30,50,__import__('time').monotonic)
        self.assertIn('OTHER 261218C00100000',calls[0]);self.assertIn('TEST  261218C00100000',calls[0])
        self.assertIn('LEGACY',[s for call in calls for s in call])
        report=json.loads((self.root/runtime.RELATIVE_DIR/'latest.json').read_text())
        self.assertEqual(len(report['portfolios']['baseline']['positions']),2)

    def test_failed_processing_retains_raw_bundle_and_persistent_health(self):
        runtime.capture_daily(self.csv,self.root,AT)
        self.root.joinpath('src/config.py').write_text('CHANGED=1\n')
        t=AT+timedelta(minutes=1);(self.root/'quotes').mkdir()
        response={'realtime':True,'quote':{'bidPrice':2.9,'askPrice':2.98,'quoteTime':t.timestamp()*1000}}
        with patch.object(collector,'ROOT',self.root),patch.object(collector,'tracked_contracts',return_value=({},0)):
            collector._collect(self.csv,self.root/'quotes',lambda symbols,**kw:{s:response for s in symbols},t,True,collector.session_bounds(t),30,50,__import__('time').monotonic)
        self.assertTrue(list((self.root/'quotes').glob('*/*.gz')))
        health=json.loads((self.root/runtime.RELATIVE_DIR/'health_latest.json').read_text())
        self.assertEqual(health['status'],'FAILED_UPDATE')
        ledger=ComparisonLedger(self.root/runtime.RELATIVE_DIR/'ledger.sqlite')
        try:self.assertEqual(ledger.load()['portfolios']['baseline']['cash'],15000)
        finally:ledger.close()

    def test_invalid_initial_source_does_not_start_a_comparison(self):
        with self.assertRaises(ValueError):runtime.capture_daily(self.csv,self.root,AT+timedelta(minutes=31))
        self.assertFalse((self.root/runtime.RELATIVE_DIR/'ledger.sqlite').exists())

    def test_stale_daily_decision_waits_and_is_applied_after_fresh_quotes(self):
        runtime.capture_daily(self.csv,self.root,AT)
        t=AT+timedelta(minutes=1)
        path=self.write_bundle(t,bundle(t,bid=2.9,ask=2.98));runtime.consume_bundle(path,self.root,t+timedelta(seconds=1))
        t=AT+timedelta(days=1);source=self.root/'next_day.csv';candidates(t).to_csv(source,index=False)
        self.assertEqual(runtime.capture_daily(source,self.root,t)['status'],'DEFERRED_FOR_FRESH_HOLDING_QUOTES')
        report=json.loads((self.root/runtime.RELATIVE_DIR/'latest.json').read_text())
        self.assertIsNotNone(report['deferred_daily_decision'])
        t+=timedelta(minutes=1);path=self.write_bundle(t,bundle(t,bid=2.9,ask=2.98));runtime.consume_bundle(path,self.root,t+timedelta(seconds=1))
        report=json.loads((self.root/runtime.RELATIVE_DIR/'latest.json').read_text())
        self.assertIsNone(report['deferred_daily_decision'])
        ledger=ComparisonLedger(self.root/runtime.RELATIVE_DIR/'ledger.sqlite')
        try:self.assertTrue(ledger.db.execute("SELECT 1 FROM inputs WHERE kind='DAILY_DECISION' AND key='next_day.csv'").fetchone())
        finally:ledger.close()

    def test_priority_only_path_avoids_reading_large_journal(self):
        runtime.capture_daily(self.csv,self.root,AT)
        t=AT+timedelta(minutes=1);(self.root/'quotes').mkdir()
        response={'realtime':True,'quote':{'bidPrice':2.9,'askPrice':2.98,'quoteTime':t.timestamp()*1000}}
        with patch.object(collector,'ROOT',self.root),patch.object(collector,'tracked_contracts',side_effect=AssertionError('journal must not be read')):
            result=collector._collect(self.root/'unused.csv',self.root/'quotes',lambda symbols,**kw:{s:response for s in symbols},t,True,collector.session_bounds(t),10,50,__import__('time').monotonic,priority_only=True)
        self.assertTrue(result['comparison_priority_only'])
        self.assertEqual(result['status'],'PRIORITY_ONLY_OBSERVED')
        self.assertEqual(result['contracts_tracked'],2)

    def test_limit_touch_fills_at_limit_without_slipping_above_it(self):
        runtime.capture_daily(self.csv,self.root,AT)
        t=AT+timedelta(minutes=1);path=self.write_bundle(t,bundle(t,bid=2.9,ask=3.))
        runtime.consume_bundle(path,self.root,t+timedelta(seconds=1))
        report=json.loads((self.root/runtime.RELATIVE_DIR/'latest.json').read_text())
        self.assertEqual(report['portfolios']['baseline']['positions'][0]['entry'],3.)

    def test_disabled_runtime_has_no_side_effects(self):
        p=self.root/'research/six_week_20261029/activation.json';p.write_text('{"enabled":false}')
        self.assertEqual(runtime.capture_daily(self.csv,self.root,AT),{'status':'DISABLED'})
        self.assertEqual(runtime.priority_contracts(self.root,AT),{})
        self.assertFalse((self.root/runtime.RELATIVE_DIR).exists())


if __name__=='__main__':unittest.main()
