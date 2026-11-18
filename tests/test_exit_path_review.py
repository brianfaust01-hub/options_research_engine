import sys
from pathlib import Path
import unittest
import gzip
import hashlib
import json
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from exit_path_review import valid_point, replay, coverage, summarize, stamp, symbol, extract, review


class ExitPathReviewTests(unittest.TestCase):
    def point(self, bid, minute=0):
        return (1000+minute*60,1000+minute*60,bid,bid+.05)

    def test_stop_gap_fills_at_observed_bid_less_slippage(self):
        r=replay([self.point(6)],10,8,14,'Original levels')
        self.assertAlmostEqual(r['price'],5.99)
        self.assertEqual(r['reason'],'OBSERVED_STOP')

    def test_target_requires_adverse_slippage_headroom(self):
        r=replay([self.point(14)],10,8,14,'Original levels')
        self.assertEqual(r['reason'],'SAMPLED_ENDPOINT')
        r=replay([self.point(14.02)],10,8,14,'Original levels')
        self.assertEqual(r['price'],14)

    def test_trailing_is_ratchet_and_preserves_gap_risk(self):
        r=replay([self.point(13.5),self.point(11,1)],10,8,14,'Trail after three-quarter target')
        self.assertEqual(r['reason'],'OBSERVED_STOP')
        self.assertAlmostEqual(r['price'],10.99)

    def test_breakeven_activates_only_after_half_target(self):
        r=replay([self.point(11.9),self.point(9.8,1)],10,8,14,'Breakeven at half target')
        self.assertEqual(r['reason'],'SAMPLED_ENDPOINT')
        r=replay([self.point(12),self.point(9.8,1)],10,8,14,'Breakeven at half target')
        self.assertEqual(r['reason'],'OBSERVED_STOP')

    def test_score_missing_does_not_invent_confidence(self):
        self.assertIsNone(replay([self.point(10)],10,8,14,'Score-conditioned stop distance'))

    def test_validation_rejects_zero_stale_future_crossed_and_delayed(self):
        q={'observed_at':'2026-10-01T14:00:30+00:00','quote_at':'2026-10-01T14:00:00+00:00',
           'bid':1,'ask':1.1,'quote_status':'OBSERVED','realtime':True}
        self.assertIsNotNone(valid_point(q))
        for patch in ({'bid':0},{'ask':.5},{'realtime':False},{'quote_at':'2026-10-01T13:59:00+00:00'},
                      {'quote_at':'2026-10-01T14:01:00+00:00'},{'bid':float('nan')}):
            self.assertIsNone(valid_point(q|patch))

    def test_coverage_excludes_overnight_minutes(self):
        sessions=[('a',0,120),('b',3600,3720)]
        pts=[(x,x,1,1.1) for x in (0,60,3600,3660)]
        c=coverage(pts,0,3719,sessions)
        self.assertEqual(c['expected_minutes'],4)
        self.assertEqual(c['coverage'],1)
        self.assertEqual(c['longest_missing_market_minutes'],0)

    def test_missing_entry_or_endpoint_fails_qualification(self):
        pts=[(x,x,1,1.1) for x in range(180,1200,60)]
        self.assertFalse(coverage(pts,0,1199,[('a',0,1200)])['qualified_sampled_path'])

    def test_event_drawdown_aggregates_simultaneous_closures(self):
        s=summarize([{'at':1,'net':100},{'at':2,'net':-80},{'at':2,'net':50}])
        self.assertEqual(s['realized_only_drawdown_dollars'],30)

    def test_broker_time_eastern_and_occ_identity(self):
        self.assertEqual(stamp('2026-11-05T10:30:00'),stamp('2026-11-05T15:30:00+00:00'))
        self.assertEqual(symbol({'ticker':'WFC','expiration':'2027-01-15','option_type':'CALL','strike':92.5}),
                         'WFC270115C00092500')

    def test_archive_read_preserves_bytes_and_records_corruption(self):
        with TemporaryDirectory() as tmp:
            day=Path(tmp)/'2026-10-01'; day.mkdir()
            q={'contract_symbol':'TEST  261218C00100000','observed_at':'2026-10-01T14:00:30+00:00',
               'quote_at':'2026-10-01T14:00:00+00:00','bid':1,'ask':1.1,'quote_status':'OBSERVED','realtime':True}
            raw=gzip.compress(json.dumps({'observations':[q,q|{'observed_at':'2026-10-01T14:00:40+00:00'}]}).encode())
            file=day/'good.gz'; file.write_bytes(raw); (day/'broken.gz').write_bytes(b'broken')
            paths,manifest,errors,counts=extract(tmp,{'TEST261218C00100000'},'2026-11-05')
            self.assertEqual(len(paths['TEST261218C00100000']),1)
            self.assertEqual(len(errors),1); self.assertEqual(len(manifest),2)
            self.assertEqual(hashlib.sha256(file.read_bytes()).digest(),hashlib.sha256(raw).digest())

    def test_no_missing_paths_manufactured_as_time_exit(self):
        v={'start':'2026-09-25','end':'2026-11-05','units':[{
            'side':1,'entry_at':'2026-10-01T10:30:00','ticker':'TEST','expiration':'2026-12-18',
            'strike':100.,'option_type':'CALL','entry':10.,'entry_fee':.7,'status':'CLOSED',
            'exit_at':'2026-10-02T10:30:00','exit':8.,'net_period_contribution':-201.4,'gross_full_trade':-200.,
            'exit_order_type':'STP','link_status':'INFERRED','original_stop':8.,'original_target':14.}]}
        r=review(v,{})
        self.assertEqual(r['qualified_groups'],0)
        self.assertEqual(r['replays'],[])
        self.assertEqual(r['stopped_with_post_exit_quotes'],0)

    def overlay_fixture(self):
        unit={'side':1,'entry_at':'2026-10-01T10:30:00','ticker':'TEST','expiration':'2026-12-18',
            'strike':100.,'option_type':'CALL','entry':10.,'entry_fee':.7,'status':'CLOSED',
            'exit_at':'2026-10-01T10:33:00','exit':14.,'net_period_contribution':398.6,'gross_full_trade':400.,
            'exit_order_type':'LMT','link_status':'INFERRED','original_stop':8.,'original_target':14.}
        points=[(stamp(f'2026-10-01T10:{30+i}:00'),stamp(f'2026-10-01T10:{30+i}:00'),bid,bid+.05)
                for i,bid in enumerate([10.,8.4,14.2,14.2])]
        return unit,points

    def test_tighter_overlay_counts_winner_sacrificed_against_actual(self):
        unit,points=self.overlay_fixture()
        r=review({'start':'2026-09-25','end':'2026-11-05','units':[unit]}, {symbol(unit):points})
        tighter=next(x for x in r['early_sale_overlays'] if x['rule']=='Stop distance x0.75' and x['slippage']==.01)
        self.assertTrue(tighter['changed']); self.assertLess(tighter['net'],0)
        self.assertGreater(tighter['actual_net'],0)
        control=next(x for x in r['early_sale_overlays'] if x['rule']=='Original levels' and x['slippage']==.01)
        self.assertAlmostEqual(control['net'],unit['net_period_contribution'])

    def test_mixed_partial_exits_not_treated_as_constant_full_quantity(self):
        unit,points=self.overlay_fixture()
        r=review({'start':'2026-09-25','end':'2026-11-05','units':[unit,unit|{'exit_at':'2026-10-01T10:32:00'}]},
                 {symbol(unit):points})
        self.assertEqual(r['early_sale_overlays'],[])


if __name__=='__main__': unittest.main()
