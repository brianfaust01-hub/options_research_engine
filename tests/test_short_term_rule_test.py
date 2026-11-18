import csv
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from short_term_rule_test import actual_exit_overlay, order_history, replay, select_bracket
from exit_path_review import stamp


class ShortTermRuleTests(unittest.TestCase):
    @staticmethod
    def points(*bids):
        return [(i*60,i*60,bid,bid+.02) for i,bid in enumerate(bids)]

    def test_delay_uses_next_fresh_bid(self):
        points = self.points(11,9.5,10)
        result = replay(points,10,1,8,12,.50,'close',delay=60)
        self.assertEqual(result['fills'],[(60,9.49,1,'stop_or_early_close')])

    def test_original_target_can_fill_during_delay(self):
        result = replay(self.points(11,12.2),10,1,8,12,.50,'close',delay=60)
        self.assertEqual(result['fills'],[(60,12,1,'target')])

    def test_raised_stop_uses_gap_bid_and_does_not_sell_on_activation(self):
        result = replay(self.points(11,10.2,12.2),10,1,8,12,.50,'raise')
        self.assertTrue(result['raised'])
        self.assertEqual(result['fills'],[(60,10.19,1,'stop_or_early_close')])

    def test_partial_fill_continues_through_later_quotes(self):
        result = replay(self.points(11,10,9),10,3,8,12,.50,'close',max_per_quote=1)
        self.assertEqual([fill[2] for fill in result['fills']],[1,1,1])
        self.assertEqual([fill[1] for fill in result['fills']],[10.99,9.99,8.99])

    def test_overlay_replaces_only_rule_fills_before_actual_reduction(self):
        result = replay(self.points(11,10,9),10,3,8,12,.50,'close',max_per_quote=1)
        units = [{'status':'CLOSED','exit':10.5,'fees':1.32,'entry_fee':.66}]*3
        delta, qty = actual_exit_overlay(result,units,60)
        self.assertEqual(qty,1)
        self.assertAlmostEqual(delta,48.96)

    def test_overlay_leaves_original_stop_fills_to_actual_record(self):
        result = replay(self.points(7,11,10),10,1,8,12,.50,'close')
        self.assertEqual(result['rule_fills'],[])

    def test_untriggered_rule_keeps_control_outcome(self):
        points = self.points(10.2,9.5,10.3)
        self.assertEqual(replay(points,10,1,8,12,.50,'close'), replay(points,10,1,8,12))

    def test_amendment_applies_on_or_after_placement(self):
        result = replay(self.points(9.5,9.5,10),10,1,8,12,amendments=[(60,1,'STP',9.7)])
        self.assertEqual(result['fills'],[(60,9.49,1,'stop_or_early_close')])

    def test_replacement_never_lowers_the_protection_floor(self):
        result = replay(self.points(11,10.2,12.2),10,1,8,12,.50,'raise',amendments=[(60,1,'STP',7)])
        self.assertEqual(result['fills'],[(60,10.19,1,'stop_or_early_close')])

    def test_export_links_bracket_and_replacement_to_parent(self):
        def row(time,side,kind,price,status,qty,effect):
            return ['', '',time,'SINGLE',side,qty,'',effect,'TEST','15 JAN 27','100','CALL',price,kind,'GTC',status]
        def detail(link,kind='',price=''):
            return ['','','',link,'','','','','','','','',price,kind,'','']
        placed = '11/10/26 10:30:00'
        amended = '11/10/26 11:30:00'
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'2026-11-10-AccountStatement.csv'
            with path.open('w',newline='',encoding='utf-8') as handle:
                csv.writer(handle).writerows([
                    ['Account Order History'],['header'],
                    row(placed,'SELL','MKT','~','CANCELED','-1','TO CLOSE'),
                    detail('TRG BY #11','STP','BASE-2'),detail('OCO #12','STP','8'),
                    row(placed,'SELL','LMT','BASE+2','WORKING','-1','TO CLOSE'),
                    detail('TRG BY #11','LMT','12'),detail('OCO #12'),
                    row(placed,'BUY','LMT','10','FILLED','+1','TO OPEN'),
                    row(amended,'SELL','MKT','~','WORKING','-1','TO CLOSE'),
                    detail('RE #13','STP','9.5'),detail('TRG BY #11'),[],
                ])
            brackets, _, changes = order_history(Path(tmp),'2026-11-10','2026-11-10')
            key = 'TEST270115C00100000'
            at = stamp('2026-11-10T10:31:00')
            self.assertEqual(select_bracket(key,at,10,1,brackets[key],None,None),
                             (8,12,'BROKER_INITIAL_BRACKET_INFERRED','TRG BY #11'))
            self.assertEqual(changes[(key,'TRG BY #11')][(stamp('2026-11-10T11:30:00'),1,'STP')],{9.5})


if __name__=='__main__':
    unittest.main()
