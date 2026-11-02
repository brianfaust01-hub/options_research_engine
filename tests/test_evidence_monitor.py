from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from evidence_monitor import compare_windows, outcome_reviews, build_monitor, publish, shadow_reviews
from shadow_option_ledger import ComparisonLedger
from test_shadow_option_ledger import AT, candidates


class MonitorTests(unittest.TestCase):
    def returns(self, early=.02, late=-.03):
        dates = pd.bdate_range('2026-09-24', periods=18)
        return pd.DataFrame([{'date': d.date().isoformat(), 'return': early if i < 13 else late}
                             for i, d in enumerate(dates) for _ in range(6)])

    def raw(self, split_policy=False):
        f = self.returns()
        rows = []
        for i, row in f.iterrows():
            rows.append({'RecommendationID': str(i), 'RecommendationDate': row['date']+'T10:30:00',
                         'Ticker': 'T'+str(i), 'Direction': 'BULLISH', 'Action': 'Evaluate Options',
                         'OpportunityType': 'Long Call Candidate', 'OptionStrategy': 'Long Call',
                         'PolicyEraID': 'PE-2026-09-08', 'PolicyEvidenceFingerprint': 'A' if not split_policy or i < 54 else 'B',
                         'ResearchScore': 80+i%6, 'MarketRegime': 'Bullish',
                         'Horizon7DStatus': 'COMPLETE', 'Horizon7DEvaluationDate': row['date'],
                         'Horizon7DDirectionalReturnPct': row['return']})
        return pd.DataFrame(rows)

    def test_detects_clear_decline_with_disjoint_date_windows(self):
        result = compare_windows(self.returns())
        self.assertEqual(result['status'], 'REVIEW_DETERIORATION')
        self.assertLess(result['date_cluster_95_interval'][1], 0)
        self.assertLess(result['reference']['last_date'], result['recent']['first_date'])

    def test_no_decline_is_not_proof_of_edge(self):
        result = compare_windows(self.returns(early=.01, late=.02))
        self.assertEqual(result['status'], 'NO_CLEAR_DETERIORATION')

    def test_repeated_rows_cannot_replace_independent_dates(self):
        f = pd.DataFrame([{'date': '2026-10-29', 'return': -.5}]*2000)
        self.assertEqual(compare_windows(f)['status'], 'INSUFFICIENT_EVIDENCE')

    def test_policy_versions_never_pooled_for_performance_alarm(self):
        data = self.raw(split_policy=True)
        result = outcome_reviews(data, AT)
        self.assertEqual(len(result['policy_cohorts']), 2)
        self.assertFalse(any(r['status'] == 'REVIEW_DETERIORATION' for r in result['comparisons']))
        combined = outcome_reviews(self.raw(), AT)
        self.assertTrue(any(r['status'] == 'REVIEW_DETERIORATION' for r in combined['comparisons']))

    def test_unknown_policy_and_future_outcomes_cannot_create_confidence(self):
        data = self.raw();data['PolicyEvidenceFingerprint'] = None
        result = outcome_reviews(data, AT)
        self.assertTrue(all(r['status'] in ('UNKNOWN_POLICY_NOT_COMPARABLE', 'DESCRIPTIVE_ONLY', 'INSUFFICIENT_EVIDENCE') for r in result['comparisons']))
        data['Horizon7DEvaluationDate'] = '2026-12-01'
        self.assertEqual(outcome_reviews(data, AT)['episodes'], 0)

    def test_price_basis_exclusion_applies_to_winners_and_losers(self):
        data = self.raw();data.loc[0:1, 'Ticker'] = 'CTVA'
        data.loc[0, 'Horizon7DDirectionalReturnPct'] = .5
        data.loc[1, 'Horizon7DDirectionalReturnPct'] = -.5
        result = outcome_reviews(data, AT)
        self.assertEqual(result['excluded_price_basis_rows'], 2)

    def test_missing_inputs_report_limitations_without_creating_trading_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = build_monitor(root, now=AT)
            self.assertEqual(value['status'], 'REVIEW_DATA')
            self.assertFalse((root/'data').exists())
            publish(root, now=AT)
            second = publish(root, now=AT)
            self.assertTrue(second['alert_changes']['ongoing_topics'])
            self.assertFalse(second['alert_changes']['new_topics'])
            files = [p for p in root.rglob('*') if p.is_file()]
            self.assertTrue(all('evidence_monitor' in p.parts for p in files))

    def test_shadow_reads_do_not_modify_inputs_orders_or_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = ComparisonLedger(root/'data/processed/configuration_comparison/ledger.sqlite')
            ledger.initialize(AT)
            ledger.capture_daily('d', candidates(), AT, fingerprint='fixture', source_hash='x')
            before = ledger.load()
            count = ledger.db.execute('SELECT count(*) FROM inputs').fetchone()[0]
            values = shadow_reviews(root, AT+timedelta(minutes=10))
            self.assertEqual(ledger.load(), before)
            self.assertEqual(ledger.db.execute('SELECT count(*) FROM inputs').fetchone()[0], count)
            self.assertTrue(all(v['performance_comparisons'][0]['status'] == 'INSUFFICIENT_EVIDENCE'
                                for v in values if v['status'] == 'OBSERVING'))
            ledger.close()

    def test_sidecar_timeout_cannot_send_email_or_change_experiment(self):
        import daily_run
        import subprocess
        with patch.object(daily_run.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixture', 45)), \
             patch.object(daily_run, 'send_email_report') as email, patch('builtins.print'):
            daily_run.refresh_evidence_monitor()
        email.assert_not_called()
