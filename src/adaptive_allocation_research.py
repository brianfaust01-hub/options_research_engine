"""Offline allocation architecture evidence. Not imported by production or shadows.

Separate broad opportunity cohorts, actual selected-trade payoff estimation,
and portfolio-policy evidence. No synthetic fills or production configuration writes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import csv
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET=ZoneInfo('America/New_York')
VERSION='ALLOCATION-ARCHITECTURE-RESEARCH-2026-11-24-v1'
RAW_FEATURES=('ResearchScore','institutional_trade_score','execution_score','broker_delta',
    'implied_volatility','spread_pct','execution_entry_price','market_score','breadth_score',
    'Return1D','Return3D','Return5D')
FEATURE_NAMES=RAW_FEATURES+('put',)
RIDGES=(.1,1.,10.,100.)
MIN_TRAIN=30
MIN_DATES=8


def number(v):
    try:
        n=float(v)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):return None


def at(v):
    d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
    return d.replace(tzinfo=ET) if d.tzinfo is None else d.astimezone(ET)


def flag(v):
    return str(v).lower() in ('true','1','1.0')


def feature_vector(row):
    put=row.get('option_strategy')=='Long Put'
    direction=-1 if put else 1
    result=[]
    for key in RAW_FEATURES:
        n=number(row.get(key))
        if n is not None and key.startswith('Return'):n*=direction
        result.append(n)
    return result+[float(put)]


def cohort(r):
    """Recorded failure mechanisms, not a post-hoc good/bad-trade label."""
    if r.get('portfolio_action') in ('OPEN','ADD'):return 'RECOMMENDED_NEW_OR_ADD'
    if r.get('option_strategy') not in ('Long Call','Long Put'):return 'NO_SELECTED_DIRECTIONAL_CONTRACT'
    opening=r.get('OpeningHourStatus')
    if opening=='CONTRADICTED':return 'DIRECTION_CONTRADICTED'
    if opening=='DATA_UNAVAILABLE':return 'ENTRY_DATA_UNAVAILABLE'
    if flag(r.get('OilRiskBlocked')):return 'PORTFOLIO_OIL_EXPOSURE_BLOCK'
    if flag(r.get('earnings_allocation_override')):return 'EVENT_RISK_BLOCK'
    if r.get('earnings_status') not in ('CONFIRMED','UNKNOWN') or opening=='NOT_REVIEWED_POOL':
        return 'NOT_FULLY_EVALUATED'
    reason=str(r.get('portfolio_action_reason',''))
    if 'invalid contract quantity' in reason and (number(r.get('portfolio_score')) or 0)>=70 and (number(r.get('execution_score')) or 0)>=70:
        return 'QUANTITY_OR_EXISTING_EXPOSURE_BLOCK'
    if (number(r.get('execution_score')) or 0)<70:return 'EXECUTION_SCORE_BLOCK'
    if not (number(r.get('execution_entry_price')) or 0)>0:return 'INVALID_CONTRACT_PRICE'
    if 'forward score' in reason or 'portfolio-context score' in reason:return 'SCORE_OR_OPERATIONAL_HURDLE_BLOCK'
    if any(s in reason for s in ('active-position limit','aggregate expected loss','full-premium utilization','concentration limit','theme/correlation proxy limit')):
        return 'RECORDED_QUALIFIED_PORTFOLIO_CAPACITY_BLOCK'
    if 'below minimum material position value' in reason:return 'MINIMUM_POSITION_VALUE_BLOCK'
    return 'OTHER_RECORDED_UNFUNDED'


def journal_key(day,r):
    return (day,str(r.get('ticker','')).upper(),r.get('option_strategy'),str(r.get('expiration',''))[:10],
        number(r.get('strike')),number(r.get('execution_entry_price')),number(r.get('institutional_trade_score')),
        number(r.get('portfolio_score')),number(r.get('execution_score')))


def project_journal(path, days):
    byid={};index=defaultdict(set);conflicts=set()
    csv.field_size_limit(20_000_000)
    fields=set(RAW_FEATURES)|{'RecommendationID','RecommendationDate','ticker','expiration','strike',
        'option_strategy','portfolio_score','risk_mode','PolicyEvidenceFingerprint','OpeningHourPolicyVersion'}
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:
        for raw in csv.DictReader(handle):
            day=raw.get('RecommendationDate','')[:10].replace('-','')
            if day not in days:continue
            rid=raw.get('RecommendationID')
            if not rid:continue
            row={k:raw.get(k,'') for k in fields}
            if rid in byid and byid[rid]!=row:conflicts.add(rid)
            byid.setdefault(rid,row)
            index[journal_key(day,raw)].add(rid)
    for rid in conflicts:byid.pop(rid,None)
    return byid,index,conflicts


def actual_trades(value, journal):
    groups=defaultdict(list)
    for u in value['units']:
        if u['side']==1 and u.get('entry_at'):
            groups[(u['entry_at'],u['ticker'],u['expiration'],u['strike'],u['option_type'])].append(u)
    result=[];excluded=Counter()
    for key,units in sorted(groups.items()):
        if any(u['status']!='CLOSED' for u in units):excluded['STILL_OPEN']+=1;continue
        ids={u.get('recommendation_id') for u in units}
        if len(ids)!=1 or next(iter(ids)) not in journal:excluded['UNRESOLVED_OR_CONFLICTED_ORIGIN']+=1;continue
        raw=journal[next(iter(ids))];decision=raw['RecommendationDate']
        if at(decision)>at(key[0]):excluded['RECOMMENDATION_AFTER_ENTRY']+=1;continue
        debit=sum(u['entry']*100 for u in units)
        net=sum(u['net_period_contribution'] for u in units)
        result.append(dict(id=hashlib.sha256(str(key).encode()).hexdigest()[:20],
            recommendation_id=next(iter(ids)),ticker=key[1],decision_at=decision,
            entry_at=key[0],exit_at=max(u['exit_at'] for u in units),
            entry_date=key[0][:10],quantity=len(units),debit=debit,net_pnl=net,
            realized_return=net/debit,features=feature_vector(raw),risk_mode=raw.get('risk_mode'),
            direction=raw.get('option_strategy'),policy=raw.get('PolicyEvidenceFingerprint'),
            opening_hour_version=raw.get('OpeningHourPolicyVersion'),
            origin_link_status=units[0].get('link_status')))
    return result,dict(excluded)


def date_weights(rows):
    count=Counter(at(r['decision_at']).date() for r in rows)
    return np.array([1/count[at(r['decision_at']).date()] for r in rows])


def prepare(rows):
    x=np.array([[np.nan if v is None else v for v in r['features']] for r in rows],dtype=float)
    w=date_weights(rows)
    missing=np.isnan(x)
    observed=np.sum(~missing,axis=0)
    # All preprocessing is fitted only on this training slice.
    means=np.nansum(x,axis=0)/np.maximum(observed,1)
    filled=np.where(missing,means,x)
    scales=np.std(filled,axis=0);scales=np.where(scales>1e-9,scales,1.)
    z=np.column_stack((np.ones(len(rows)),(filled-means)/scales,missing.astype(float)))
    return z,w,means,scales


def fit(rows,ridge):
    z,w,means,scales=prepare(rows)
    y=np.array([r['realized_return'] for r in rows])
    penalty=np.eye(z.shape[1])*ridge;penalty[0,0]=0
    beta=np.linalg.solve(z.T@(w[:,None]*z)+penalty,z.T@(w*y))
    return dict(beta=beta,means=means,scales=scales,ridge=ridge)


def predict(model,row):
    x=np.array([np.nan if v is None else v for v in row['features']],dtype=float)
    missing=np.isnan(x);x=np.where(missing,model['means'],x)
    z=np.r_[1.,(x-model['means'])/model['scales'],missing.astype(float)]
    return float(z@model['beta'])


def eligible_training(rows,decision):
    cutoff=at(decision)
    return [r for r in rows if at(r['decision_at'])<cutoff and at(r['exit_at'])<cutoff]


def select_ridge(train):
    dates=sorted({at(r['decision_at']).date() for r in train})
    folds=[]
    for fraction in (.6,.8):
        boundary=dates[min(len(dates)-1,int(len(dates)*fraction))]
        start=datetime.combine(boundary,datetime.min.time(),tzinfo=ET)
        inner=[r for r in train if at(r['exit_at'])<start and at(r['decision_at'])<start]
        val=[r for r in train if at(r['decision_at'])>=start]
        if len(inner)>=20 and val:folds.append((inner,val))
    if not folds:return 100.,[], 'NO_VALID_INNER_SPLIT_CONSERVATIVE_REGULARIZATION'
    losses={};residuals={}
    for ridge in RIDGES:
        errors=[]
        for inner,val in folds:
            model=fit(inner,ridge)
            errors.extend((at(r['decision_at']).date(),abs(predict(model,r)-r['realized_return'])) for r in val)
        grouped=defaultdict(list)
        for date,error in errors:grouped[date].append(error)
        losses[ridge]=np.mean([np.mean(v) for v in grouped.values()])
        residuals[ridge]=[e for _,e in errors]
    # Favor stronger regularization for exact ties, never optimize on outer outcomes.
    chosen=min(RIDGES,key=lambda r:(losses[r],-r))
    return chosen,residuals[chosen],'NESTED_CHRONOLOGICAL_TRAIN_ONLY'


def walk_forward(rows):
    predictions=[];skipped=Counter()
    for row in sorted(rows,key=lambda r:(at(r['decision_at']),r['id'])):
        train=eligible_training(rows,row['decision_at'])
        dates={at(r['decision_at']).date() for r in train}
        if len(train)<MIN_TRAIN or len(dates)<MIN_DATES:
            skipped['WARMUP_INSUFFICIENT_CLOSED_TRADES_OR_DATES']+=1;continue
        ridge,errors,status=select_ridge(train)
        model=fit(train,ridge);prediction=predict(model,row)
        w=date_weights(train)
        base=float(np.average([r['realized_return'] for r in train],weights=w))
        contextual=[r for r in train if r['risk_mode']==row['risk_mode'] and r['direction']==row['direction']]
        context_dates=len({at(r['decision_at']).date() for r in contextual})
        predictions.append(dict(**row,prediction=prediction,prior_mean=base,training_groups=len(train),
            training_dates=len(dates),latest_training_exit=max(r['exit_at'] for r in train),ridge=ridge,
            tuning_status=status,context_groups=len(contextual),context_dates=context_dates,
            empirical_validation_absolute_error_p80=float(np.quantile(errors,.8)) if errors else None,
            extrapolation_warning=context_dates<MIN_DATES))
    return predictions,dict(skipped)


def performance(rows):
    if not rows:return dict(n=0)
    weights=date_weights(rows)
    model_error=[abs(r['prediction']-r['realized_return']) for r in rows]
    baseline_error=[abs(r['prior_mean']-r['realized_return']) for r in rows]
    retained=[r for r in rows if r['prediction']>0]
    skipped=[r for r in rows if r['prediction']<=0]
    return dict(n=len(rows),dates=len({at(r['decision_at']).date() for r in rows}),
        date_weighted_model_mae=float(np.average(model_error,weights=weights)),
        date_weighted_prior_mean_mae=float(np.average(baseline_error,weights=weights)),
        actual_baseline_net=sum(r['net_pnl'] for r in rows),
        positive_forecast_retained_groups=len(retained),positive_forecast_retained_actual_net=sum(r['net_pnl'] for r in retained),
        missed_winning_dollars=sum(max(0,r['net_pnl']) for r in skipped),
        avoided_losing_dollars=-sum(min(0,r['net_pnl']) for r in skipped),
        warning='Selected actual-trade screen only; not rejected-trade or self-financing portfolio returns')


def opportunity_panel(manifest,journal,index,conflicts):
    fields=set(RAW_FEATURES)|{'ticker','option_strategy','expiration','strike','portfolio_score','portfolio_action',
        'portfolio_action_reason','allocation_decision','RecommendationID','OpeningHourStatus','OilRiskBlocked',
        'earnings_allocation_override','earnings_status','risk_mode','market_regime'}
    rows=[]
    for source in manifest:
        path=Path(source['candidates']);day=path.name.split('_')[2]
        frame=pd.read_csv(path,usecols=lambda k:k in fields,low_memory=False)
        for raw in frame.to_dict('records'):
            rid=raw.get('RecommendationID')
            if not isinstance(rid,str) or rid not in journal:
                matches=index.get(journal_key(day,raw),set())-conflicts
                rid=next(iter(matches)) if len(matches)==1 else None
                provenance='UNIQUE_CONTRACT_DATE_FEATURE_INFERENCE' if rid else 'UNRESOLVED_OR_AMBIGUOUS'
            else:provenance='EXACT_SOURCE_ID'
            origin=journal.get(rid,{})
            rows.append(dict(date=day,ticker=raw.get('ticker'),option_strategy=raw.get('option_strategy'),
                cohort=cohort(raw),recommendation_id=rid,join_status=provenance,
                raw_quality=number(raw.get('institutional_trade_score')),portfolio_score=number(raw.get('portfolio_score')),
                recorded_reason=raw.get('portfolio_action_reason'),risk_mode=raw.get('risk_mode'),
                features=feature_vector(origin) if origin else None))
    return rows


def sanitize(v):
    if isinstance(v,dict):return {str(k):sanitize(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [sanitize(x) for x in v]
    if hasattr(v,'item'):return sanitize(v.item())
    if isinstance(v,float) and not math.isfinite(v):return None
    return v


def run(attribution,penalties,journal_path,hindsight_path,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    sources={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (attribution,penalties,journal_path,hindsight_path)}
    actual=json.loads(Path(attribution).read_text());replay=json.loads(Path(penalties).read_text())
    days={d['date'] for d in replay['days']}
    journal,index,conflicts=project_journal(journal_path,days)
    trades,excluded=actual_trades(actual,journal)
    predictions,warmup=walk_forward(trades)
    panel=opportunity_panel(replay['source_manifest'],journal,index,conflicts)
    # Whole panel cohorts have stock diagnostics, not broker-return labels.
    hs=pd.read_csv(hindsight_path,usecols=lambda x:x in ('RecommendationID','RecommendationDate','Ticker','Direction') or x.startswith(('Horizon3D','Horizon5D','Horizon7D')),low_memory=False)
    from hindsight_analytics import build_thesis_episodes
    episodes=build_thesis_episodes(hs)
    outcomes={r['RecommendationID']:r for r in episodes.to_dict('records')}
    cohort_outcomes={}
    for label in sorted({r['cohort'] for r in panel}):
        observations=[r for r in panel if r['cohort']==label]
        horizons={}
        for horizon in (3,5,7):
            seen=set();values=[];pending=missing=0
            for r in observations:
                h=outcomes.get(r['recommendation_id'])
                if h is None:missing+=1;continue
                if h['ThesisEpisodeID'] in seen:continue
                seen.add(h['ThesisEpisodeID'])
                value=number(h.get(f'Horizon{horizon}DDirectionalReturnPct'))
                if h.get(f'Horizon{horizon}DStatus')!='COMPLETE' or value is None:pending+=1;continue
                values.append(value)
            horizons[str(horizon)]=dict(episodes=len(seen),mature=len(values),pending=pending,unmatched_rows=missing,
                positive=sum(v>0 for v in values),negative=sum(v<0 for v in values),
                mean_directional_stock_return=sum(values)/len(values) if values else None)
        cohort_outcomes[label]=dict(observations=len(observations),horizons=horizons)
    summaries=dict(overall=performance(predictions))
    for mode in sorted({r['risk_mode'] for r in predictions}):summaries[mode]=performance([r for r in predictions if r['risk_mode']==mode])
    by_date=defaultdict(float)
    for r in trades:by_date[r['entry_date']]+=r['net_pnl']
    result=dict(version=VERSION,scope='RESEARCH_ONLY_NO_PRODUCTION_OR_SHADOW_CONNECTION',
        architecture='Opportunity quality -> conditional payoff/uncertainty -> portfolio choice and exposure; independent feasibility and risk constraints',
        actual_training_groups=len(trades),actual_training_dates=len(by_date),excluded_actual=excluded,
        actual_label_selection='Only broker-executed long trades have actual realized option-return labels; this model is selection-biased outside that population',
        training_features=FEATURE_NAMES,minimum_training_groups=MIN_TRAIN,minimum_training_dates=MIN_DATES,
        ridge_grid=RIDGES,model_comparison=summaries,warmup=warmup,
        opportunity_cohorts=cohort_outcomes,conflicted_journal_ids=len(conflicts),
        opportunity_join_coverage=dict(Counter(r['join_status'] for r in panel)),
        sources=sources,predictions=predictions,
        limitations=['Chronological labels use only prior closed actual trades. Nested tuning uses only that training set; no future realized label is fitted.',
          'Return estimates are not calibrated win probabilities. Validation error scale is not a calibrated confidence interval.',
          'Missing/novel market contexts are flagged. No prediction or positive forecast authorizes an order or position size.',
          'Panel stock outcomes do not measure option fills, stops, premiums, fees or portfolio opportunity cost; cohort membership and overlaps are not randomized.',
          'Whole alternate-portfolio returns require matched quote coverage, order assumptions, incumbent replacement outcomes, cash propagation and feasible quantities. No such profit is manufactured here.',
          'The panel uses archived initial checks; a historical execution score is not proof of a live executable quote or depth.',
          'No model was fitted on synthetic rejected-trade option returns. Liquidity/data/event failures are not relabeled missed winners.'])
    for p,h in sources.items():
        if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise ValueError('Input changed during research: '+p)
    for name,value in [('review.json',result),('opportunity_panel.json',panel)]:
        with (output/name).open('x',encoding='utf-8') as handle:json.dump(sanitize(value),handle,indent=2,allow_nan=False)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('attribution','penalties','journal','hindsight','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();r=run(a.attribution,a.penalties,a.journal,a.hindsight,a.output)
    print(json.dumps(sanitize({k:v for k,v in r.items() if k not in ('predictions','sources','opportunity_cohorts')}),indent=2))
