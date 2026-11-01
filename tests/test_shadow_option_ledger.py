import copy,json,sys,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from shadow_option_ledger import ComparisonLedger,trading_gap_seconds
from position_review import _review_single_position

AT=datetime(2026,11,2,15,36,tzinfo=timezone.utc)


def candidates(at=AT,extra=False):
    r={'RecommendationID':'a','RecommendationDate':at.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).replace(tzinfo=None).isoformat(),'ticker':'TEST','option_strategy':'Long Call','expiration':'2026-12-18','strike':100.,'contract_symbol':'TEST  261218C00100000','contracts':3,'execution_entry_price':3.,'stop_loss_price':2.4,'profit_target_price':4.2,'time_stop_dte':14,'portfolio_score':85.,'allocation_score':85.,'confidence':90,'execution_score':90.,'earnings_status':'VERIFIED','earnings_date':'2027-03-01','action':'Evaluate Options','opportunity_type':'Call Candidate','ResearchScore':95.,'theta_drag_pct_per_day':.005,'broker_delta':.4,'implied_volatility':.3,'expected_move_window_days':7,'market_regime':'Bullish','risk_mode':'Normal','breadth_regime':'Broad Participation'}
    rows=[r]
    if extra:rows.append(dict(r,RecommendationID='b',ticker='OTHER',contract_symbol='OTHER 261218C00100000',broker_delta=.8,implied_volatility=.5))
    return pd.DataFrame(rows)


def bundle(at,bid=2.9,ask=3.,**kwargs):
    point={'contract_symbol':'TEST  261218C00100000','observed_at':at.isoformat(),'quote_at':at.isoformat(),'realtime':True,'quote_status':'OBSERVED','bid':bid,'ask':ask}
    point.update(kwargs)
    return {'observations':[point]}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'ledger.sqlite';self.l=ComparisonLedger(self.path)
        self.l.initialize(AT,market_slippage=0,mode='FIXTURE')
        self.l.capture_daily('day1',candidates(),AT,fingerprint='fixture',source_hash='source1')
    def tearDown(self):self.l.close();self.tmp.cleanup()
    def send(self,key,minutes=1,bid=2.9,ask=3.,**kwargs):
        t=AT+timedelta(minutes=minutes)
        return self.l.process_bundle(key,bundle(t,bid,ask,**kwargs),t+timedelta(seconds=1),fingerprint='fixture')

    def test_ask_limit_then_bid_stop_costs_cash_and_oco(self):
        self.send('above',ask=3.01)
        self.assertEqual(len(self.l.snapshot()['portfolios']['baseline']['positions']),0)
        self.send('entry',minutes=2);self.send('stop',minutes=3,bid=2.3,ask=2.4)
        snap=self.l.snapshot()
        for p in snap['portfolios'].values():
            self.assertFalse(p['positions']);self.assertAlmostEqual(p['realized_net_pnl'],-214.2)
            self.assertAlmostEqual(p['nav'],14785.8);self.assertAlmostEqual(p['fees_paid'],4.2)
        self.send('later-target',minutes=4,bid=5,ask=5.1)
        self.assertAlmostEqual(self.l.snapshot()['portfolios']['baseline']['nav'],14785.8)

    def test_target_never_assumes_better_than_limit(self):
        self.send('entry');self.send('target',minutes=2,bid=4.5,ask=4.6)
        self.assertAlmostEqual(self.l.snapshot()['portfolios']['baseline']['realized_net_pnl'],355.8)

    def test_restart_duplicate_input_and_policy_fingerprint(self):
        self.send('entry');state=self.l.load();self.l.close();self.l=ComparisonLedger(self.path)
        t=AT+timedelta(minutes=1)
        self.assertFalse(self.l.process_bundle('entry',bundle(t),t+timedelta(seconds=2),fingerprint='fixture'))
        self.assertEqual(state,self.l.load())
        with self.assertRaises(ValueError):self.l.process_bundle('entry',bundle(t,bid=2.8),t+timedelta(seconds=2),fingerprint='fixture')
        with self.assertRaises(ValueError):self.l.process_bundle('changed-policy',bundle(t),t+timedelta(seconds=2),fingerprint='different')
        self.assertEqual(state,self.l.load())
        self.assertFalse(self.l.capture_daily('day1',candidates(),AT+timedelta(minutes=2),fingerprint='fixture',source_hash='source1'))
        with self.assertRaises(ValueError):self.l.initialize(AT)

    def test_stale_future_and_predecision_quotes_never_fill(self):
        t=AT+timedelta(minutes=1)
        self.send('stale',quote_at=(t-timedelta(seconds=61)).isoformat())
        self.send('future',minutes=2,quote_at=(t+timedelta(minutes=2)).isoformat())
        self.send('delayed',minutes=3,realtime=False)
        self.assertFalse(self.l.snapshot()['portfolios']['baseline']['positions'])
        self.assertEqual(self.l.load()['health']['invalid_quotes'],3)

    def test_stale_mark_blocks_new_allocation_and_missing_is_not_zero(self):
        self.send('entry')
        t=AT+timedelta(minutes=5)
        self.l.capture_daily('day2',candidates(t),t,fingerprint='fixture',source_hash='source2')
        snap=self.l.snapshot()
        self.assertTrue(snap['portfolios']['baseline']['stale_or_missing_marks'])
        self.assertEqual(snap['portfolios']['baseline']['positions'][0]['quantity'],3)
        self.assertTrue(self.l.db.execute("SELECT count(*) FROM events WHERE kind='ALLOCATION_SKIPPED_STALE_HOLDINGS'").fetchone()[0])

    def test_profit_ratchet_uses_shared_review_without_network(self):
        self.send('entry');self.send('gain',minutes=2,bid=3.7,ask=3.8)
        t=AT+timedelta(minutes=2,seconds=2)
        with patch('position_review._get_option_mark',side_effect=AssertionError('network')),patch('position_review.get_next_earnings_date',side_effect=AssertionError('network')):
            self.l.capture_daily('newreview',candidates(t),t,fingerprint='fixture',source_hash='newsource')
        lots=[l for l in self.l.load()['portfolios']['baseline']['lots'].values() if l['status']=='OPEN']
        self.assertGreater(lots[0]['stop'],3.)
        self.send('protected-stop',minutes=3,bid=3.1,ask=3.2)
        self.assertFalse(self.l.snapshot()['portfolios']['baseline']['positions'])

    def test_profile_changes_decisions_not_risk_or_account_seed(self):
        t=AT+timedelta(seconds=1)
        self.l.capture_daily('two',candidates(t,extra=True),t,fingerprint='fixture',source_hash='two')
        s=self.l.load();a=s['portfolios']['baseline'];b=s['portfolios']['moderate_delta_iv']
        pending=lambda p:[o for o in p['orders'].values() if o['status']=='PENDING']
        self.assertEqual(len(pending(a)),2);self.assertEqual(len(pending(b)),1)
        self.assertEqual(a['cash'],b['cash']);self.assertEqual(a['cash'],15000)
        self.assertLessEqual(self.l.pending_reserve(s,a),a['cash'])

    def test_expired_orders_cannot_fill_next_session(self):
        t=AT+timedelta(days=1)
        self.l.process_bundle('tomorrow',bundle(t),t+timedelta(seconds=1),fingerprint='fixture')
        self.assertFalse(self.l.snapshot()['portfolios']['baseline']['positions'])
        self.assertEqual(self.l.load()['portfolios']['baseline']['cash'],15000)

    def test_zero_bid_is_not_a_fabricated_fill_or_settlement(self):
        self.send('entry');self.send('zero',minutes=2,bid=0,ask=.01)
        p=self.l.snapshot()['portfolios']['baseline']
        self.assertEqual(p['positions'][0]['quantity'],3)
        self.assertAlmostEqual(p['realized_net_pnl'],0)
        self.assertEqual(self.l.load()['health']['zero_bid_observations'],1)
        self.send('executable-near-total-loss',minutes=3,bid=.01,ask=.02)
        p=self.l.snapshot()['portfolios']['baseline']
        self.assertAlmostEqual(p['realized_net_pnl'],-901.2)
        self.assertFalse(p['positions'])

    def test_partial_exit_keeps_remaining_bracket_and_reconciles_fees(self):
        self.send('entry')
        from types import SimpleNamespace
        t=AT+timedelta(minutes=1,seconds=2)
        def reduced(candidates_arg,positions_arg,**kwargs):
            pos=positions_arg.copy();pos['portfolio_target_contracts']=1;pos['portfolio_action_reason']='fixture reduction'
            cand=candidates_arg.copy();cand['portfolio_action']='PASS'
            return SimpleNamespace(positions=pos,candidates=cand,summary={})
        with patch('configuration_profile_shadow.allocate_profile',side_effect=reduced):
            self.l.capture_daily('reduce',candidates(t),t,fingerprint='fixture',source_hash='reduce')
        self.send('reduction-fill',minutes=2,bid=3.05,ask=3.1)
        p=self.l.snapshot()['portfolios']['baseline']
        self.assertEqual(p['positions'][0]['quantity'],1)
        self.assertAlmostEqual(p['realized_net_pnl'],7.2)
        self.send('remaining-stop',minutes=3,bid=2.3,ask=2.4)
        p=self.l.snapshot()['portfolios']['baseline']
        self.assertAlmostEqual(p['realized_net_pnl'],-64.2)
        self.assertFalse(p['positions'])

    def test_no_fills_using_quote_from_before_decision(self):
        t=AT+timedelta(seconds=1)
        self.l.process_bundle('predecision',bundle(t,quote_at=(AT-timedelta(seconds=1)).isoformat(),observed_at=(AT-timedelta(seconds=1)).isoformat()),t+timedelta(seconds=1),fingerprint='fixture')
        self.assertFalse(self.l.snapshot()['portfolios']['baseline']['positions'])

    def test_nav_history_export_and_no_duplicate_valuations(self):
        self.send('entry');before=self.l.db.execute('SELECT count(*) FROM valuations').fetchone()[0]
        self.send('entry');self.assertEqual(self.l.db.execute('SELECT count(*) FROM valuations').fetchone()[0],before)
        out=Path(self.tmp.name)/'exports';self.l.export(out)
        self.assertEqual(len(pd.read_csv(out/'simulated_fills.csv')),2)
        history=pd.read_csv(out/'nav_history.csv')
        self.assertEqual(set(history.portfolio),{'baseline','moderate_delta_iv'})
        self.assertTrue((out/'quote_coverage.csv').exists())

    def test_replacements_wait_for_filled_sales_and_recycle_actual_cash(self):
        l=ComparisonLedger(Path(self.tmp.name)/'full.sqlite');l.initialize(AT,market_slippage=0,mode='FIXTURE')
        try:
            base=candidates().iloc[0].to_dict()
            def rows(at,include_new=False):
                items=[]
                for i in range(10+(3 if include_new else 0)):
                    ticker=('OLD'+str(i)) if i<10 else ('NEW'+str(i-10))
                    score=85 if i<10 else 95
                    items.append(dict(base,RecommendationID=ticker,ticker=ticker,contract_symbol=ticker+' 261218C00100000',execution_entry_price=11.9,stop_loss_price=11.5,profit_target_price=15.,portfolio_score=score,allocation_score=score,RecommendationDate=at.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).replace(tzinfo=None).isoformat()))
                return pd.DataFrame(items)
            def quotes(at,frame):
                return {'observations':[dict(bundle(at,bid=11.8,ask=11.9)['observations'][0],contract_symbol=r.contract_symbol) for _,r in frame.iterrows()]}
            first=rows(AT);l.capture_daily('first',first,AT,fingerprint='fixture',source_hash='first')
            t=AT+timedelta(minutes=1);l.process_bundle('filled-first',quotes(t,first),t+timedelta(seconds=1),fingerprint='fixture')
            self.assertEqual(len(l.snapshot()['portfolios']['baseline']['positions']),10)
            t+=timedelta(seconds=2);second=rows(t,True);l.capture_daily('rotate',second,t,fingerprint='fixture',source_hash='rotate')
            state=l.load();pending=state['portfolios']['baseline']['orders'].values()
            self.assertTrue(any(o.get('funding_status')=='WAITING_FOR_CASH' and o['status']=='PENDING' for o in pending))
            cash=state['portfolios']['baseline']['cash']
            t=AT+timedelta(minutes=2);new=second[second.ticker.str.startswith('NEW')]
            l.process_bundle('new-before-sales',quotes(t,new),t+timedelta(seconds=1),fingerprint='fixture')
            self.assertAlmostEqual(l.snapshot()['portfolios']['baseline']['cash'],cash)
            t=AT+timedelta(minutes=3);l.process_bundle('sales',quotes(t,second),t+timedelta(seconds=1),fingerprint='fixture')
            t=AT+timedelta(minutes=4);l.process_bundle('recycled',quotes(t,second),t+timedelta(seconds=1),fingerprint='fixture')
            p=l.snapshot()['portfolios']['baseline']
            self.assertEqual(len(p['positions']),10)
            self.assertEqual(sum(x['ticker'].startswith('NEW') for x in p['positions']),3)
            self.assertGreaterEqual(p['cash'],0)
        finally:l.close()

    def test_gap_clock_excludes_closed_hours_and_includes_missed_sessions(self):
        self.assertEqual(trading_gap_seconds('2026-11-06T15:59:00-05:00','2026-11-09T09:31:00-05:00'),120)
        self.assertEqual(trading_gap_seconds('2026-11-02T15:59:00-05:00','2026-11-04T09:31:00-05:00'),23520)
        self.assertEqual(trading_gap_seconds('2026-11-25T15:59:00-05:00','2026-11-27T09:31:00-05:00'),120)
        self.assertEqual(trading_gap_seconds('2026-11-27T12:59:00-05:00','2026-11-30T09:31:00-05:00'),120)

    def test_fresh_unchanged_quote_observed_after_decision_can_fill(self):
        t=AT+timedelta(seconds=10)
        self.l.process_bundle('unchanged',bundle(t,quote_at=(AT-timedelta(seconds=1)).isoformat()),t+timedelta(seconds=1),fingerprint='fixture')
        self.assertTrue(self.l.snapshot()['portfolios']['baseline']['positions'])

    def test_approved_add_is_incremental_and_never_exceeds_contract_cap(self):
        l=ComparisonLedger(Path(self.tmp.name)/'add.sqlite');l.initialize(AT,market_slippage=0,mode='FIXTURE')
        try:
            first=candidates();first['contracts']=1;first['portfolio_score']=75;first['allocation_score']=75
            l.capture_daily('first',first,AT,fingerprint='fixture',source_hash='first')
            t=AT+timedelta(minutes=1);l.process_bundle('first-fill',bundle(t),t+timedelta(seconds=1),fingerprint='fixture')
            self.assertEqual(sum(p['quantity'] for p in l.snapshot()['portfolios']['baseline']['positions']),1)
            t+=timedelta(seconds=2);second=candidates(t);second['contracts']=1;second['portfolio_score']=95;second['allocation_score']=95
            l.capture_daily('add',second,t,fingerprint='fixture',source_hash='add')
            t=AT+timedelta(minutes=2);l.process_bundle('add-fill',bundle(t),t+timedelta(seconds=1),fingerprint='fixture')
            self.assertEqual(sum(p['quantity'] for p in l.snapshot()['portfolios']['baseline']['positions']),3)
        finally:l.close()

    def test_aware_dates_and_closed_session_required(self):
        with self.assertRaises(ValueError):self.l.capture_daily('bad',candidates(),AT.replace(tzinfo=None),fingerprint='fixture',source_hash='x')
        with self.assertRaises(ValueError):self.l.capture_daily('night',candidates(),AT.replace(hour=23),fingerprint='fixture',source_hash='x')


if __name__=='__main__':unittest.main()
