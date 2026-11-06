from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import opening_hour as m
from test_portfolio_arbitrator import candidate,position
from portfolio_arbitrator import arbitrate_portfolio
from production_risk_controls import arbitrate_with_oil_guard
from configuration_profile_shadow import allocate_profile

NOW=datetime(2026,11,5,15,37,tzinfo=timezone.utc)
START=datetime(2026,11,5,14,30,tzinfo=timezone.utc)
END=START+timedelta(hours=1)


def bars(up=True):
    result=[]
    for i in range(60):
        price=100+(i*.02 if up else -i*.02)
        result.append({'datetime':int((START+timedelta(minutes=i)).timestamp()*1000),
            'open':price,'high':price+.02,'low':price-.02,'close':price+.01 if up else price-.01,'volume':100})
    return {'candles':result}


class OpeningHourTests(unittest.TestCase):
    def test_window_and_dst(self):
        self.assertEqual(m.window(NOW),(START,END))
        self.assertIsNone(m.window(START+timedelta(minutes=59)))
        self.assertIsNone(m.window(NOW.replace(hour=22)))
        summer=datetime(2026,9,18,15,tzinfo=timezone.utc)
        self.assertEqual(m.window(summer)[0].hour,13)

    def test_complete_hour_excludes_later_and_premarket_bars(self):
        raw=bars();raw['candles']+=[dict(raw['candles'][0],datetime=int(END.timestamp()*1000),close=1),
            dict(raw['candles'][0],datetime=int((START-timedelta(minutes=1)).timestamp()*1000))]
        s=m.summarize(raw,START,END)
        self.assertEqual(s['status'],'COMPLETE')
        self.assertEqual(s['bars'],60)
        self.assertGreater(s['return_from_open'],0)
        self.assertGreater(s['close'],s['bar_vwap'])
        self.assertEqual(s['last_bar_at'],(END-timedelta(minutes=1)).isoformat())

    def test_missing_duplicate_crossed_ohlc_and_zero_volume_fail(self):
        for kind in ('missing','duplicate','invalid','volume'):
            raw=bars()
            if kind=='missing':raw['candles'].pop()
            elif kind=='duplicate':raw['candles'].append(raw['candles'][0].copy())
            elif kind=='invalid':raw['candles'][0]['high']=1
            else:
                for c in raw['candles']:c['volume']=0
            self.assertNotEqual(m.summarize(raw,START,END)['status'],'COMPLETE',kind)

    def test_confirmation_and_contradiction_are_directional_not_automatic_inverse(self):
        up=m.summarize(bars(),START,END);down=m.summarize(bars(False),START,END)
        self.assertEqual(m.evaluate(up,'Long Call',up)[0],'CONFIRMED')
        self.assertEqual(m.evaluate(down,'Long Call',up)[0],'CONTRADICTED')
        self.assertEqual(m.evaluate(down,'Long Put',up)[0],'CONFIRMED')
        self.assertEqual(m.evaluate(up,'Long Put',up)[0],'CONTRADICTED')
        self.assertEqual(m.evaluate(up,'Long Call',{'status':'MISSING'})[0],'DATA_UNAVAILABLE')
        self.assertEqual(m.evaluate({**up,'return_from_open':-.01},'Long Call',up)[0],'MIXED')

    def test_production_excludes_contradiction_reallocates_and_shadow_remains_original(self):
        rows=pd.DataFrame([dict(candidate('UP',99),option_strategy='Long Call'),
            dict(candidate('DOWN',98),option_strategy='Long Call'),
            dict(candidate('PUT',97),option_strategy='Long Put')])
        original=rows.copy(deep=True)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def fetch(symbol,start,end):
                self.assertEqual((start,end),(START,END))
                return bars(symbol in ('UP','SPY'))
            def oil(*a,**k):return arbitrate_with_oil_guard(arbitrate_portfolio,*a,**k)
            result=m.arbitrate_with_opening_hour(oil,rows,pd.DataFrame(),15000,root=root,now=NOW,fetch=fetch)
            self.assertEqual(set(result.candidates.query("allocation_decision == 'Allocate'").ticker),{'UP','PUT'})
            self.assertEqual(result.candidates.loc[1,'action'],'Evaluate Options')
            self.assertEqual(result.candidates.loc[1,'option_strategy'],'Long Call')
            self.assertTrue(result.candidates.loc[1,'OpeningHourBlocked'])
            pd.testing.assert_frame_equal(rows,original)
            artifact=root/result.candidates.loc[0,'OpeningHourEvidencePath']
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),result.candidates.loc[0,'OpeningHourEvidenceSHA256'])
            frozen=allocate_profile(result.candidates,pd.DataFrame(),policy='baseline',account_nav=15000)
            self.assertEqual(set(frozen.candidates.query("allocation_decision == 'Allocate'").ticker),{'UP','DOWN','PUT'})

    def test_missing_market_data_defers_entries_but_not_existing_holdings(self):
        rows=pd.DataFrame([dict(candidate('NEW'),option_strategy='Long Call')]);held=pd.DataFrame([position('HOLD')])
        with tempfile.TemporaryDirectory() as tmp:
            result=m.arbitrate_with_opening_hour(arbitrate_portfolio,rows,held,15000,root=Path(tmp),now=NOW,
                fetch=lambda s,a,b: {} if s=='SPY' else bars())
            self.assertNotEqual(result.candidates.iloc[0].allocation_decision,'Allocate')
            self.assertEqual(result.positions.iloc[0].portfolio_action,'HOLD')
            self.assertEqual(result.positions.iloc[0].OpeningHourStatus,'COMPLETE')

    def test_pre_window_and_failed_fetch_do_not_use_daily_prices_as_substitute(self):
        rows=pd.DataFrame([dict(candidate('NEW'),option_strategy='Long Call')])
        with tempfile.TemporaryDirectory() as tmp:
            result=m.arbitrate_with_opening_hour(arbitrate_portfolio,rows,pd.DataFrame(),15000,root=Path(tmp),
                now=START,fetch=lambda *_:self.fail('Pre-window fetch'))
            self.assertNotEqual(result.candidates.iloc[0].allocation_decision,'Allocate')
            def failed(*_):raise RuntimeError('fixture')
            result=m.arbitrate_with_opening_hour(arbitrate_portfolio,rows,pd.DataFrame(),15000,root=Path(tmp),now=NOW,fetch=failed)
            self.assertEqual(result.candidates.iloc[0].OpeningHourStatus,'DATA_UNAVAILABLE')

    def test_fetch_bounded_to_candidate_pool_plus_spy(self):
        rows=pd.DataFrame([dict(candidate('T'+str(i),score=100-i),option_strategy='Long Call') for i in range(45)])
        with tempfile.TemporaryDirectory() as tmp:
            records,summaries,*_=m.collect_context(rows,pd.DataFrame(),root=Path(tmp),now=NOW,fetch=lambda *_:bars())
            self.assertEqual(len(summaries),31)
            self.assertEqual(records[44]['status'],'NOT_REVIEWED_POOL')

    def test_brief_explains_first_hour_confirmation_and_original_snapshots(self):
        from report_writer import _opening_hour_review
        text,rows=_opening_hour_review(pd.DataFrame([{'ticker':'OLD'}]))
        self.assertIn('not captured',text)
        self.assertEqual(rows,[])
        frame=pd.DataFrame([{'ticker':'TEST','option_strategy':'Long Call','OpeningHourStatus':'CONTRADICTED',
            'OpeningHourSPYStatus':'COMPLETE','OpeningHourSPYReturn':-.01,'OpeningHourReturn':-.02,
            'OpeningHourCloseVsBarVWAP':-.01,'allocation_decision':'No Allocation','OpeningHourReason':'opposed'}])
        text,rows=_opening_hour_review(frame)
        self.assertIn('contradicted 1',text)
        self.assertIn('not automatically reversed',text)
        self.assertEqual(rows[0][0],'TEST')


if __name__=='__main__':unittest.main()
