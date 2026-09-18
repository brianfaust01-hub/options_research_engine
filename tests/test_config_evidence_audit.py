import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from config_evidence_audit import audit, field_coverage, markdown, value

NOW = datetime(2026, 9, 18, 15, tzinfo=timezone.utc)


class ConfigEvidenceAuditTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'src').mkdir()
        (root / 'data' / 'processed' / 'option_observations').mkdir(parents=True)
        (root / 'src' / 'config.py').write_text('MIN_OPPORTUNITY_SCORE = 70\nTEST_MODE = False\nNEW_RISK_SETTING = 5\n')
        row = {'RecommendationID': 'R1', 'RecommendationDate': '2026-09-08T11:00:00',
            'PolicyEraID': 'PE-2026-09-08', 'Direction': 'BULLISH',
            'option_strategy': 'Long Call', 'expiration': '2026-11-20', 'strike': '100',
            'premium': '2', 'contract_symbol': 'A     261120C00100000',
            'ResearchScore': '0', 'market_regime': 'Unknown', 'allocation_decision': 'No Allocation'}
        data = [row, row.copy(), {**row, 'RecommendationID': 'OLD', 'PolicyEraID': 'LEGACY'},
                {**row, 'RecommendationID': 'FUTURE', 'RecommendationDate': '2026-09-25'},
                {**row, 'RecommendationID': 'R2', 'Direction': 'BEARISH', 'premium': '',
                 'contract_symbol': '', 'strike': '', 'expiration': ''}]
        self.write_csv(root / 'data' / 'trade_journal.csv', data)
        self.write_csv(root / 'data' / 'processed' / 'research_hindsight_fixture.csv', [
            {'RecommendationID': 'R1', 'Horizon7DStatus': 'COMPLETE',
             'Horizon7DDirectionalReturnPct': '0.02'},
            {'RecommendationID': 'R2', 'Horizon7DStatus': 'IN_PROGRESS',
             'Horizon7DDirectionalReturnPct': ''}])

    def write_csv(self, path, data):
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

    def test_actual_values_not_just_headers_and_zero_is_valid(self):
        result = field_coverage([{'ResearchScore': '0', 'RecommendationDate': '2026-09-08'},
            {'ResearchScore': 'nan'}, {'ResearchScore': ''}], 'ResearchScore')
        self.assertEqual(result['available'], 1)
        self.assertEqual(result['missing'], 2)
        self.assertEqual(result['first_available_date'], '2026-09-08')
        self.assertEqual(value({'ResearchScore': '', 'research_score': '80'}, 'ResearchScore'), '80')
        self.assertIsNone(value({'market_regime': 'Unknown'}, 'market_regime'))

    def test_policy_filters_deduplication_unmapped_and_immature(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            result = audit(root, now=NOW)
            self.assertEqual(result['population']['current_unique_recommendations'], 2)
            self.assertEqual(result['population']['duplicate_ids'], 1)
            self.assertEqual(result['population']['selected_contract'], 1)
            self.assertEqual(result['unmapped_settings'], ['NEW_RISK_SETTING'])
            self.assertEqual(result['outcomes']['7D']['complete_numeric'], 1)
            self.assertEqual(result['outcomes']['7D']['not_complete_or_not_in_latest_hindsight'], 1)
            self.assertFalse(result['production_policy_changed'])
            self.assertTrue(result['collection_is_not_calibration_readiness'])
            self.assertEqual(len(result['config_source_sha256']), 64)

    def test_complete_status_without_return_is_an_error_not_maturity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            self.write_csv(root / 'data' / 'processed' / 'research_hindsight_fixture.csv', [
                {'RecommendationID': 'R1', 'Horizon7DStatus': 'COMPLETE',
                 'Horizon7DDirectionalReturnPct': 'nan'}])
            result = audit(root, now=NOW)
            self.assertEqual(result['outcomes']['7D']['complete_numeric'], 0)
            self.assertEqual(result['outcomes']['7D']['complete_but_missing_return'], 1)

    def test_stale_quotes_do_not_count_as_usable_iv_or_returns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / 'data' / 'processed' / 'option_observations' / 'sample_fixture.json'
            quote = {'contract_symbol': 'A     261120C00100000',
                'recommendations': [{'recommendation_id': 'R1'}], 'quote_status': 'STALE_QUOTE',
                'eligible_for_sampled_returns': False, 'iv_decimal': .4, 'iv_status': 'STALE_QUOTE',
                'quote_at': '2026-09-17T20:00:00+00:00', 'bid': 2, 'ask': 2.1}
            path.write_text(json.dumps({'observations': [quote]}))
            result = audit(root, now=NOW)
            self.assertEqual(result['option_quotes']['usable_observations'], 0)
            self.assertEqual(result['option_quotes']['usable_iv_observations'], 0)
            self.assertIsNone(result['option_quotes']['first_usable_date'])
            quote.update(quote_status='OBSERVED', eligible_for_sampled_returns=True,
                         iv_status='OBSERVED', quote_at='2026-09-18T14:30:00+00:00')
            path.write_text(json.dumps({'observations': [quote]}))
            result = audit(root, now=NOW)
            self.assertEqual(result['option_quotes']['first_usable_date'], '2026-09-18')
            self.assertEqual(result['option_quotes']['usable_iv_observations'], 1)
            self.assertEqual(result['option_quotes']['intraday_exit_ordering'], 'NOT_VERIFIED_BY_DAILY_SNAPSHOTS')

    def test_audit_is_read_only_and_reports_corrupt_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            bad = root / 'data' / 'processed' / 'option_observations' / 'sample_bad.json'
            bad.write_text('invalid')
            before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result = audit(root, now=NOW)
            self.assertTrue(result['option_quotes']['artifact_issues'])
            text = markdown(result)
            self.assertIn('Daily quotes do not establish intraday', text)
            self.assertIn('COLLECTION_GAP', text)
            self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_empty_sources_never_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            (root / 'src' / 'config.py').write_text('MIN_OPPORTUNITY_SCORE = 70')
            result = audit(root, now=NOW)
            self.assertTrue(all(f['collection_status'] == 'NO_POPULATION' for f in result['families']))


if __name__ == '__main__':
    unittest.main()
