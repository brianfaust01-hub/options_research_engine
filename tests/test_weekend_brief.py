import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import weekend_brief as m

NOW=datetime(2026,11,20,20,0,tzinfo=timezone.utc)


def position():
    return dict(PositionID='P1',RecommendationID='R1',Ticker='KKR',OptionStrategy='Long Put',
        Expiration='2027-01-15',Strike='90',Contracts='2',EntryPremium='5.50',Status='OPEN',
        EntryDate='2026-11-19T11:00:00',RecommendedStop='4.65',ticker='KKR',
        expiration='2027-01-15',strike=90.,option_type='PUT',contract_symbol='KKR270115P00090000')


def plan():
    return dict(RecommendationID='R1',RecommendationDate='2026-11-19T10:30:00',ticker='KKR',
        expiration='2027-01-15',strike='90',option_strategy='Long Put',profit_target_price='8.15',
        stop_loss_price='4.65',sector='Financials',industry='Capital Markets',theme='Markets')


def quote(**changes):
    return dict(quote_status='OBSERVED',bid=6.5,ask=6.7,quote_at=NOW.isoformat(),quote_age_seconds=0.,realtime=True,**changes)


def research(direction='Bearish', move=-.02, vwap=-.01):
    return dict(status='CURRENT_PROVISIONAL',direction=direction,basis='Provisional',
        intraday=dict(status='COMPLETE',return_from_open=move,close_vs_bar_vwap=vwap),
        last_hour=dict(status='COMPLETE',return_from_open=move,close_vs_bar_vwap=vwap))


def review(**changes):
    args=dict(p=position(),plan=plan(),quote=quote(),research=research(),market=research(),
              earnings='2027-02-01',now=NOW,session=m.session_info(NOW))
    args.update(changes)
    return m.review_position(**args)


def temporary_inputs(root):
    (root/'data').mkdir()
    p=position()
    with (root/'data/paper_portfolio.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(p));w.writeheader();w.writerow(p)
    r=plan()
    with (root/'data/trade_journal.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(r));w.writeheader();w.writerow(r)
    with (root/'data/account_state_snapshots.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['AsOfDate','ImportedAt','SourcePath','SourceSHA256'])
        w.writeheader();w.writerow(dict(AsOfDate='2026-11-19',ImportedAt='2026-11-19T17:00:00',SourcePath='statement.csv',SourceSHA256='abc'))


def collector(positions,now,session):
    return {p['contract_symbol']:quote() for p in positions},{'KKR':research(),'SPY':research()},{'KKR':'2027-02-01'},{}


class WeekendBriefTests(unittest.TestCase):
    def test_schedule_dst_holidays_early_close_and_late_recovery(self):
        regular=m.session_info(NOW)
        self.assertEqual(regular['due'],NOW)
        self.assertTrue(m.scheduled_due(NOW,regular))
        self.assertFalse(m.scheduled_due(NOW+timedelta(minutes=15),regular))
        early=datetime(2026,11,27,17,tzinfo=timezone.utc)
        self.assertEqual(m.session_info(early)['due'],early)
        self.assertEqual(m.session_info(early)['close'].hour,18)
        self.assertFalse(m.scheduled_due(early+timedelta(hours=4),m.session_info(early)))
        summer=datetime(2026,10,30,19,tzinfo=timezone.utc)
        self.assertEqual(m.session_info(summer)['due'],summer)
        self.assertIsNone(m.session_info(datetime(2026,12,25,20,tzinfo=timezone.utc)))
        self.assertIsNone(m.session_info(NOW+timedelta(days=1)))

    def test_profit_and_remaining_reward_are_dollars_at_held_quantity(self):
        r=review()
        self.assertAlmostEqual(r['pnl_dollars'],220)
        self.assertAlmostEqual(r['pnl_pct'],.20)
        self.assertAlmostEqual(r['reward_to_target'],310)
        self.assertAlmostEqual(r['giveback_to_stop'],390)
        self.assertEqual(r['guidance'],'REASSESS')
        self.assertTrue(any('giveback' in s for s in r['reasons']))

    def test_supported_thesis_can_hold_without_a_fixed_profit_exit(self):
        p=plan();p['profit_target_price']='12'
        self.assertEqual(review(plan=p)['guidance'],'HOLD')

    def test_opposed_thesis_can_prompt_discretionary_close(self):
        r=review(research=research('Bullish',.02,.01))
        self.assertEqual(r['guidance'],'CONSIDER CLOSING')

    def test_last_hour_reversal_prompts_reassessment(self):
        p=plan();p['profit_target_price']='12'
        context=research();context['last_hour']=research('Bullish',.01,.01)['intraday']
        self.assertEqual(review(plan=p,research=context)['guidance'],'REASSESS')

    def test_bad_quotes_never_support_hold_or_fabricate_pnl(self):
        for changes in (dict(quote_status='STALE_QUOTE'),dict(quote_at=(NOW-timedelta(minutes=2)).isoformat()),
                        dict(quote_at=(NOW+timedelta(seconds=1)).isoformat()),dict(bid=0),dict(ask=6),dict(bid=float('nan'))):
            q=quote();q.update(changes)
            r=review(quote=q)
            self.assertFalse(r['quote_usable'])
            self.assertNotIn('pnl_dollars',r)
            self.assertEqual(r['guidance'],'REASSESS')

    def test_unknown_plan_does_not_use_old_75_percent_target(self):
        r=review(plan={})
        self.assertIsNone(r['target'])
        self.assertEqual(r['guidance'],'REASSESS')

    def test_bid_crossing_is_not_reported_as_std_stop_execution(self):
        q=quote();q.update(bid=4.5,ask=4.7)
        r=review(quote=q)
        self.assertEqual(r['guidance'],'REASSESS')
        self.assertTrue(any('does not establish an STD stop trigger' in s for s in r['reasons']))

    def test_events_missing_evidence_and_expiry(self):
        self.assertEqual(review(earnings='2026-11-23')['guidance'],'CONSIDER CLOSING')
        p=position();p['expiration']='2026-11-20'
        self.assertEqual(review(p=p)['guidance'],'CONSIDER CLOSING')
        self.assertEqual(review(earnings=None)['guidance'],'REASSESS')
        self.assertEqual(review(research={})['guidance'],'REASSESS')

    def test_exact_plan_lineage_rejects_contract_mismatch_and_duplicate_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);temporary_inputs(root)
            path=root/'data/trade_journal.csv'
            self.assertEqual(m.load_plans(path,[position()],NOW)['P1']['profit_target_price'],'8.15')
            p=position();p['strike']=95
            self.assertEqual(m.load_plans(path,[p],NOW),{})
            r=plan();r['profit_target_price']='20'
            with path.open('a',newline='') as f:csv.DictWriter(f,fieldnames=list(r)).writerow(r)
            self.assertEqual(m.load_plans(path,[position()],NOW),{})

    def test_fresh_daily_thesis_requires_complete_session_and_ignores_future_daily_bar(self):
        session=m.session_info(NOW)
        daily=[]
        for i,day in enumerate(pd.bdate_range(end='2026-11-19',periods=220)):
            price=200-i*.2
            daily.append(dict(Datetime=int(day.tz_localize('America/New_York').timestamp()*1000),
                Open=price,High=price+1,Low=price-1,Close=price,Volume=10000000))
        candles=[]
        for i in range(330):
            price=155-i*.01
            candles.append(dict(datetime=int((session['open']+timedelta(minutes=i)).timestamp()*1000),
                open=price,high=price+.1,low=price-.1,close=price-.01,volume=10000))
        result=m.fresh_research('KKR',daily,dict(candles=candles),NOW,session)
        self.assertEqual(result['status'],'CURRENT_PROVISIONAL')
        self.assertEqual(result['direction'],'Bearish')
        future=dict(daily[-1],Datetime=int((NOW+timedelta(days=1)).timestamp()*1000),Close=99999)
        self.assertEqual(m.fresh_research('KKR',daily+[future],dict(candles=candles),NOW,session)['direction'],'Bearish')
        self.assertEqual(m.fresh_research('KKR',daily,dict(candles=candles[:-1]),NOW,session)['status'],'INCOMPLETE_INTRADAY')

    def test_render_has_only_holdings_escapes_html_and_labels_stale_quantity(self):
        p=position();p['ticker']='<TEST>'
        r=m.build_report([p],dict(status='UNCONFIRMED',broker_as_of='2026-11-19',warning='Confirm quantities'),{},
            {p['contract_symbol']:quote()},{},{},NOW,m.session_info(NOW))
        md,page=m.render(r)
        self.assertIn('Confirm quantities',page)
        self.assertIn('&lt;TEST&gt;',page)
        self.assertNotIn('<TEST>',page)
        self.assertNotIn('New Trades to Enter',md)
        self.assertIn('No new trades',md)

    def test_preview_send_dedup_and_source_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);temporary_inputs(root)
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'data').iterdir()}
            preview=m.run(root,now=NOW,collector=collector)
            self.assertEqual(preview['status'],'PREVIEW')
            self.assertFalse((Path(preview['report']).parent/'delivery.json').exists())
            with patch('email_reporter.send_email_report') as send:
                self.assertEqual(m.run(root,send=True,scheduled=True,now=NOW,collector=collector)['status'],'SENT')
                self.assertEqual(m.run(root,send=True,scheduled=True,now=NOW,collector=collector)['status'],'ALREADY_SENT')
                self.assertEqual(send.call_count,1)
            after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'data').iterdir()}
            self.assertEqual(before,after)

    def test_uncertain_smtp_does_not_retry_or_duplicate_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);temporary_inputs(root)
            with patch('email_reporter.send_email_report',side_effect=RuntimeError('SMTP interrupted')):
                with self.assertRaises(RuntimeError):m.run(root,send=True,now=NOW,collector=collector)
            with patch('email_reporter.send_email_report') as send:
                self.assertEqual(m.run(root,send=True,now=NOW,collector=collector)['status'],'DELIVERY_UNCERTAIN_REQUIRES_REVIEW')
                send.assert_not_called()

    def test_nonfriday_or_missed_window_does_no_collection(self):
        with patch.object(m,'collect') as collect:
            self.assertEqual(m.run(now=NOW+timedelta(days=1))['status'],'OUTSIDE_REVIEW_WINDOW')
            self.assertEqual(m.run(now=NOW+timedelta(hours=1),scheduled=True)['status'],'OUTSIDE_REVIEW_WINDOW')
            collect.assert_not_called()

    def test_no_priced_positions_is_unavailable_not_zero_profit(self):
        r=m.build_report([position()],dict(warning='Confirm'),{}, {},{}, {},NOW,m.session_info(NOW))
        self.assertIsNone(r['pnl_dollars'])
        self.assertEqual(r['priced_positions'],0)

    def test_holdings_change_during_collection_suppresses_email(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);temporary_inputs(root)
            def mutate(positions,now,session):
                path=root/'data/paper_portfolio.csv'
                path.write_text(path.read_text()+'\n')
                return collector(positions,now,session)
            with patch('email_reporter.send_email_report') as send:
                self.assertEqual(m.run(root,send=True,now=NOW,collector=mutate)['status'],'HOLDINGS_CHANGED_DURING_REVIEW')
                send.assert_not_called()


if __name__=='__main__':unittest.main()
