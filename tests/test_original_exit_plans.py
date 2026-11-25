from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import paper_portfolio
from original_exit_plans import restore_original_plans
from position_review import _resolve_exit_rules


def position():
    return dict(PositionID='P1',RecommendationID='R1',Ticker='WFC',OptionStrategy='Long Put',
        Expiration='2027-01-15',Strike=82.5,EntryPremium=4.35,EntryDate='2026-11-18T11:19:20',
        Status='OPEN',Contracts=2,RecommendedStop=4.25)


def recommendation():
    return dict(RecommendationID='R1',RecommendationDate='2026-11-18T10:39:32',ticker='WFC',
        expiration='2027-01-15',strike=82.5,option_strategy='Long Put',profit_target_price=6.02,
        stop_loss_price=3.61,time_stop_dte=14)


class OriginalExitPlanTests(unittest.TestCase):
    def test_original_target_replaces_missing_plan_not_entry_times_75_percent(self):
        f=restore_original_plans(pd.DataFrame([position()]),journal_rows=[recommendation()])
        target,stop,dte=_resolve_exit_rules(f.iloc[0].to_dict())
        self.assertEqual((target,stop,dte),(6.02,3.61,14))
        self.assertEqual(f.iloc[0].RecommendedStop,4.25)

    def test_newer_ticker_recommendation_cannot_retarget_existing_contract(self):
        newer=dict(recommendation(),RecommendationID='R2',profit_target_price=9.99)
        f=restore_original_plans(pd.DataFrame([position()]),journal_rows=[recommendation(),newer])
        self.assertEqual(f.iloc[0].ProfitTarget,6.02)

    def test_explicit_existing_levels_and_raised_stop_are_preserved(self):
        p=dict(position(),ProfitTarget=6.05,StopLoss=3.65,TimeStopDTE=12)
        f=restore_original_plans(pd.DataFrame([p]),journal_rows=[recommendation()])
        self.assertEqual(_resolve_exit_rules(f.iloc[0].to_dict()),(6.05,3.65,12))
        self.assertEqual(f.iloc[0].RecommendedStop,4.25)

    def test_ambiguous_or_wrong_contract_origin_is_not_inferred_by_ticker(self):
        for rows,status in (([recommendation(),dict(recommendation(),profit_target_price=10)],'CONFLICTING_ORIGIN_ID'),
                            ([dict(recommendation(),strike=90)],'ORIGIN_CONTRACT_MISMATCH')):
            f=restore_original_plans(pd.DataFrame([position()]),journal_rows=rows)
            self.assertEqual(f.iloc[0].ExitPlanStatus,status)
            self.assertTrue(pd.isna(f.iloc[0].ProfitTarget))

    def test_future_origin_is_not_used_and_closed_history_not_backfilled(self):
        f=restore_original_plans(pd.DataFrame([position()]),journal_rows=[dict(recommendation(),RecommendationDate='2026-11-19T10:00:00')])
        self.assertEqual(f.iloc[0].ExitPlanStatus,'ORIGIN_TIME_UNVERIFIED')
        f=restore_original_plans(pd.DataFrame([dict(position(),Status='CLOSED')]),journal_rows=[recommendation()])
        self.assertTrue(pd.isna(f.iloc[0].ProfitTarget))

    def test_load_recovers_plan_without_mutating_files(self):
        with TemporaryDirectory() as d:
            root=Path(d);path=root/'paper_portfolio.csv';journal=root/'trade_journal.csv'
            pd.DataFrame([position()]).to_csv(path,index=False)
            pd.DataFrame([recommendation()]).to_csv(journal,index=False)
            before=path.read_bytes(),journal.read_bytes()
            with patch.object(paper_portfolio,'PORTFOLIO_PATH',path):f=paper_portfolio.load_portfolio()
            self.assertEqual(f.iloc[0].ProfitTarget,6.02)
            self.assertEqual(before,(path.read_bytes(),journal.read_bytes()))

    def test_legacy_fallback_without_origin_remains_backward_compatible(self):
        p=dict(position(),RecommendationID=None)
        f=restore_original_plans(pd.DataFrame([p]),journal_rows=[recommendation()])
        self.assertEqual(f.iloc[0].ExitPlanStatus,'MISSING_ORIGIN_ID')
        self.assertEqual(_resolve_exit_rules(f.iloc[0].to_dict())[0],4.35*1.75)


if __name__=='__main__':unittest.main()
