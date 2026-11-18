from datetime import datetime
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from broker_performance_attribution import reconstruct,match_plan
from broker_reconciliation import BrokerTrade


def trade(at,side,q,price,effect='TO OPEN'):
    return BrokerTrade('2026-11-02T'+at,side,q,effect,'TEST','2027-01-15',100,'CALL',price,'LMT')


def cash(t,fee):
    return {'ExecutedAt':t.executed_at,'EventType':'TRD','Description':'BOT +1 TEST 100 15 JAN 27 100 CALL',
            'MiscFees':0.,'CommissionsFees':-fee}


def position(q,entry,mark):
    return {'ticker':'TEST','expiration':'2027-01-15','strike':100,'option_type':'CALL',
            'quantity':q,'entry_price':entry,'mark':mark}


def plan(at='2026-11-02T10:00:00',rid='rec'):
    return {'at':datetime.fromisoformat(at),'RecommendationID':rid,'allocation_decision':'Allocate',
        'id_conflict':False,'contracts':'1','execution_entry_price':'2.05','stop_loss_price':'1.6',
        'profit_target_price':'3','ResearchScore':'90','portfolio_score':'85','execution_score':'90',
        'broker_delta':'.4','implied_volatility':'.3','PolicyEvidenceFingerprint':'p',
        'ProductionRiskPolicyVersion':'','OpeningHourPolicyVersion':''}


START=datetime(2026,11,1,16);END=datetime(2026,11,2,16)
KEY=('TEST','2027-01-15',100.,'CALL')


class AttributionTests(unittest.TestCase):
    def test_closed_and_open_dollars_and_fees_reconcile(self):
        fills=[trade('10:10:00','BUY',2,2),trade('11:00:00','SELL',1,3,'TO CLOSE')]
        rows,missing=reconstruct([], [position(1,2,2.5)],fills,[cash(fills[0],1.4),cash(fills[1],.7)],START,END,{KEY:[plan()]})
        self.assertFalse(missing)
        self.assertAlmostEqual(sum(r['net_period_contribution'] for r in rows),147.9)
        self.assertEqual(sum(r.get('above_recorded_recommendation_quantity',False) for r in rows),1)

    def test_over_sell_and_buy_to_close_are_short_not_deleted(self):
        fills=[trade('10:10:00','SELL',1,3,'TO CLOSE'),trade('11:00:00','BUY',1,2,'TO CLOSE')]
        rows,_=reconstruct([],[],fills,[cash(t,.7) for t in fills],START,END,{KEY:[plan()]})
        self.assertEqual(rows[0]['link_status'],'UNSUPPORTED_SHORT')
        self.assertAlmostEqual(rows[0]['net_period_contribution'],98.6)

    def test_reopened_plan_is_not_falsely_lifetime_excess(self):
        fills=[trade('10:10:00','BUY',1,2),trade('11:00:00','SELL',1,3,'TO CLOSE'),
               trade('12:00:00','BUY',1,2),trade('13:00:00','SELL',1,3,'TO CLOSE')]
        rows,_=reconstruct([],[],fills,[cash(t,.7) for t in fills],START,END,{KEY:[plan()]})
        self.assertTrue(all(not r['above_recorded_recommendation_quantity'] for r in rows))
        self.assertEqual(len({r['unit_id'] for r in rows}),2)

    def test_inherited_contribution_uses_starting_mark_not_full_trade_gain(self):
        t=trade('11:00:00','SELL',1,3,'TO CLOSE')
        rows,_=reconstruct([position(1,1,2)],[],[t],[cash(t,.7)],START,END,{})
        self.assertEqual(rows[0]['gross_full_trade'],200)
        self.assertEqual(rows[0]['gross_period_contribution'],100)
        self.assertAlmostEqual(rows[0]['net_period_contribution'],99.3)

    def test_no_future_plan_and_ambiguous_ids_not_guessed(self):
        self.assertEqual(match_plan(KEY,datetime(2026,11,2,9),{KEY:[plan()]})['link_status'],'UNMATCHED')
        out=match_plan(KEY,datetime(2026,11,2,11),{KEY:[plan(),plan(rid='other')]})
        self.assertEqual(out['link_status'],'AMBIGUOUS_CONTRACT_TIME')
        self.assertNotIn('recommendation_id',out)

    def test_exact_ending_inventory_required(self):
        with self.assertRaises(ValueError):reconstruct([], [position(1,2,2)],[],[],START,END,{})


if __name__=='__main__':unittest.main()
