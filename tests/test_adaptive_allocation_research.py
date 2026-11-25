from datetime import datetime,timedelta
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import adaptive_allocation_research as m


def trade(i,ret=.1):
    day=datetime(2026,9,1)+timedelta(days=i)
    return dict(id=str(i),decision_at=day.replace(hour=10).isoformat(),
        exit_at=(day+timedelta(days=1)).replace(hour=11).isoformat(),
        entry_date=day.date().isoformat(),features=[float(i%5),None,float(i%3)],
        realized_return=ret,net_pnl=ret*100,debit=100,quantity=1,
        risk_mode='Normal',direction='Long Call')


class AdaptiveAllocationResearchTests(unittest.TestCase):
    def test_rejected_candidates_are_not_all_labeled_missed_opportunities(self):
        base=dict(option_strategy='Long Put',earnings_status='CONFIRMED',execution_score=90,
                  execution_entry_price=5,portfolio_score=80,portfolio_action_reason='forward score below cutoff')
        self.assertEqual(m.cohort(dict(base,portfolio_action='OPEN')),'RECOMMENDED_NEW_OR_ADD')
        self.assertEqual(m.cohort(dict(base,OpeningHourStatus='CONTRADICTED')),'DIRECTION_CONTRADICTED')
        self.assertEqual(m.cohort(dict(base,OpeningHourStatus='NOT_REVIEWED_POOL')),'NOT_FULLY_EVALUATED')
        self.assertEqual(m.cohort(dict(base,execution_score=50)),'EXECUTION_SCORE_BLOCK')
        self.assertEqual(m.cohort(base),'SCORE_OR_OPERATIONAL_HURDLE_BLOCK')
        self.assertEqual(m.cohort(dict(base,portfolio_action_reason='active-position limit reached')),
                         'RECORDED_QUALIFIED_PORTFOLIO_CAPACITY_BLOCK')

    def test_contract_quantity_failure_is_distinct_from_execution_failure(self):
        r=dict(option_strategy='Long Put',earnings_status='CONFIRMED',execution_score=90,
            execution_entry_price=10,portfolio_score=80,portfolio_action_reason='invalid contract quantity or entry price')
        self.assertEqual(m.cohort(r),'QUANTITY_OR_EXISTING_EXPOSURE_BLOCK')

    def test_directional_movement_features_do_not_treat_puts_as_calls(self):
        call=m.feature_vector(dict(option_strategy='Long Call',Return1D=.03))
        put=m.feature_vector(dict(option_strategy='Long Put',Return1D=.03))
        index=m.RAW_FEATURES.index('Return1D')
        self.assertEqual(call[index],.03)
        self.assertEqual(put[index],-.03)

    def test_future_and_unclosed_labels_cannot_enter_training(self):
        a=trade(1);b=trade(2);c=trade(10)
        b['exit_at']='2026-12-01T12:00:00'
        rows=m.eligible_training([a,b,c],'2026-09-05T10:00:00')
        self.assertEqual([r['id'] for r in rows],['1'])

    def test_same_instant_exit_is_not_available_before_decision(self):
        r=trade(1);r['exit_at']='2026-09-05T10:00:00'
        self.assertEqual(m.eligible_training([r],'2026-09-05T10:00:00'),[])

    def test_training_preprocessing_ignores_the_test_observation(self):
        rows=[trade(i) for i in range(30)]
        model=m.fit(rows,10)
        before=model['means'].copy()
        test=trade(100);test['features']=[1e9,None,-1e9]
        m.predict(model,test)
        np.testing.assert_array_equal(before,model['means'])

    def test_date_weighting_prevents_one_busy_day_dominating_fit(self):
        a=trade(1);b=trade(1);c=trade(2)
        w=m.date_weights([a,b,c])
        np.testing.assert_allclose(w,[.5,.5,1.])

    def test_constant_payoff_is_recovered_without_nan_from_missing_fields(self):
        rows=[trade(i,.12) for i in range(35)]
        model=m.fit(rows,100)
        self.assertAlmostEqual(m.predict(model,trade(100)),.12)

    def test_walk_forward_prediction_does_not_change_when_own_future_label_changes(self):
        rows=[trade(i,.1+(.02 if i%2 else -.02)) for i in range(34)]
        first,_=m.walk_forward(rows)
        changed=[dict(r) for r in rows];changed[-1]['realized_return']=-.99
        second,_=m.walk_forward(changed)
        self.assertAlmostEqual(first[-1]['prediction'],second[-1]['prediction'])
        for r in first:self.assertLess(m.at(r['latest_training_exit']),m.at(r['decision_at']))

    def test_dollar_screen_charges_missed_winners_and_counts_avoided_losses(self):
        rows=[dict(trade(1,.5),prediction=-.1,prior_mean=.1),dict(trade(2,-.2),prediction=-.1,prior_mean=.1)]
        result=m.performance(rows)
        self.assertEqual(result['missed_winning_dollars'],50)
        self.assertEqual(result['avoided_losing_dollars'],20)
        self.assertEqual(result['positive_forecast_retained_actual_net'],0)
        self.assertEqual(result['actual_baseline_net'],30)


if __name__=='__main__':unittest.main()
