"""Frozen six-week challenger: research score and direction, shadow use only.

Probabilities concern positive seven-session underlying directional returns,
not profitable options. No portfolio, order, or baseline configuration writes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from config_combination_analysis import post_fix_episode_frame

VERSION = 'SIX-WEEK-SHADOW-2026-10-29-v1'
FEATURES = ['research_score_centered', 'bullish']
ALPHA = 10.0  # one declared regularizer; no historical hyperparameter search


def design(frame):
    score = pd.to_numeric(frame['ResearchScore'], errors='coerce')
    direction = frame['Direction'].astype(str).str.upper()
    if score.isna().any() or not score.between(0,100).all() or not direction.isin(['BULLISH','BEARISH']).all():
        raise ValueError('Valid research scores and known directions required')
    return np.column_stack([np.ones(len(frame)), (score.to_numpy()-75)/25, direction.eq('BULLISH').astype(float)])


def fit(frame):
    x = design(frame); y = frame['_Return'].gt(0).to_numpy(float)
    beta = np.zeros(x.shape[1]); penalty = np.array([0., ALPHA, ALPHA])
    for _ in range(100):
        p = 1/(1+np.exp(-np.clip(x@beta,-30,30)))
        h = x.T@(x*np.maximum(p*(1-p),1e-6)[:,None])+np.diag(penalty)
        step = np.linalg.solve(h, x.T@(p-y)+penalty*beta)
        beta -= step
        if abs(step).max()<1e-8: break
    return beta.tolist()


def predict(frame, coefficients):
    return 1/(1+np.exp(-np.clip(design(frame)@np.asarray(coefficients),-30,30)))


def training_before(frame, date):
    # A full business-day embargo: labels must predate the prior business day.
    cutoff = pd.Timestamp(date).normalize()-pd.offsets.BDay(1)
    maturity = pd.to_datetime(frame['Horizon7DEvaluationDate'], errors='coerce', format='mixed').dt.normalize()
    return frame[frame['_Date'].lt(cutoff) & maturity.lt(cutoff)].copy()


def metrics(frame, col):
    p = np.clip(frame[col].to_numpy(float),1e-8,1-1e-8); y=frame['_Return'].gt(0).to_numpy(float)
    pos=p[y==1]; neg=p[y==0]
    auc=float(((pos[:,None]>neg).sum()+.5*(pos[:,None]==neg).sum())/(len(pos)*len(neg))) if len(pos)*len(neg) else None
    return {'n':len(frame),'dates':int(frame['_Date'].nunique()),'brier':float(np.mean((p-y)**2)),
            'log_loss':float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))), 'auc':auc,
            'mean_prediction':float(p.mean()),'win_rate':float(y.mean())}


def evaluate(frame):
    rows=[]; folds=[]
    for date in sorted(frame['_Date'].unique()):
        train=training_before(frame,date); test=frame[frame['_Date'].eq(date)].copy()
        if len(train)<50 or train['_Date'].nunique()<3 or train['_Return'].gt(0).nunique()<2: continue
        test['challenger_probability']=predict(test,fit(train))
        test['base_rate_probability']=(train['_Return'].gt(0).sum()+1)/(len(train)+2)
        # A score is not a probability: this is explicitly a naive comparator.
        test['naive_score_probability']=pd.to_numeric(test['ResearchScore'])/100
        test['train_n']=len(train);test['train_latest_outcome']=str(pd.to_datetime(train['Horizon7DEvaluationDate']).max().date())
        folds.append({'test_date':str(pd.Timestamp(date).date()),'train_n':len(train),'test_n':len(test),'train_last_outcome':test['train_latest_outcome'].iloc[0]})
        rows.append(test)
    if not rows: raise ValueError('Insufficient chronological validation data')
    oos=pd.concat(rows,ignore_index=True)
    result={'version':VERSION,'validation':'expanding chronological; outcome-date purge plus one-business-day embargo',
            'folds':folds,'metrics':{c:metrics(oos,c) for c in ['challenger_probability','base_rate_probability','naive_score_probability']},
            'direction':{d:metrics(g,'challenger_probability') for d,g in oos.groupby('Direction')}}
    selections={}
    for name,col in [('challenger','challenger_probability'),('legacy','ResearchScore')]:
        selected=oos.sort_values(['_Date',col,'RecommendationID'],ascending=[True,False,True]).groupby('_Date').head(3)
        r=selected['_Return']; loss=-r[r<0].sum()
        selections[name]={'n':len(r),'mean_underlying_directional_return':float(r.mean()),'win_rate':float(r.gt(0).mean()),'profit_factor':float(r[r>0].sum()/loss) if loss else None,'worst':float(r.min())}
    result['top3_matched_dates']=selections
    result['daily_loss_delta']=[{'date':str(pd.Timestamp(d).date()),'brier_delta':float(((g.challenger_probability-g._Return.gt(0))**2-(g.base_rate_probability-g._Return.gt(0))**2).mean())} for d,g in oos.groupby('_Date')]
    return result,oos


def build(source,output):
    source=Path(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    frame=post_fix_episode_frame(pd.read_csv(source,low_memory=False))
    result,oos=evaluate(frame)
    # Only labels already available at the checkpoint enter the frozen artifact.
    mature=frame[pd.to_datetime(frame.Horizon7DEvaluationDate,errors='coerce').lt(pd.Timestamp('2026-10-30'))]
    model={'version':VERSION,'mode':'SHADOW_ONLY','target':'positive seven-session underlying directional return',
           'features':FEATURES,'coefficients':fit(mature),'regularization':ALPHA,'training_n':len(mature),
           'training_latest_outcome':str(pd.to_datetime(mature.Horizon7DEvaluationDate).max().date()),
           'training_base_rate':float((mature['_Return'].gt(0).sum()+1)/(len(mature)+2)),
           'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'training_source':str(source.resolve()),
           'activation_not_before':'2026-11-01','promotion_allowed':False,
           'limitations':['Discovery reused previously inspected history; forward shadow is confirmatory','Underlying probability is not option profitability','No dynamic stop, target or allocation changes justified by this artifact']}
    (output/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (output/'challenger.json').write_text(json.dumps(model,indent=2),encoding='utf-8')
    oos.to_csv(output/'chronological_predictions.csv',index=False)
    return result


def shadow(journal,model):
    if model.get('mode')!='SHADOW_ONLY' or model.get('version')!=VERSION: raise ValueError('Unsupported shadow artifact')
    frame=journal.drop_duplicates('RecommendationID',keep='last').copy()
    date=pd.to_datetime(frame.RecommendationDate,errors='coerce',format='mixed')
    latest=date.dt.normalize().max()
    frame['Direction']=frame.Direction.astype(str).str.upper().str.strip()
    valid=date.notna() & frame.Direction.isin(['BULLISH','BEARISH']) & pd.to_numeric(frame.ResearchScore,errors='coerce').between(0,100)
    action=frame.get('Action',frame.get('action',pd.Series('',index=frame.index))).fillna('').astype(str).str.casefold()
    opportunity=frame.get('OpportunityType',frame.get('opportunity_type',pd.Series('',index=frame.index))).fillna('').astype(str).str.casefold()
    strategy=frame.get('OptionStrategy',frame.get('option_strategy',pd.Series('',index=frame.index))).fillna('').astype(str).str.casefold()
    valid &= action.eq('evaluate options') & opportunity.str.contains('candidate',regex=False) & strategy.isin(['long call','long put'])
    frame=frame[valid].copy();date=date[valid]
    if date.empty: raise ValueError('No valid candidates')
    frame=frame[date.dt.normalize().eq(latest)].copy()
    if frame.empty: raise ValueError('Latest recommendation day has no comparable candidates')
    if latest<pd.Timestamp(model['activation_not_before']): raise ValueError('Forward shadow cannot start before activation date')
    if latest<=pd.Timestamp(model['training_latest_outcome']): raise ValueError('Training outcome overlaps forward prediction date')
    frame['ShadowBaseRate']=model.get('training_base_rate');frame['ShadowProbability']=predict(frame,model['coefficients']);frame['ShadowPolicyVersion']=VERSION
    frame['ShadowTarget']=model['target'];frame['ShadowMode']='FORWARD_SHADOW'
    frame=frame.sort_values(['ShadowProbability','RecommendationID'],ascending=[False,True])
    frame['ShadowRank']=np.arange(1,len(frame)+1)
    frame['Ticker']=frame.get('Ticker',frame.get('ticker'))
    frame['ContractSymbol']=frame.get('ContractSymbol',frame.get('contract_symbol'))
    frame['BaselineAllocationDecision']=frame.get('AllocationDecision',frame.get('allocation_decision'))
    frame['BaselineRecommendedContracts']=frame.get('contracts')
    columns=['RecommendationID','RecommendationDate','Ticker','ContractSymbol','BaselineAllocationDecision','BaselineRecommendedContracts','Direction','ResearchScore','ShadowProbability','ShadowBaseRate','ShadowRank','ShadowPolicyVersion','ShadowTarget','ShadowMode']
    return frame[columns]


def review_forward(predictions, hindsight, as_of):
    """Score saved forecasts only when their target labels have matured."""
    p=predictions[predictions.ShadowPolicyVersion.eq(VERSION)].copy()
    if p.groupby('RecommendationID').ShadowProbability.nunique().gt(1).any():
        raise ValueError('Conflicting frozen forecasts for a recommendation')
    p=p.drop_duplicates('RecommendationID',keep='first')
    labels=hindsight[['RecommendationID','Horizon7DEvaluationDate','Horizon7DDirectionalReturnPct']].drop_duplicates('RecommendationID',keep='last')
    f=p.merge(labels,on='RecommendationID',how='left',validate='one_to_one')
    mature=pd.to_datetime(f.Horizon7DEvaluationDate,errors='coerce',format='mixed').le(pd.Timestamp(as_of))
    f['_Return']=pd.to_numeric(f.Horizon7DDirectionalReturnPct,errors='coerce')
    mature &= f._Return.notna()
    f['_Date']=pd.to_datetime(f.RecommendationDate,errors='coerce',format='mixed').dt.normalize()
    evaluated=f[mature].copy()
    return {'version':VERSION,'as_of':str(as_of),'saved_unique_predictions':len(f),'matured':len(evaluated),
            'censored_or_missing':int((~mature).sum()),'automatic_promotion':False,
            'metrics':{c:metrics(evaluated,c) for c in ['ShadowProbability','ShadowBaseRate']} if len(evaluated) else {}}


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build');b.add_argument('--source',type=Path,required=True);b.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('shadow');s.add_argument('--journal',type=Path,required=True);s.add_argument('--model',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    r=sub.add_parser('review');r.add_argument('--predictions-dir',type=Path,required=True);r.add_argument('--source',type=Path,required=True);r.add_argument('--as-of',required=True);r.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.command=='build': print(json.dumps(build(a.source,a.output),indent=2))
    elif a.command=='review':
        files=sorted(a.predictions_dir.glob('predictions_*.csv'))
        if not files: raise FileNotFoundError('No saved forward forecasts')
        result=review_forward(pd.concat([pd.read_csv(f) for f in files],ignore_index=True),pd.read_csv(a.source,low_memory=False),a.as_of)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open('x',encoding='utf-8') as handle: json.dump(result,handle,indent=2)
        print(json.dumps(result,indent=2))
    else:
        result=shadow(pd.read_csv(a.journal,low_memory=False),json.loads(a.model.read_text(encoding='utf-8')))
        a.output.parent.mkdir(parents=True,exist_ok=True)
        if a.output.exists(): raise FileExistsError('Preserve existing shadow predictions; choose a new output path')
        result.to_csv(a.output,index=False);print(f'Saved {len(result)} shadow predictions')
