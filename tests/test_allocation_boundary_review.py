from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import allocation_boundary_review as m


def candidate():
    return dict(ticker='TEST',action='Evaluate Options',option_strategy='Long Call',expiration='2027-01-15',
        strike=100,contracts=2,execution_entry_price=5,premium=5,portfolio_score=69,execution_score=85,
        stop_loss_price=4,earnings_status='CONFIRMED',earnings_allocation_override=False)


class AllocationBoundaryTests(unittest.TestCase):
    def test_soft_score_failure_is_not_conflated_with_execution_or_entry_data_failure(self):
        r=candidate();asset,reason=m.viability(r,[],15000)
        self.assertIsNone(reason)
        self.assertEqual(asset['contracts'],2)
        self.assertIsNotNone(m.viability(dict(r,execution_score=60),[],15000)[1])
        self.assertEqual(m.viability(dict(r,OpeningHourBlocked=True),[],15000)[1],'OPENING_HOUR_BLOCK')

    def test_score_includes_recorded_marginal_penalty_and_entry_hurdle(self):
        self.assertEqual(m.score(dict(portfolio_score=74,portfolio_correlation_penalty=3)),69)

    def test_held_exposure_prevents_claiming_an_unaffordable_extra_contract(self):
        r=dict(candidate(),portfolio_score=90)
        held=[dict(ticker='TEST',contracts=2,current_price=5,entry_price=5)]
        self.assertIn('invalid contract quantity',m.viability(r,held,15000)[1])

    def test_option_snapshot_diagnostics_are_not_actual_trade_profit(self):
        r=m.quote_diagnostic((1,1,1.9,2.1),(2,2,2.4,2.6))
        self.assertAlmostEqual(r['midpoint_price_change_per_contract'],50)
        self.assertAlmostEqual(r['bidask_friction_sensitivity_per_contract'],30)
        self.assertIn('not fills',r['basis'])
        self.assertIsNone(m.quote_diagnostic(None,(2,2,2.4,2.6)))

    def test_missing_actual_and_quote_outcomes_are_not_zero_profit(self):
        row=dict(effective_score=69,side='below',date='20261124',quote_diagnostics={})
        result=m.summary([row],5)['below']
        self.assertIsNone(result['actual_executed_net'])
        self.assertIsNone(result['option_quote_diagnostics']['3']['midpoint_change_one_contract_each'])
        self.assertEqual(result['option_quote_diagnostics']['3']['unresolved_timing'],1)


if __name__=='__main__':unittest.main()
