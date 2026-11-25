"""Read-only Friday holdings review. No allocation, broker orders or portfolio writes."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd

from exit_path_review import symbol
from opening_hour import summarize, evaluate
from option_observation_collector import normalize_quote
from portfolio_exposure import classify_ticker

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo('America/New_York')
VERSION = 'FRIDAY-HOLDINGS-REVIEW-2026-11-23-v1'


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def session_info(now):
    """NYSE session/calendar owns DST, holidays, early closes and next open."""
    if now.tzinfo is None:
        raise ValueError('Timezone-aware timestamp required')
    import pandas_market_calendars as calendars
    local = now.astimezone(ET)
    schedule = calendars.get_calendar('NYSE').schedule(
        local.date()-timedelta(days=7), local.date()+timedelta(days=10))
    today = schedule[schedule.index.date == local.date()]
    if today.empty or local.weekday() != 4:
        return None
    row = today.iloc[0]
    later = schedule[schedule.index.date > local.date()]
    prior = schedule[schedule.index.date < local.date()]
    return dict(open=row.market_open.to_pydatetime(), close=row.market_close.to_pydatetime(),
                due=row.market_close.to_pydatetime()-timedelta(hours=1),
                next_open=later.iloc[0].market_open.to_pydatetime(),
                previous_session=str(prior.index[-1].date()))


def scheduled_due(now, session):
    return bool(session and session['due'] <= now < session['due']+timedelta(minutes=15))


def read_holdings(root, now):
    """Read without paper_portfolio.load_portfolio's schema/creation side effects."""
    path = Path(root)/'data/paper_portfolio.csv'
    raw = path.read_bytes()
    rows = list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    held = [r for r in rows if r.get('Status','').upper() == 'OPEN']
    seen = set()
    for r in held:
        if not r.get('PositionID') or r['PositionID'] in seen:
            raise ValueError('Missing or duplicate open position identity')
        seen.add(r['PositionID'])
        qty = number(r.get('Contracts'))
        if qty is None or qty <= 0 or qty != int(qty) or number(r.get('EntryPremium')) is None or float(r['EntryPremium']) <= 0:
            raise ValueError('Invalid long position quantity or entry')
        if r.get('OptionStrategy') not in ('Long Call','Long Put'):
            raise ValueError('Unsupported position strategy')
        r['option_type'] = 'PUT' if r['OptionStrategy'] == 'Long Put' else 'CALL'
        r['ticker'] = r['Ticker'].strip().upper()
        r['expiration'] = r['Expiration'][:10]
        r['strike'] = float(r['Strike'])
        r['contract_symbol'] = symbol(r)
    meta = dict(portfolio_sha256=hashlib.sha256(raw).hexdigest(),
                portfolio_read_at=now.isoformat(), broker_as_of=None,
                status='UNCONFIRMED', warning='Holdings may omit intraday fills or exits. Confirm quantities in thinkorswim before acting.')
    snapshots = Path(root)/'data/account_state_snapshots.csv'
    if snapshots.exists():
        with snapshots.open(encoding='utf-8-sig', newline='') as handle:
            records = list(csv.DictReader(handle))
        valid = [r for r in records if r.get('AsOfDate','') <= now.astimezone(ET).date().isoformat()]
        if valid:
            latest = max(valid, key=lambda r:(r['AsOfDate'],r.get('ImportedAt','')))
            meta.update(broker_as_of=latest['AsOfDate'], broker_source=latest.get('SourcePath'),
                        broker_source_sha256=latest.get('SourceSHA256'))
    # A dated statement is not a live holdings feed, even when dated today.
    return held, meta


def load_plans(path, positions, now):
    """Exact originating IDs only; conflicts/mismatched contracts stay unknown."""
    wanted = {p.get('RecommendationID') for p in positions if p.get('RecommendationID')}
    plans = {}; conflicts = set()
    csv.field_size_limit(20_000_000)
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            rid = row.get('RecommendationID')
            if rid not in wanted:
                continue
            projection = {k:row.get(k,'') for k in ('RecommendationID','RecommendationDate','ticker','expiration','strike',
                'option_strategy','profit_target_price','stop_loss_price','earnings_date','sector','industry','theme')}
            try:
                at = datetime.fromisoformat(projection['RecommendationDate'].replace('Z','+00:00'))
                at = at.replace(tzinfo=ET) if at.tzinfo is None else at
                if at > now:
                    continue
            except ValueError:
                continue
            if rid in plans and plans[rid] != projection:
                conflicts.add(rid)
            plans.setdefault(rid, projection)
    result = {}
    for p in positions:
        rid = p.get('RecommendationID'); r = plans.get(rid)
        if r and rid not in conflicts and (r['ticker'].upper(),r['expiration'][:10],number(r['strike']),r['option_strategy']) == (p['ticker'],p['expiration'],p['strike'],p['OptionStrategy']):
            result[p['PositionID']] = r
    return result


def fresh_research(ticker, daily, intraday, now, session):
    """Same research modules; today's OHLCV is explicitly provisional through cutoff."""
    from indicators import calculate_indicators_for_ticker
    from research_engine import evaluate_strategies
    end = now.astimezone(timezone.utc).replace(second=0, microsecond=0)
    context = summarize(intraday, session['open'], end)
    if context['status'] != 'COMPLETE':
        return dict(status='INCOMPLETE_INTRADAY', intraday=context)
    frame = pd.DataFrame(daily)
    if frame.empty or 'Datetime' not in frame:
        return dict(status='MISSING_DAILY', intraday=context)
    frame['date'] = pd.to_datetime(frame['Datetime'], unit='ms', utc=True).dt.tz_convert(ET).dt.date
    frame = frame[frame.date < now.astimezone(ET).date()].sort_values('date')
    if len(frame) < 199 or frame.date.duplicated().any() or str(frame.date.iloc[-1]) != session['previous_session']:
        return dict(status='INCOMPLETE_DAILY', intraday=context)
    columns = ['Open','High','Low','Close','Volume']
    frame = frame[columns].apply(pd.to_numeric, errors='coerce')
    if not all(math.isfinite(x) for x in frame.to_numpy().ravel()) or (frame[['Open','High','Low','Close']] <= 0).any().any() or (frame.Volume < 0).any():
        return dict(status='INVALID_DAILY', intraday=context)
    frame = pd.concat([frame,pd.DataFrame([dict(Open=context['open'], High=context['high'], Low=context['low'],
        Close=context['close'], Volume=context['volume'])])],ignore_index=True)
    research = evaluate_strategies(calculate_indicators_for_ticker(ticker,frame))
    last_hour = summarize(intraday, end-timedelta(hours=1), end)
    return dict(status='CURRENT_PROVISIONAL', intraday=context, last_hour=last_hour,
                direction=research['Direction'], research_score=research['ResearchScore'],
                reasons=research['StrategyReasons'], basis='Daily indicators with provisional session-to-now OHLCV; no full-day volume claim')


def review_position(p, plan, quote, research, market, earnings, now, session):
    entry = float(p['EntryPremium']); qty = int(float(p['Contracts']))
    result = dict(position_id=p['PositionID'], ticker=p['ticker'], contract=p['contract_symbol'],
        option_strategy=p['OptionStrategy'], expiration=p['expiration'], strike=p['strike'], contracts=qty,
        entry=entry, recommendation_id=p.get('RecommendationID'), quote=quote, research=research,
        originating_plan=plan,
        originating_plan_sha256=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest() if plan else None,
        guidance='REASSESS', reasons=[], quantity_status='CONFIRM_IN_BROKER', earnings_date=earnings,
        earnings_status='CURRENT_PROVIDER_DATE' if earnings else 'UNKNOWN',
        events_status='Earnings reviewed when available; unscheduled news and broad event calendar not covered')
    target = number(plan.get('profit_target_price'))
    stop = number(p.get('RecommendedStop')) or number(plan.get('stop_loss_price'))
    if target is not None and target <= 0: target = None
    if stop is not None and stop <= 0: stop = None
    result.update(target=target, stop=stop, plan_status='EXACT_ORIGINATING_RECOMMENDATION' if plan else 'UNKNOWN',
                  level_status='Engine reference levels; confirm current broker OCO prices')
    exposure = classify_ticker(p['ticker'])
    result.update({k:plan.get(k) or exposure[k] for k in ('sector','industry','theme')})
    age=quote.get('quote_age_seconds')
    if quote.get('quote_at'):
        try:
            age=(now-datetime.fromisoformat(quote['quote_at'])).total_seconds()
        except (TypeError,ValueError):
            age=None
    bid,ask=number(quote.get('bid')),number(quote.get('ask'))
    usable = quote.get('quote_status')=='OBSERVED' and quote.get('realtime') is True and age is not None and 0 <= age <= 60 and bid is not None and ask is not None and 0<bid<=ask
    result['quote_usable'] = usable
    if not usable:
        result['reasons'].append('Fresh real-time option bid/ask unavailable; no price-based hold conclusion.')
        return result
    mid=(bid+ask)/2
    result.update(mark=mid, pnl_dollars=(mid-entry)*100*qty, pnl_pct=mid/entry-1,
        bid_value=bid*100*qty, premium_at_risk=bid*100*qty, spread_dollars=(ask-bid)*100*qty,
        profit_at_bid=(bid-entry)*100*qty,
        reward_to_target=max(0,target-mid)*100*qty if target is not None else None,
        giveback_to_stop=max(0,mid-stop)*100*qty if stop is not None else None)
    reasons=result['reasons']
    good = research.get('status')=='CURRENT_PROVISIONAL' and market.get('status')=='CURRENT_PROVISIONAL'
    if not good:
        reasons.append('Fresh stock/SPY evidence is incomplete; thesis requires reassessment.')
    else:
        sign=1 if p['option_type']=='CALL' else -1
        wanted='Bullish' if sign==1 else 'Bearish'
        intraday_status,_=evaluate(research['intraday'],p['OptionStrategy'],market['intraday'])
        result.update(thesis_direction=research['direction'], intraday_status=intraday_status,
                      spy_return=market['intraday']['return_from_open'])
        if research['direction'] not in (wanted,'Neutral') and intraday_status=='CONTRADICTED':
            result['guidance']='CONSIDER CLOSING'
            reasons.append('Refreshed daily thesis and today\'s move/price versus VWAP both oppose this position.')
        elif research['direction']==wanted and intraday_status=='CONFIRMED':
            result['guidance']='HOLD'
            reasons.append('Refreshed thesis and session price action support the existing direction.')
        else:
            reasons.append('Daily thesis and session price action are mixed.')
        hour=research.get('last_hour',{})
        if hour.get('status')=='COMPLETE' and sign*hour['return_from_open']<0 and sign*hour['close_vs_bar_vwap']<0:
            reasons.append('The last hour moved against the position and finished on the adverse side of its bar-VWAP.')
            if result['guidance']=='HOLD': result['guidance']='REASSESS'
    if target is None or stop is None or (target is not None and stop is not None and stop>=target):
        reasons.append('Original target or recorded stop is missing/inconsistent; verify the bracket.')
        if result['guidance']=='HOLD': result['guidance']='REASSESS'
    else:
        if bid>=target:
            reasons.append('Observed bid is at/above the reference target; verify whether the existing order has filled.')
            result['guidance']='REASSESS'
        if bid<=stop:
            reasons.append('Observed bid is at/below the reference stop; this does not establish an STD stop trigger. Verify order status.')
            result['guidance']='REASSESS'
        if result['pnl_dollars']>0 and result['giveback_to_stop']>=result['reward_to_target']:
            reasons.append('Potential giveback to the recorded stop is at least the remaining gain to target; weigh securing the profit.')
            if result['guidance']=='HOLD': result['guidance']='REASSESS'
    expiry=datetime.fromisoformat(p['expiration']).date()
    next_day=session['next_open'].astimezone(ET).date()
    if expiry<next_day or (earnings and now.astimezone(ET).date() <= datetime.fromisoformat(earnings).date() <= next_day):
        result['guidance']='CONSIDER CLOSING'
        reasons.append('Expiration or a reported earnings date falls before/at the next market session; confirm event timing.')
    if not earnings:
        reasons.append('Upcoming earnings date is unconfirmed; unknown does not mean event-free.')
        if result['guidance']=='HOLD': result['guidance']='REASSESS'
    return result


def build_report(positions, holdings, plans, quotes, research, earnings, now, session):
    rows=[review_position(p,plans.get(p['PositionID'],{}),quotes.get(p['contract_symbol'],{}),
        research.get(p['ticker'],{}),research.get('SPY',{}),earnings.get(p['ticker']),now,session) for p in positions]
    clusters=[]
    for field in ('sector','industry','theme'):
        buckets={}
        for r in rows:
            label=r.get(field)
            if not label or label=='Unknown': continue
            buckets.setdefault((label,r['option_strategy']),[]).append(r)
        for (label,direction),members in buckets.items():
            if len({r['ticker'] for r in members})>1:
                clusters.append(dict(kind=field,name=label,direction=direction,tickers=sorted({r['ticker'] for r in members}),
                    premium_cost=sum(r['entry']*100*r['contracts'] for r in members)))
    return dict(version=VERSION,as_of=now.isoformat(),review_date=now.astimezone(ET).date().isoformat(),
        next_session=session['next_open'].astimezone(ET).isoformat(),holdings=holdings,positions=rows,
        exposure_clusters=clusters,position_count=len(rows),priced_positions=sum(r['quote_usable'] for r in rows),
        pnl_dollars=sum(r.get('pnl_dollars',0) for r in rows) if not rows or any(r['quote_usable'] for r in rows) else None,
        pnl_scope='Priced positions only; gross open P/L before fees',
        advisory='Decision support only. Confirm holdings and live orders; final weekend decision is yours.',
        rules='No new trades, automatic closes, stop/target changes or allocation changes.')


def fmt(value, percent=False):
    if value is None: return 'Unavailable'
    return f'{value:+.1%}' if percent else f'${value:,.2f}'


def render(report):
    h=report['holdings']
    lines=['# Friday Weekend Hold Review','',f"As of {report['as_of']} · Next session: {report['next_session']}",'',
        report['advisory'], '', f"Holdings last broker statement: {h.get('broker_as_of') or 'Unknown'}. {h['warning']}",'',
        f"{report['position_count']} recorded positions; {report['priced_positions']} freshly priced. Gross open P/L: {fmt(report['pnl_dollars'])} (priced positions only).",'']
    if report.get('research_cutoff'):
        lines += ['Stock research through '+datetime.fromisoformat(report['research_cutoff']).astimezone(ET).strftime('%Y-%m-%d %H:%M %Z')+'; today\'s daily bar remains provisional.','']
    header=''.join('<p>'+html.escape(s)+'</p>' for s in lines[2:] if s)
    cards=[]
    for r in report['positions']:
        title=f"{r['ticker']} {r['expiration']} ${r['strike']:g} {r['option_strategy']} × {r['contracts']} — {r['guidance']}"
        details=[f"Open gain/loss: {fmt(r.get('pnl_dollars'))} / {fmt(r.get('pnl_pct'),True)}; bid-based P/L: {fmt(r.get('profit_at_bid'))}.",
            f"Option midpoint: {fmt(r.get('mark'))}; bid/ask: {fmt(r['quote'].get('bid'))} / {fmt(r['quote'].get('ask'))}; quote time: {r['quote'].get('quote_at') or 'Unavailable'}.",
            f"Reference target / recorded stop: {fmt(r['target'])} / {fmt(r['stop'])}. Confirm current OCO in broker.",
            f"Remaining gain to target: {fmt(r.get('reward_to_target'))}; potential giveback to stop: {fmt(r.get('giveback_to_stop'))}.",
            f"Current bid value exposed to weekend risk: {fmt(r.get('premium_at_risk'))}. Stop orders do not cap weekend losses.",
            f"Refreshed thesis: {r['research'].get('direction','Unavailable')}; {r['research'].get('basis','Fresh evidence unavailable')}.",
            f"Earnings: {r['earnings_date'] or 'Unknown'}. {r['events_status']}."]+r['reasons']
        if r.get('spy_return') is not None:
            stock=r['research']['intraday']['return_from_open']
            hour=r['research'].get('last_hour',{}).get('return_from_open')
            details.insert(6,f"Stock move today: {fmt(stock,True)}; last hour: {fmt(hour,True)}; SPY today: {fmt(r['spy_return'],True)}.")
        lines += ['## '+title,'']+['- '+s for s in details]+['']
        color={'HOLD':'#12623d','REASSESS':'#805300','CONSIDER CLOSING':'#a12626'}[r['guidance']]
        cards.append(f'<section><h2 style="color:{color}">{html.escape(title)}</h2><ul>'+''.join('<li>'+html.escape(s)+'</li>' for s in details)+'</ul></section>')
    if not report['positions']:
        lines+=['No open positions are recorded. Confirm the holdings source is current.','']
        cards.append('<p>No open positions are recorded. Confirm the holdings source is current.</p>')
    clusters=report['exposure_clusters']
    exposure=['Shared '+c['kind']+': '+c['name']+' — '+', '.join(c['tickers'])+' ('+c['direction']+'); premium cost '+fmt(c['premium_cost']) for c in clusters]
    exposure=exposure or ['No shared classified exposure found. Unknown classifications and correlations are not measured.']
    lines+=['## Shared exposure','']+['- '+s for s in exposure]+['','No broad event-calendar clearance is implied. '+report['rules']]
    page='<!doctype html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;max-width:950px;margin:24px auto;color:#182431"><h1>Friday Weekend Hold Review</h1>'+header+''.join(cards)+'<h2>Shared exposure</h2><ul>'+''.join('<li>'+html.escape(s)+'</li>' for s in exposure)+'</ul><p>'+html.escape(report['rules'])+'</p></body></html>'
    return '\n'.join(lines)+'\n',page


def collect(positions, now, session):
    from schwab.market_data_client import get_option_quotes, get_normalized_price_history
    from schwab.market_token_manager import get_access_token
    from opening_hour import fetch_history
    from decision_enrichment import get_next_earnings_date
    token=get_access_token()
    symbols={p['contract_symbol']:p['ticker'].ljust(6)+p['contract_symbol'][len(p['ticker']):] for p in positions}
    quotes={}; evidence={}; research={}; earnings={}; failures=[]
    end=now.astimezone(timezone.utc).replace(second=0,microsecond=0)
    for ticker in sorted({p['ticker'] for p in positions}|{'SPY'}):
        try:
            daily=get_normalized_price_history(ticker,period=2)
            intraday=fetch_history(ticker,session['open'],end,token)
            research[ticker]=fresh_research(ticker,daily,intraday,now,session)
            evidence[ticker]=dict(daily=daily,intraday=intraday)
        except Exception as exc:
            research[ticker]=dict(status='FETCH_FAILED',error_type=type(exc).__name__)
        if ticker!='SPY':
            try:
                value=get_next_earnings_date(ticker)
                earnings[ticker]=value.isoformat() if value and value>=now.astimezone(ET).date() else None
            except Exception:
                earnings[ticker]=None
    # Quotes last: slower stock/calendar requests must not age the option snapshot.
    for offset in range(0,len(symbols),50):
        keys=list(symbols)[offset:offset+50]
        try:
            raw=get_option_quotes([symbols[k] for k in keys],timeout_seconds=10,cached_auth_only=True)
            receipt=datetime.now(timezone.utc)
            normalized={''.join(k.split()):v for k,v in raw.items()}
            for key in keys:
                quotes[key]={**normalize_quote(normalized.get(key,{}),receipt),'received_at':receipt.isoformat()}
        except Exception as exc:
            failures.append(dict(stage='option_quotes',error_type=type(exc).__name__))
    return quotes,research,earnings,dict(market_evidence=evidence,failures=failures,research_cutoff=now.isoformat())


def run(root=ROOT, *, send=False, scheduled=False, now=None, collector=collect):
    fixed=now is not None
    now=now or datetime.now(timezone.utc)
    session=session_info(now)
    if not session or not session['open']<=now<session['close'] or (scheduled and not scheduled_due(now,session)):
        return dict(status='OUTSIDE_REVIEW_WINDOW')
    root=Path(root); out=root/'reports/weekend_review'/now.astimezone(ET).date().isoformat()
    out.mkdir(parents=True,exist_ok=True)
    # Lock is process-owned, not a stale sentinel; serializes send/receipt writes.
    import msvcrt
    with (out/'run.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1): lock.write(b'0'); lock.flush()
        lock.seek(0)
        try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError: return dict(status='ALREADY_RUNNING')
        try:
            receipt=out/'delivery.json'
            if send and receipt.exists():
                state=json.loads(receipt.read_text())
                return dict(status='ALREADY_SENT' if state['status']=='SENT' else 'DELIVERY_UNCERTAIN_REQUIRES_REVIEW')
            positions,holdings=read_holdings(root,now)
            plans=load_plans(root/'data/trade_journal.csv',positions,now) if positions else {}
            quotes,research,earnings,evidence=collector(positions,now,session) if positions else ({},{},{},{})
            receipt_time=now if fixed else datetime.now(timezone.utc)
            if send and not scheduled_due(receipt_time,session):
                return dict(status='SEND_WINDOW_EXPIRED')
            report=build_report(positions,holdings,plans,quotes,research,earnings,receipt_time,session)
            report['research_cutoff']=now.isoformat()
            report['input_evidence']=evidence
            identifier=uuid4().hex
            report_path=out/f'weekend_review_{identifier}.md'
            markdown,page=render(report)
            report_path.write_text(markdown,encoding='utf-8')
            report_path.with_suffix('.html').write_text(page,encoding='utf-8')
            report_path.with_suffix('.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
            if send:
                current=now if fixed else datetime.now(timezone.utc)
                if not scheduled_due(current,session):
                    return dict(status='SEND_WINDOW_EXPIRED',report=str(report_path))
                if hashlib.sha256((root/'data/paper_portfolio.csv').read_bytes()).hexdigest()!=holdings['portfolio_sha256']:
                    return dict(status='HOLDINGS_CHANGED_DURING_REVIEW',report=str(report_path))
                # Never auto-resend an ambiguous SMTP transaction after a crash.
                receipt.write_text(json.dumps(dict(status='SENDING',report=str(report_path),at=current.isoformat())))
                from email_reporter import send_email_report
                send_email_report(report_path,subject='Project Stonks — Friday Weekend Hold Review')
                receipt.write_text(json.dumps(dict(status='SENT',report=str(report_path),at=datetime.now(timezone.utc).isoformat())))
            return dict(status='SENT' if send else 'PREVIEW',report=str(report_path))
        finally:
            lock.seek(0); msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send',action='store_true',help='Email the configured recipient during the Friday review window')
    parser.add_argument('--scheduled',action='store_true',help='Guard normal/early-close review time')
    args=parser.parse_args()
    try:
        result=run(send=args.send,scheduled=args.scheduled)
    except Exception as exc:
        print(json.dumps(dict(status='FAILED',error_type=type(exc).__name__)))
        raise SystemExit(1) from None
    print(json.dumps(result))
    if result['status'] in ('SEND_WINDOW_EXPIRED','HOLDINGS_CHANGED_DURING_REVIEW','DELIVERY_UNCERTAIN_REQUIRES_REVIEW'):
        raise SystemExit(1)


if __name__=='__main__':
    main()
