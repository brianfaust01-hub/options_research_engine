"""Exploratory dollar-based entry-filter review; never changes trading rules.

Chronological selection with a purged boundary. Frozen candidate menu,
training winner-dollar preservation, holdout costs and date-block uncertainty.
Historical matching remains inferred; this is not a prospective trial.
"""
from collections import defaultdict
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import median

FEATURES=['ResearchScore','portfolio_score','execution_score','broker_delta','implied_volatility',
          'spread_pct','theta_drag_pct_per_day','market_regime','breadth_regime','ResearchRankingTimeEdge']
RULES=[('Research score >=90','ResearchScore','ge',90),
       ('Portfolio score >=80','portfolio_score','ge',80),
       ('Portfolio score >=85','portfolio_score','ge',85),
       ('Execution score >=70','execution_score','ge',70),
       ('Execution score >=80','execution_score','ge',80),
       ('Absolute delta >=0.25','abs_delta','ge',.25),
       ('Absolute delta >=0.35','abs_delta','ge',.35),
       ('Moderate delta 0.35-0.50','abs_delta','range',(.35,.50)),
       ('IV <=40%','implied_volatility','le',.40),
       ('IV <=60%','implied_volatility','le',.60),
       ('Spread <=5%','spread_pct','le',.05),
       ('Theta drag <=1%/day','theta_drag_pct_per_day','le',.01),
       ('Entry within 30 minutes','entry_delay_minutes','le',30),
       ('Entry within 60 minutes','entry_delay_minutes','le',60)]


def number(v):
    try:
        result=float(v)
        return result if math.isfinite(result) else None
    except (ValueError,TypeError):return None


def trades_from_attribution(value,journal):
    ids={r.get('recommendation_id') for r in value['units'] if r.get('recommendation_id')}
    projected={};csv.field_size_limit(20_000_000)
    with Path(journal).open(encoding='utf-8-sig',newline='') as handle:
        for row in csv.DictReader(handle):
            rid=row.get('RecommendationID')
            if rid in ids:projected.setdefault(rid,{k:row.get(k) for k in FEATURES})
    groups=defaultdict(list);open_keys=set()
    for r in value['units']:
        if r['side']!=1 or not r['entry_at']:continue
        k=(r['entry_at'],r['ticker'],r['expiration'],r['strike'],r['option_type'])
        if r['status']=='OPEN':open_keys.add(k)
        else:groups[k].append(r)
    trades=[]
    for k,rows in sorted(groups.items()):
        if k in open_keys:continue
        r=rows[0];rid=r.get('recommendation_id');raw=projected.get(rid,{})
        feature={key:number(raw.get(key)) for key in FEATURES if key not in ('market_regime','breadth_regime')}
        feature.update({key:raw.get(key) for key in ('market_regime','breadth_regime')})
        d=feature.get('broker_delta');feature['abs_delta']=abs(d) if d is not None else None
        feature['entry_delay_minutes']=(datetime.fromisoformat(r['entry_at'])-datetime.fromisoformat(r['recommendation_at'])).total_seconds()/60 if r.get('recommendation_at') else None
        trades.append({'id':hashlib.sha256(str(k).encode()).hexdigest()[:20],
            'ticker':k[1],'direction':k[4],'entry_at':k[0],'entry_date':k[0][:10],
            'closed_at':max(p['exit_at'] for p in rows),'quantity':len(rows),
            'net_pnl':sum(p['net_period_contribution'] for p in rows),
            'within_recorded_quantity_pnl':sum(p['net_period_contribution'] for p in rows if not p.get('above_recorded_recommendation_quantity')),
            'entry_debit':sum(p['entry']*100+p['entry_fee'] for p in rows),
            'recommendation_id':rid,'link_status':r['link_status'],
            'core_policy_fingerprint':r.get('core_policy_fingerprint'),
            'exit_order_types':sorted(set(p['exit_order_type'] for p in rows)),
            'features':feature})
    return trades,len(open_keys)


def keeps(trade,rule):
    _,feature,op,threshold=rule;value=trade['features'].get(feature)
    if value is None:return True # Never make missing historical fields a benefit.
    if op=='ge':return value>=threshold
    if op=='le':return value<=threshold
    return threshold[0]<value<=threshold[1]


def metrics(rows):
    wins=[r['net_pnl'] for r in rows if r['net_pnl']>0];losses=[r['net_pnl'] for r in rows if r['net_pnl']<0]
    return {'groups':len(rows),'dates':len({r['entry_date'] for r in rows}),
        'net_pnl':sum(r['net_pnl'] for r in rows),'winning_dollars':sum(wins),
        'losing_dollars':sum(losses),'win_rate':len(wins)/len(rows) if rows else None,
        'profit_factor':sum(wins)/-sum(losses) if losses else None,
        'within_recorded_quantity_pnl':sum(r['within_recorded_quantity_pnl'] for r in rows)}


def evaluate(rows,rule,large_threshold):
    kept=[r for r in rows if keeps(r,rule)];dropped=[r for r in rows if not keeps(r,rule)]
    baseline=metrics(rows);result=metrics(kept);excluded=metrics(dropped)
    large=[r for r in rows if r['net_pnl']>=large_threshold]
    retained_large=[r for r in large if keeps(r,rule)]
    avoided=-sum(min(0,r['net_pnl']) for r in dropped);lost=sum(max(0,r['net_pnl']) for r in dropped)
    delta=result['net_pnl']-baseline['net_pnl']
    worst_avoided=max((-r['net_pnl'] for r in dropped if r['net_pnl']<0),default=0)
    return {'baseline':baseline,'kept':result,'dropped':excluded,'avoided_loss_dollars':avoided,
        'forgone_profit_dollars':lost,'net_improvement':delta,
        'large_winners':len(large),'large_winners_retained':len(retained_large),
        'large_winner_dollars_retained':sum(r['net_pnl'] for r in retained_large)/sum(r['net_pnl'] for r in large) if large else None,
        'winner_dollars_retained':result['winning_dollars']/baseline['winning_dollars'] if baseline['winning_dollars'] else None,
        'missing_feature_groups':sum(r['features'].get(rule[1]) is None for r in rows),
        'improvement_without_largest_avoided_loss':delta-worst_avoided,
        'one_contract_net_improvement':-sum(r['net_pnl']/r['quantity'] for r in dropped),
        'within_recorded_quantity_improvement':result['within_recorded_quantity_pnl']-baseline['within_recorded_quantity_pnl'],
        'dropped_trades':[{'id':r['id'],'ticker':r['ticker'],'entry_date':r['entry_date'],'net_pnl':r['net_pnl']} for r in dropped],
        'by_direction':{d:{'baseline':metrics([r for r in rows if r['direction']==d]),
            'kept':metrics([r for r in kept if r['direction']==d])} for d in ('CALL','PUT')}}


def block_interval(rows,rule,draws=2000):
    daily=defaultdict(float)
    for r in rows:daily[r['entry_date']]+=-r['net_pnl'] if not keeps(r,rule) else 0
    values=list(daily.values())
    if len(values)<5:return None
    rng=random.Random(20261106)
    means=sorted(sum(rng.choice(values) for _ in values)/len(values) for _ in range(draws))
    return {'entry_dates':len(values),'draws':draws,'mean_daily_improvement':sum(values)/len(values),
        'low95':means[int(.025*draws)],'high95':means[int(.975*draws)],
        'limitation':'Exploratory entry-date bootstrap, unadjusted for multiple comparisons; overlapping positions can remain dependent.'}


def review(value,journal):
    journal_hash=hashlib.sha256(Path(journal).read_bytes()).hexdigest()
    rows,open_groups=trades_from_attribution(value,journal)
    if hashlib.sha256(Path(journal).read_bytes()).hexdigest()!=journal_hash:raise ValueError('Journal changed during feature projection')
    dates=sorted({r['entry_date'] for r in rows})
    if len(dates)<9:raise ValueError('Insufficient independent entry-date coverage for chronological split')
    cut=dates[(len(dates)*2)//3-1]
    train=[r for r in rows if r['entry_date']<=cut and r['closed_at'][:10]<=cut]
    purged=[r for r in rows if r['entry_date']<=cut and r['closed_at'][:10]>cut]
    holdout=[r for r in rows if r['entry_date']>cut]
    winners=sorted(r['net_pnl'] for r in train if r['net_pnl']>0)
    large=winners[int(.75*(len(winners)-1))] if winners else float('inf')
    scores=[]
    for rule in RULES:
        t=evaluate(train,rule,large);h=evaluate(holdout,rule,large)
        eligible=t['kept']['groups']>=.60*len(train) and t['dropped']['groups']>=5 and t['net_improvement']>0 and (t['winner_dollars_retained'] or 0)>=.80
        scores.append({'rule':rule[0],'spec':rule,'eligible_on_train':eligible,'train':t,'holdout':h,
            'holdout_uncertainty':block_interval(holdout,rule)})
    eligible=[r for r in scores if r['eligible_on_train']]
    selected=max(eligible,key=lambda r:r['train']['net_improvement'])['rule'] if eligible else None
    return {'status':'EXPLORATORY_NOT_DEPLOYABLE','period':{'start':value['start'],'end':value['end']},
        'split':'First two-thirds of distinct entry dates train; latest third holdout; training outcomes must close by cut date.',
        'training_cut_date':cut,'journal_sha256':journal_hash,'train':metrics(train),'holdout':metrics(holdout),'all_closed':metrics(rows),
        'purged_cross_boundary_groups':len(purged),'excluded_still_open_groups':open_groups,
        'training_large_winner_threshold':large,'selected_using_train_only':selected,'rules':scores,'trades':rows,
        'limits':['Retrospective hypothesis screen, not a preregistered forward test or proven causal improvement.',
            'All candidate rules are fixed in source before selection; no ticker blacklist, outcome-based quantity editing or stop/target optimization.',
            'Actual prices/fees/quantities are retained; skipped trades hold cash with no replacements or reinvestment.',
            'Known recommendations are contract/time inferences, not broker-confirmed intent.',
            'IV, delta, scores and spreads are recorded recommendation-time features, not necessarily the eventual fill-time market conditions.',
            'Closed-trade sampling omits open positions and may favor different holding durations; open groups are separately counted.',
            'Policy fingerprints are retained; the period spans changes, not one perfectly constant production policy.',
            'First-hour and VIX capture is too recent for this window and is not backfilled.',
            'Holdout tables for every rule are exploratory multiple comparisons; only the train-selected rule is the designated selection check.',
            'Equal-contract and recorded-quantity sensitivities are diagnostics, not guaranteed alternative fills or equal-risk portfolio returns.']}


def markdown(v):
    lines=['# Avoiding losers while preserving larger winners','',
        '**Exploratory retrospective review. No production filter changed.**','',
        f"Actual closed long-option entry groups: {v['all_closed']['groups']}; net ${v['all_closed']['net_pnl']:,.2f}. Window: {v['period']['start']} close through {v['period']['end']} close.",
        f"Train ends {v['training_cut_date']}: {v['train']['groups']} closed groups. Holdout: {v['holdout']['groups']} groups. Purged cross-boundary outcomes: {v['purged_cross_boundary_groups']}; still-open groups excluded: {v['excluded_still_open_groups']}.",
        f"Large winner threshold learned from training winners only: ${v['training_large_winner_threshold']:,.2f}. Training selection requires >=60% trade retention, >=80% winning-dollar retention, >=5 exclusions and positive dollar improvement.",
        f"Train-selected rule: **{v['selected_using_train_only'] or 'None qualified'}**.",
        '', '| Rule | Train benefit | Train winner $ retained | Holdout benefit | Holdout losses avoided | Holdout profits forgone | Holdout winner $ retained | Holdout large winners retained |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    pct=lambda p:'Unavailable' if p is None else f'{p:.1%}'
    for r in v['rules']:
        t=r['train'];h=r['holdout']
        lines.append(f"| {r['rule']} | ${t['net_improvement']:+,.2f} | {pct(t['winner_dollars_retained'])} | ${h['net_improvement']:+,.2f} | ${h['avoided_loss_dollars']:,.2f} | ${h['forgone_profit_dollars']:,.2f} | {pct(h['winner_dollars_retained'])} | {h['large_winners_retained']}/{h['large_winners']} |")
    lines+=['','## Selected rule validation','']
    chosen=next((r for r in v['rules'] if r['rule']==v['selected_using_train_only']),None)
    if chosen:
        h=chosen['holdout']
        lines+=[f"Holdout baseline ${h['baseline']['net_pnl']:,.2f}; retained trades ${h['kept']['net_pnl']:,.2f}; net difference ${h['net_improvement']:+,.2f}.",
            f"Without the largest avoided loser: ${h['improvement_without_largest_avoided_loss']:+,.2f}. One-contract sensitivity: ${h['one_contract_net_improvement']:+,.2f}; within-recorded-quantity sensitivity: ${h['within_recorded_quantity_improvement']:+,.2f}.",
            'Entry-date uncertainty: '+str(chosen['holdout_uncertainty'])]
    else:lines+=['No rule met training protection criteria. Do not select a rule solely because its holdout result looks attractive.']
    lines+=['','## Limits','',*[f'- {x}' for x in v['limits']]]
    return '\n'.join(lines)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--attribution',type=Path,required=True)
    p.add_argument('--journal',type=Path,default=Path('data/trade_journal.csv'));p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();source=args.attribution.read_bytes();value=review(json.loads(source),args.journal)
    value['source_sha256']=hashlib.sha256(source).hexdigest()
    args.output.mkdir(parents=True,exist_ok=True)
    for name,text in [('review.json',json.dumps(value,indent=2)),('review.md',markdown(value))]:
        with (args.output/name).open('x',encoding='utf-8') as handle:handle.write(text)
    print(json.dumps({k:v for k,v in value.items() if k not in ('rules','trades')},indent=2))
