import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import asdict
from datetime import date, timedelta

import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from policy_evidence import capture_policy_evidence, RULE_FILES
from trade_constructor import construct_trade
from trade_journal import log_completed_observations, _build_completed_observation


class PolicyEvidenceTests(unittest.TestCase):
    def setup_root(self, root):
        (root / 'src').mkdir()
        for name in RULE_FILES:
            (root / 'src' / name).write_text('VALUE = 1\n')
        (root / 'src' / 'config.py').write_text(
            'MAX_POSITION_SIZE_PCT = .08\nMAX_POSITION_SIZE_PCT = .09\n'
            'POLICY_ERA_ID = "PE-2026-09-08"\nCLIENT_SECRET = "private-fixture"\n')

    def test_immutable_archive_and_no_config_secret_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.setup_root(root)
            first = capture_policy_evidence(root)
            artifact = root / first['PolicyEvidencePath']
            content = artifact.read_text()
            data = json.loads(content)
            self.assertEqual(first['PolicyEvidenceStatus'], 'CAPTURED')
            self.assertEqual(data['settings']['MAX_POSITION_SIZE_PCT'], .09)
            self.assertNotIn('private-fixture', content)
            self.assertNotIn('config.py', data['rule_sources'])
            self.assertEqual(capture_policy_evidence(root), first)
            self.assertEqual(artifact.read_text(), content)
            (root / 'src' / 'exit_rules.py').write_text('VALUE = 2\n')
            second = capture_policy_evidence(root)
            self.assertNotEqual(first['PolicyEvidenceFingerprint'], second['PolicyEvidenceFingerprint'])
            self.assertEqual(artifact.read_text(), content)

    def test_missing_source_is_partial_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.setup_root(root)
            (root / 'src' / 'exit_rules.py').unlink()
            self.assertEqual(capture_policy_evidence(root)['PolicyEvidenceStatus'], 'PARTIAL_RULE_COVERAGE')

    def test_scores_and_selection_evidence_flow_without_scoring_change(self):
        row = pd.Series({'Ticker': 'TEST', 'StrategyScore': 80, 'Confidence': 80,
            'TrendScore': 80, 'MomentumScore': 70, 'StrategyReasons': 'fixture',
            'HoldingPeriodDays': 45, 'OpportunityType': 'Long Call Candidate',
            'Action': 'Evaluate Options', 'OpportunityScore': 80, 'BullishScore': 80,
            'BearishScore': 0, 'DirectionalConviction': 80})
        contract = pd.Series({'contractSymbol': 'TEST', 'strike': 100, 'mid': 1,
            'Expiration': str(date.today() + timedelta(days=60)), 'DTE': 60,
            'ContractScore': 90, 'FinalContractScore': 95, 'HorizonFitScore': 85,
            'execution_entry_price': 1.1, 'execution_exit_price': .9,
            'selection_evidence_json': '[{"contractSymbol":"TEST"}]'})
        with patch('trade_constructor.select_best_contract', return_value=contract):
            trade = construct_trade(row)
        self.assertEqual(trade.contract_score, 90)
        self.assertEqual(trade.final_contract_score, 95)
        self.assertEqual(trade.horizon_fit_score, 85)
        # The original notes-based scoring input still exists and is unchanged.
        self.assertIn('Contract Score: 90', trade.notes)
        observation = _build_completed_observation(asdict(trade), {'Ticker': 'TEST', 'Close': 100}, {}, {}, '2026-09-18')
        self.assertEqual(observation['contract_score'], 90)
        self.assertEqual(observation['selection_evidence_json'], trade.selection_evidence_json)

    def test_journal_lineage_is_captured_once_per_scan_and_before_snapshot(self):
        captured = []
        def snapshot(observation):
            captured.append(observation.copy())
            return {'recommendation_id': 'R1', 'file_path': 'fixture', 'schema_version': '4.0'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.setup_root(root)
            with patch('trade_journal.PROJECT_ROOT', root), \
                 patch('trade_journal.write_observation_snapshot', side_effect=snapshot), \
                 patch('trade_journal._append_rows_to_journal'):
                count = log_completed_observations(pd.DataFrame([{'ticker': 'TEST', 'action': 'Watch'}]),
                    pd.DataFrame([{'Ticker': 'TEST', 'Close': 100}]), {}, {})
            self.assertEqual(count, 1)
            self.assertEqual(captured[0]['PolicyEvidenceStatus'], 'CAPTURED')
            self.assertEqual(len(captured[0]['PolicyEvidenceFingerprint']), 64)


if __name__ == '__main__':
    unittest.main()
