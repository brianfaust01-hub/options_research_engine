import unittest
import pandas as pd
from test_portfolio_arbitrator import candidate, position
from portfolio_arbitrator import arbitrate_portfolio
from production_risk_controls import arbitrate_with_oil_guard, oil_linked
from configuration_profile_shadow import allocate_profile


class OilRiskTests(unittest.TestCase):
    def test_broad_coverage_and_metadata(self):
        for ticker in ['XOM','CVX','DVN','COP','EOG','SLB','HAL','KMI','VLO','MPC','XLE']:
            self.assertTrue(oil_linked({'ticker':ticker}))
        self.assertTrue(oil_linked({'ticker':'UNMAPPED','industry':'Oil & Gas Exploration'}))
        self.assertFalse(oil_linked({'ticker':'RTX'}))

    def test_only_one_new_name_and_shadow_restores_original_choices(self):
        rows=pd.DataFrame([candidate('XOM',99),candidate('CVX',98),candidate('KO',97)])
        original=rows.copy(deep=True)
        result=arbitrate_with_oil_guard(arbitrate_portfolio,rows,pd.DataFrame(),15000)
        allocated=result.candidates.query("allocation_decision == 'Allocate'").ticker.tolist()
        self.assertIn('XOM',allocated)
        self.assertNotIn('CVX',allocated)
        self.assertIn('KO',allocated)
        self.assertEqual(result.candidates.loc[1,'action'],'Evaluate Options')
        self.assertTrue(result.candidates.loc[1,'OilRiskBlocked'])
        pd.testing.assert_frame_equal(rows,original)
        # The frozen allocator ignores the production-only marker and reasons.
        shadow=allocate_profile(result.candidates,pd.DataFrame(),policy='baseline',account_nav=15000)
        self.assertEqual(set(shadow.candidates.query("allocation_decision == 'Allocate'").ticker),{'XOM','CVX','KO'})

    def test_existing_name_blocks_new_even_when_close_recommended(self):
        held=pd.DataFrame([position('SLB')]);held.loc[0,'position_recommendation']='SELL'
        result=arbitrate_with_oil_guard(arbitrate_portfolio,pd.DataFrame([candidate('EOG',99)]),held,15000)
        self.assertNotEqual(result.candidates.iloc[0].allocation_decision,'Allocate')

    def test_unqualified_highest_does_not_block_feasible_name(self):
        rows=pd.DataFrame([candidate('XOM',99,execution=1),candidate('CVX',90)])
        result=arbitrate_with_oil_guard(arbitrate_portfolio,rows,pd.DataFrame(),15000)
        self.assertEqual(result.candidates.iloc[1].allocation_decision,'Allocate')

    def test_existing_breach_visible_no_extra_name(self):
        result=arbitrate_with_oil_guard(arbitrate_portfolio,pd.DataFrame([candidate('HAL',99)]),pd.DataFrame([position('XOM'),position('CVX')]),15000)
        self.assertTrue(result.summary['oil_limit_breached_in_actual_holdings'])
        self.assertNotEqual(result.candidates.iloc[0].allocation_decision,'Allocate')


if __name__=='__main__':unittest.main()
