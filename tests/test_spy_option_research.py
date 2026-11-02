from datetime import timedelta
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import spy_option_research as spy
import intraday_option_paths as collector
from test_shadow_option_ledger import AT, candidates


class SpyResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        p = self.root/spy.SETTINGS
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'enabled': True, 'start_date': '2026-11-02', 'holding_days': 7, 'minimum_dte': 45, 'initial_capital': 15000}))
        manifest = self.root/'research/six_week_20261029/release_manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'spy_expected_initial_fingerprint': spy.policy_fingerprint(self.root)}))
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def history(self):
        return [{'Close': 100, 'High': 101, 'Low': 99, 'Volume': 100000} for _ in range(210)]

    def select(self, **kwargs):
        self.calls.append(kwargs)
        side = 'P' if 'Put' in kwargs['opportunity_type'] else 'C'
        return {'contractSymbol': 'SPY   261218'+side+'00600000', 'Expiration': '2026-12-18',
                'bid': 5, 'ask': 5.1, 'broker_delta': .4, 'implied_volatility': .25}

    def run_capture(self, **kwargs):
        return spy.capture(self.root, now=AT, history=self.history, selector=self.select,
                           evaluate=lambda f: {'Direction': 'Bullish', 'ResearchScore': 80},
                           candidate_builder=self.build, **kwargs)

    def build(self, root, record, now):
        frame = candidates(at=now)
        frame['ticker'] = 'SPY'
        frame['contract_symbol'] = 'SPY   261218C00600000'
        frame['execution_entry_price'] = 5.1
        frame['stop_loss_price'] = 4.2
        frame['profit_target_price'] = 7.5
        if record['selections'][0]['status'] != 'SELECTED':
            frame['action'] = 'Watch'
        return frame

    def test_two_sided_selection_idempotent_and_isolated(self):
        self.assertEqual(self.run_capture()['status'], 'CAPTURED')
        self.assertEqual(len(self.calls), 2)
        watch = spy.watch_contracts(self.root, AT)
        self.assertEqual(len(watch), 2)
        path = next((self.root/spy.DIRECTORY/'selections').glob('*.json'))
        before = path.read_bytes()
        self.assertEqual(self.run_capture()['status'], 'ALREADY_CAPTURED')
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(path.read_bytes(), before)
        for name in ['paper_portfolio.csv', 'trade_journal.csv', 'capital_ledger.csv']:
            self.assertFalse((self.root/'data'/name).exists())
        self.assertTrue(all(w['recommendations'][0]['allocation_decision'] == 'RESEARCH_ONLY_NOT_ALLOCATED' for w in watch.values()))

    def test_nullable_live_contract_metadata_serializes_without_changing_selection(self):
        import pandas as pd
        def nullable_selector(**kwargs):
            return dict(self.select(**kwargs), optional_provider_field=pd.NA,
                        nested_metadata={'missing': pd.NA, 'timestamp': pd.Timestamp('2026-11-02T15:30:00Z')},
                        unavailable_date=pd.NaT)
        result = spy.capture(self.root, now=AT, history=self.history, selector=nullable_selector,
                             evaluate=lambda f: {'Direction': 'Bullish', 'optional': pd.NA}, candidate_builder=self.build)
        self.assertEqual(result['status'], 'CAPTURED')
        record = json.loads(Path(result['source']).read_text())
        self.assertIsNone(record['signal']['optional'])
        for selection in record['selections']:
            self.assertEqual(selection['status'], 'SELECTED')
            self.assertIsNone(selection['contract']['optional_provider_field'])
            self.assertIsNone(selection['contract']['unavailable_date'])
            self.assertIsNone(selection['contract']['nested_metadata']['missing'])
            self.assertEqual(selection['contract']['nested_metadata']['timestamp'], '2026-11-02T15:30:00+00:00')

    def test_missing_required_quote_remains_rejected_after_serialization_fix(self):
        import pandas as pd
        def invalid(**kwargs):
            return dict(self.select(**kwargs), bid=pd.NA)
        with self.assertRaises(ValueError):
            spy.capture(self.root, now=AT, history=self.history, selector=invalid,
                        evaluate=lambda f: {}, candidate_builder=self.build)
        self.assertFalse((self.root/spy.DIRECTORY/'ledger.sqlite').exists())

    def test_no_eligible_contract_is_evidence_not_fake_selection(self):
        spy.capture(self.root, now=AT, history=self.history, selector=lambda **k: None, evaluate=lambda f: {}, candidate_builder=self.build)
        self.assertEqual(spy.watch_contracts(self.root, AT), {})
        record = json.loads(next((self.root/spy.DIRECTORY/'selections').glob('*.json')).read_text())
        self.assertTrue(all(x['status'] == 'NO_ELIGIBLE_CONTRACT' for x in record['selections']))

    def test_short_dte_and_missing_history_fail_without_publishing(self):
        with self.assertRaises(ValueError):
            spy.capture(self.root, now=AT, history=lambda: [], selector=self.select)
        def bad(**kwargs):
            return dict(self.select(**kwargs), Expiration='2026-11-20')
        with self.assertRaises(ValueError):
            spy.capture(self.root, now=AT, history=self.history, selector=bad, evaluate=lambda f: {})
        self.assertFalse((self.root/spy.DIRECTORY/'watch.json').exists())

    def test_off_hours_never_fetches(self):
        result = spy.capture(self.root, now=AT-timedelta(days=1), history=lambda: self.fail('No Sunday fetch'))
        self.assertEqual(result['status'], 'AWAITING_START_DATE')
        self.assertFalse((self.root/spy.DIRECTORY).exists())

    def test_intraday_priority_comparison_then_spy_without_journal(self):
        self.run_capture()
        calls = []
        def fetch(symbols, timeout_seconds):
            calls.extend(symbols)
            return {s: {'realtime': True, 'quote': {'bidPrice': 5, 'askPrice': 5.1, 'quoteTime': AT.timestamp()*1000}} for s in symbols}
        with patch.object(collector, 'ROOT', self.root), patch('shadow_comparison_runtime.priority_contracts', return_value={}), patch('shadow_comparison_runtime.consume_bundle', return_value={}):
            result = collector.collect_intraday('absent.csv', self.root/'bundles', now=AT,
                                                priority_only=True, fetch=fetch)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['status'], 'PRIORITY_ONLY_OBSERVED')
        with gzip.open(next((self.root/'bundles').glob('*/*.gz')), 'rt') as handle:
            record = json.load(handle)
        self.assertTrue(all(c['research_test'] == spy.VERSION for c in record['contracts']))
        summary = spy.research_status(self.root, AT)
        self.assertEqual(summary['latest_quote_health']['valid_contract_minutes'], 2)
        self.assertIsNotNone(summary['portfolio'])
        spy.record_quote_health(self.root, record, next((self.root/'bundles').glob('*/*.gz')))
        self.assertEqual(spy.research_status(self.root, AT)['latest_quote_health']['valid_contract_minutes'], 2)

    def test_single_spy_book_quote_fills_and_stop_use_existing_engine(self):
        self.run_capture()
        path = self.root/'sample.json.gz'
        def send(at, bid, ask):
            point = {'contract_symbol': 'SPY   261218C00600000', 'quote_at': at.isoformat(),
                     'observed_at': at.isoformat(), 'realtime': True,
                     'quote_status': 'OBSERVED', 'bid': bid, 'ask': ask}
            with gzip.open(path, 'wt') as handle:
                json.dump({'observations': [point]}, handle)
            return spy.consume_bundle(path, self.root, at)
        send(AT+timedelta(minutes=1), 5, 5.1)
        first = json.loads((self.root/spy.DIRECTORY/'portfolio_latest.json').read_text())
        self.assertEqual(set(first['portfolios']), {'baseline'})
        self.assertEqual(len(first['portfolios']['baseline']['positions']), 1)
        # New raw source identity for the next immutable bundle.
        path = self.root/'stop.json.gz'
        send(AT+timedelta(minutes=2), 4.1, 4.2)
        final = json.loads((self.root/spy.DIRECTORY/'portfolio_latest.json').read_text())
        self.assertEqual(final['portfolios']['baseline']['closed_round_trips'], 1)
        self.assertLess(final['portfolios']['baseline']['total_net_pnl'], 0)
        self.assertFalse((self.root/'data/processed/configuration_comparison/ledger.sqlite').exists())
        state = final
        self.assertEqual(spy.consume_bundle(path, self.root, AT+timedelta(minutes=2))['status'], 'ALREADY_PROCESSED')
        self.assertEqual(json.loads((self.root/spy.DIRECTORY/'portfolio_latest.json').read_text()), state)

    def test_spy_policy_change_cannot_silently_reuse_account(self):
        self.run_capture()
        path = self.root/spy.SETTINGS
        config = json.loads(path.read_text());config['holding_days'] = 14
        path.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, 'policy changed'):
            self.run_capture()

    def test_real_pipeline_can_choose_no_trade_without_forcing_a_probe(self):
        directory = self.root/'data/processed'
        directory.mkdir(parents=True)
        candidates().to_csv(directory/'trade_recommendations_fixture.csv', index=False)
        record = {'holding_days_for_contract_fit': 7,
                  'signal': {'StrategyScore': 50, 'ResearchScore': 50, 'TrendScore': 50,
                             'MomentumScore': 20, 'LiquidityScore': 10,
                             'MomentumDirection': 'Neutral', 'Direction': 'Neutral',
                             'StrategyReasons': 'fixture'},
                  'selections': [{'side': 'Long Call', 'contract': self.select(ticker='SPY', opportunity_type='Long Call')},
                                 {'side': 'Long Put', 'contract': self.select(ticker='SPY', opportunity_type='Long Put')}]}
        with patch('trade_constructor.select_best_contract', side_effect=AssertionError('No extra chain request')):
            frame = spy.build_candidate(self.root, record, AT)
        self.assertIn(frame.iloc[0]['action'], ('Pass', 'Watch'))
        self.assertEqual(frame.iloc[0]['earnings_status'], 'NOT_APPLICABLE_ETF')
        self.assertEqual(frame.iloc[0]['ticker'], 'SPY')

    def test_real_pipeline_uses_only_signal_side_and_preserves_exit_plan(self):
        directory = self.root/'data/processed'
        directory.mkdir(parents=True)
        candidates().to_csv(directory/'trade_recommendations_fixture.csv', index=False)
        contract = dict(self.select(ticker='SPY', opportunity_type='Long Call'),
                        strike=600, mid=5.05, DTE=46, ContractScore=90,
                        FinalContractScore=90, HorizonFitScore=90, ExecutionScore=95,
                        ExecutionGrade='A', ResearchPrice=5.05, ExecutionEntryPrice=5.1,
                        ExecutionExitPrice=5, spread_pct=.02, SpreadDollars=.1,
                        option_open_interest=10000, openInterest=10000, volume=1000,
                        OptionVolume=1000, OptionOpenInterest=10000, theta=-.02)
        record = {'holding_days_for_contract_fit': 7,
                  'signal': {'StrategyScore': 90, 'ResearchScore': 90, 'TrendScore': 90,
                             'MomentumScore': 90, 'LiquidityScore': 30,
                             'MomentumDirection': 'Bullish', 'Direction': 'Bullish',
                             'StrategyReasons': 'fixture', 'ATR': 2, 'Price': 600},
                  'selections': [{'side': 'Long Call', 'contract': contract},
                                 {'side': 'Long Put', 'contract': None}]}
        with patch('trade_constructor.select_best_contract', side_effect=AssertionError('No extra chain request')):
            frame = spy.build_candidate(self.root, record, AT)
        row = frame.iloc[0]
        self.assertEqual(row['option_strategy'], 'Long Call')
        self.assertEqual(row['contract_symbol'], contract['contractSymbol'])
        self.assertLess(row['stop_loss_price'], row['execution_entry_price'])
        self.assertGreater(row['profit_target_price'], row['execution_entry_price'])
