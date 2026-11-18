from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from trade_filter_review import evaluate,keeps,block_interval


def t(pnl,feature,day='2026-10-01',qty=1):
    return {'id':str(pnl)+day,'ticker':'TEST','entry_date':day,'direction':'CALL',
        'quantity':qty,'net_pnl':pnl,'within_recorded_quantity_pnl':pnl,
        'features':{'implied_volatility':feature}}


class TradeFilterTests(unittest.TestCase):
    def test_saved_losses_are_offset_by_winners_forgone(self):
        rule=('IV','implied_volatility','le',.4)
        rows=[t(500,.5),t(-100,.5),t(200,.3)]
        result=evaluate(rows,rule,400)
        self.assertEqual(result['avoided_loss_dollars'],100)
        self.assertEqual(result['forgone_profit_dollars'],500)
        self.assertEqual(result['net_improvement'],-400)
        self.assertEqual(result['large_winners_retained'],0)

    def test_missing_features_kept_never_mined_as_benefit(self):
        rule=('IV','implied_volatility','le',.4)
        self.assertTrue(keeps(t(-100,None),rule))
        result=evaluate([t(-100,None),t(200,.3)],rule,150)
        self.assertEqual(result['net_improvement'],0)
        self.assertEqual(result['missing_feature_groups'],1)

    def test_remove_largest_avoided_loss_exposes_outlier(self):
        result=evaluate([t(-1000,.6),t(200,.3)],('IV','implied_volatility','le',.4),150)
        self.assertEqual(result['net_improvement'],1000)
        self.assertEqual(result['improvement_without_largest_avoided_loss'],0)

    def test_contract_sensitivity_not_confused_with_dollar_gains(self):
        result=evaluate([t(-300,.6,qty=3),t(200,.3)],('IV','implied_volatility','le',.4),150)
        self.assertEqual(result['one_contract_net_improvement'],100)
        self.assertEqual(result['net_improvement'],300)

    def test_cluster_uncertainty_is_reproducible_and_needs_dates(self):
        rule=('IV','implied_volatility','le',.4)
        self.assertIsNone(block_interval([t(100,.3)],rule))
        rows=[t(-100 if i%2 else 100,.6,f'2026-10-{i+1:02}') for i in range(9)]
        self.assertEqual(block_interval(rows,rule),block_interval(rows,rule))
        self.assertLess(block_interval(rows,rule)['low95'],0)
        self.assertGreater(block_interval(rows,rule)['high95'],0)


if __name__=='__main__':unittest.main()
