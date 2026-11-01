import json
from datetime import timedelta
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from experiment_reporting import build_comparison, comparison_markdown
from shadow_option_ledger import ComparisonLedger
from test_shadow_option_ledger import AT, candidates, bundle


class ReportingTests(unittest.TestCase):
    def test_not_started_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(build_comparison(tmp, AT)['status'], 'NOT_STARTED')
            self.assertFalse((Path(tmp)/'data').exists())
            self.assertIn('No matched forward return', comparison_markdown(build_comparison(tmp, AT)))

    def test_paired_returns_costs_and_explanations_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = ComparisonLedger(root/'data/processed/configuration_comparison/ledger.sqlite')
            ledger.initialize(AT)
            ledger.capture_daily('day', candidates(extra=True), AT, fingerprint='fixture', source_hash='x')
            at = AT+timedelta(minutes=1)
            points = bundle(at, bid=2.9, ask=2.98)
            points['observations'].append(dict(points['observations'][0], contract_symbol='OTHER 261218C00100000'))
            ledger.process_bundle('q', points, at, fingerprint='fixture')
            before = ledger.load()
            report = build_comparison(root, at)
            self.assertEqual(report['status'], 'OBSERVING')
            for window in report['periods'].values():
                a, b = window['baseline'], window['moderate_delta_iv']
                self.assertAlmostEqual(window['challenger_minus_control']['net_pnl'], b['net_pnl']-a['net_pnl'])
                for p in (a, b):
                    self.assertAlmostEqual(p['net_pnl'], p['realized_net_change']+p['unrealized_net_change'])
            self.assertEqual(len(report['selection_overlap_since_start']['control_only']), 1)
            self.assertEqual(ledger.load(), before)
            text = comparison_markdown(report, detailed=True)
            self.assertIn('Selection and allocation evidence', text)
            self.assertIn('Sampled quote-touch', text)
            self.assertTrue(report['coverage']['valid_contract_minutes'])
            ledger.close()

    def test_prior_week_not_reported_as_current_week(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = ComparisonLedger(root/'data/processed/configuration_comparison/ledger.sqlite')
            ledger.initialize(AT)
            ledger.capture_daily('day', candidates(), AT, fingerprint='fixture', source_hash='x')
            report = build_comparison(root, AT+timedelta(days=7))
            self.assertNotIn('this_week', report['periods'])
            self.assertIn('since_start', report['periods'])
            self.assertEqual(report['current_week_status'], 'AWAITING_CURRENT_WEEK_OBSERVATIONS')
            ledger.close()

    def test_non_forward_fixture_not_presented_as_forward_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ComparisonLedger(Path(tmp)/'data/processed/configuration_comparison/ledger.sqlite')
            ledger.initialize(AT, mode='HISTORICAL_FIXTURE')
            self.assertEqual(build_comparison(tmp, AT)['status'], 'NON_FORWARD_DATA_NOT_COMPARABLE')
            ledger.close()
