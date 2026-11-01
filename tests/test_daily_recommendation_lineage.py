import sys,unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
import trade_journal as journal


class DailyLineageTests(unittest.TestCase):
    def fixture(self):
        trades=pd.DataFrame({'ticker':['AAA','BBB'],'action':['Watch','Watch'],'confidence':[50,60],'portfolio_score':[70,80]})
        research=pd.DataFrame({'Ticker':['AAA','BBB'],'Close':[100.,200.]})
        return trades,research
    def snapshot(self,row):
        return {'recommendation_id':'id-'+row['ticker'],'file_path':'fixture/'+row['ticker']+'.json','schema_version':1}
    def test_daily_output_receives_exact_committed_journal_ids_without_score_changes(self):
        trades,research=self.fixture();original=trades.copy(deep=True)
        with patch.object(journal,'ENABLE_JOURNAL_WRITES',True),patch.object(journal,'capture_policy_evidence',return_value={'PolicyEvidenceFingerprint':'fixture'}),patch.object(journal,'write_observation_snapshot',side_effect=self.snapshot),patch.object(journal,'_append_rows_to_journal') as append:
            self.assertEqual(journal.log_completed_observations(trades,research,{},{}),2)
            rows=append.call_args.args[0]
            self.assertEqual(trades.RecommendationID.tolist(),[r['RecommendationID'] for r in rows])
            self.assertEqual(trades.RecommendationDate.tolist(),[r['RecommendationDate'] for r in rows])
            self.assertTrue(trades.RecommendationDate.notna().all())
        pd.testing.assert_frame_equal(trades[original.columns],original)
    def test_failed_journal_commit_does_not_attach_false_lineage(self):
        trades,research=self.fixture();original=trades.copy(deep=True)
        with patch.object(journal,'ENABLE_JOURNAL_WRITES',True),patch.object(journal,'capture_policy_evidence',return_value={}),patch.object(journal,'write_observation_snapshot',side_effect=self.snapshot),patch.object(journal,'_append_rows_to_journal',side_effect=OSError('fixture')):
            with self.assertRaises(OSError):journal.log_completed_observations(trades,research,{}, {})
        pd.testing.assert_frame_equal(trades,original)


if __name__=='__main__':unittest.main()
