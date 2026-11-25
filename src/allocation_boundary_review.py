"""Offline boundary study: recorded viability, exact broker dollars and quote diagnostics."""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import argparse
import pandas as pd
import portfolio_arbitrator as arb
from adaptive_allocation_research import project_journal,journal_key,number,flag,at,sanitize
from exit_path_review import symbol,valid_point,schedule

FIELDS={'ticker','action','contracts','execution_entry_price','premium','portfolio_score','execution_score',
    'stop_loss_price','stop_loss_pct','earnings_allocation_override','earnings_status','option_strategy',
    'expiration','strike','RecommendationID','OpeningHourBlocked','OilRiskBlocked','OpeningHourStatus',
    'portfolio_action','portfolio_action_reason','portfolio_correlation_penalty','portfolio_account_nav',
    'institutional_trade_score','risk_mode','market_regime'}


def viability(row,positions,nav):
    if flag(row.get('OpeningHourBlocked')):return None,'OPENING_HOUR_BLOCK'
    if flag(row.get('OilRiskBlocked')):return None,'OIL_EXPOSURE_BLOCK'
    held=[p for p in positions if p.get('ticker')==row.get('ticker')]
    value=sum((number(p.get('current_price')) or number(p.get('entry_price')) or 0)*100*(number(p.get('contracts')) or 0) for p in held)
    qty=sum(number(p.get('contracts')) or 0 for p in held)
    asset=arb._candidate_asset(0,pd.Series(row),nav,value,qty)
    other=[s for s in asset['base_reasons'] if not s.startswith('forward score')]
    return (asset,None) if not other else (None,'; '.join(other))


def score(row,new_penalty=2):
    base=number(row.get('portfolio_score'))
    if base is None:return None
    return base-new_penalty-(number(row.get('portfolio_correlation_penalty')) or 0)


def quote_diagnostic(entry,exit):
    if entry is None or exit is None:return None
    em=(entry[2]+entry[3])/2;xm=(exit[2]+exit[3])/2
    return dict(entry_mid=em,exit_mid=xm,midpoint_price_change_per_contract=(xm-em)*100,
        midpoint_return=xm/em-1,bidask_friction_sensitivity_per_contract=(exit[2]-entry[3])*100,
        entry_quote_at=entry[1],entry_received_at=entry[0],exit_quote_at=exit[1],exit_received_at=exit[0],
        basis='Gross observed fixed-horizon quote changes, not fills, stop/limit results or portfolio profit')


def read_windows(root,cases,calendar,as_of):
    windows=defaultdict(list)
    for r in cases:
        if not r.get('decision_at'):continue
        start=at(r['decision_at']).timestamp()
        date=at(r['decision_at']).date().isoformat()
        if date not in calendar:continue
        windows[date].append((start,start+900,r['contract']))
        dates=list(calendar)
        for h in (1,3):
            index=dates.index(date)+h
            if index>=len(dates):continue
            enddate=dates[index];end=calendar[enddate][1]
            r['endpoint_'+str(h)]=dict(date=enddate,end=end,mature=end<=as_of)
            if end<=as_of:windows[enddate].append((end-300,end,r['contract']))
    paths=defaultdict(dict);manifest=[];corrupt=[]
    for day,ranges in sorted(windows.items()):
        wanted={r[2] for r in ranges}
        for path in sorted((Path(root)/day).glob('sample_*.gz')):
            try:
                clock=path.name.split('_')[1]
                rough=datetime.fromisoformat(day+'T'+clock[:2]+':'+clock[2:4]+':'+clock[4:6]+'+00:00').timestamp()
            except (ValueError,IndexError):rough=None
            if rough is not None and not any(a-60<=rough<=b+60 for a,b,_ in ranges):continue
            raw=path.read_bytes();manifest.append(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest()))
            try:
                bundle=json.loads(gzip.decompress(raw))
                for obs in bundle['observations']:
                    key=''.join(obs.get('contract_symbol','').split())
                    if key not in wanted:continue
                    p=valid_point(obs)
                    if p and any(k==key and a<=p[1]<=p[0]<=b for a,b,k in ranges):
                        old=paths[key].get(p[1])
                        if old is None or p[0]<old[0]:paths[key][p[1]]=p
            except (ValueError,OSError,EOFError,KeyError,TypeError):corrupt.append(str(path))
        print('Boundary quote windows:',day,flush=True)
    for r in cases:
        if not r.get('decision_at'):continue
        start=at(r['decision_at']).timestamp()
        ps=list(paths[r['contract']].values())
        entries=[p for p in ps if start<=p[1]<=p[0]<=start+900]
        entry=min(entries,key=lambda p:p[1]) if entries else None
        r['entry_snapshot_available']=entry is not None
        r['quote_diagnostics']={}
        for h in (1,3):
            endpoint=r.get('endpoint_'+str(h))
            if not endpoint or not endpoint['mature']:continue
            end=endpoint['end'];exits=[p for p in ps if end-300<=p[1]<=p[0]<=end]
            exit=max(exits,key=lambda p:p[1]) if exits else None
            r['quote_diagnostics'][str(h)]=quote_diagnostic(entry,exit)
    return manifest,corrupt


def summary(rows,window):
    subset=[r for r in rows if abs(r['effective_score']-70)<=window]
    result={}
    for side in ('below','at_or_above'):
        selected=[r for r in subset if r['side']==side]
        stock={}
        for h in (3,5,7):
            # Earliest available observation per stock-thesis episode in this
            # boundary side. No outcomes used to select the representative.
            seen=set();values=[];pending=missing=0
            for r in selected:
                outcome=r.get('stock_outcome')
                if not outcome:missing+=1;continue
                if outcome['episode'] in seen:continue
                seen.add(outcome['episode'])
                value=outcome.get(str(h))
                if value is None:pending+=1
                else:values.append(value)
            stock[str(h)]=dict(mature_episodes=len(values),pending=pending,unmatched_rows=missing,
                positive=sum(v>0 for v in values),negative=sum(v<0 for v in values),
                mean_directional_return=sum(values)/len(values) if values else None)
        options={}
        for h in (1,3):
            qs=[r['quote_diagnostics'].get(str(h)) for r in selected if r.get('quote_diagnostics',{}).get(str(h))]
            mature=sum(bool(r.get('endpoint_'+str(h),{}).get('mature')) for r in selected)
            pending=sum(bool(r.get('endpoint_'+str(h))) and not r['endpoint_'+str(h)]['mature'] for r in selected)
            options[str(h)]=dict(covered_observations=len(qs),total_observations=len(selected),
                mature_endpoints=mature,pending_endpoints=pending,unresolved_timing=len(selected)-mature-pending,
                mature_missing_price_pair=mature-len(qs),
                positive=sum(q['midpoint_price_change_per_contract']>0 for q in qs),
                midpoint_change_one_contract_each=sum(q['midpoint_price_change_per_contract'] for q in qs) if qs else None,
                bidask_friction_sensitivity_one_contract_each=sum(q['bidask_friction_sensitivity_per_contract'] for q in qs) if qs else None)
        actual=[r for r in selected if r.get('actual_closed_net') is not None]
        result[side]=dict(observations=len(selected),dates=len({r['date'] for r in selected}),
            actual_executed_closed_cases=len(actual),actual_executed_net=sum(r['actual_closed_net'] for r in actual) if actual else None,
            actual_winners=sum(r['actual_closed_net']>0 for r in actual),stock=stock,option_quote_diagnostics=options)
    return result


def run(root,penalty_path,attribution_path,hindsight_path,output,*,as_of):
    root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    penalties=json.loads(Path(penalty_path).read_text())
    days={r['date'] for r in penalties['days']}
    journal,index,conflicts=project_journal(root/'data/trade_journal.csv',days)
    from hindsight_analytics import build_thesis_episodes
    hs=pd.read_csv(hindsight_path,usecols=lambda x:x in ('RecommendationID','RecommendationDate','Ticker','Direction') or x.startswith(('Horizon3D','Horizon5D','Horizon7D')),low_memory=False)
    outcomes={r['RecommendationID']:r for r in build_thesis_episodes(hs).to_dict('records')}
    actual=json.loads(Path(attribution_path).read_text());units=defaultdict(list)
    for u in actual['units']:
        if u['side']==1 and u.get('recommendation_id') and u.get('entry_at'):units[u['recommendation_id']].append(u)
    cases=[];exclusions=Counter()
    for source in penalties['source_manifest']:
        path=Path(source['candidates']);day=path.name.split('_')[2]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('Candidate source changed')
        if hashlib.sha256(Path(source['positions']).read_bytes()).hexdigest()!=source['position_sha256']:raise ValueError('Position source changed')
        frame=pd.read_csv(path,usecols=lambda k:k in FIELDS,low_memory=False)
        positions=pd.read_csv(source['positions']).to_dict('records')
        for row in frame.to_dict('records'):
            effective=score(row)
            if effective is None or abs(effective-70)>10:continue
            asset,reason=viability(row,positions,number(row.get('portfolio_account_nav')) or 15000)
            if reason:exclusions[reason]+=1;continue
            rid=row.get('RecommendationID')
            if not isinstance(rid,str) or rid not in journal:
                matches=index.get(journal_key(day,row),set())-conflicts
                rid=next(iter(matches)) if len(matches)==1 else None
                join='UNIQUE_DATE_CONTRACT_FEATURE_INFERENCE' if rid else 'UNRESOLVED'
            else:join='EXACT_SOURCE_ID'
            plan=journal.get(rid,{})
            contract=symbol(dict(ticker=row['ticker'],expiration=row['expiration'],strike=row['strike'],
                option_type='PUT' if row['option_strategy']=='Long Put' else 'CALL'))
            case=dict(date=day,ticker=row['ticker'],option_strategy=row['option_strategy'],contract=contract,
                recommendation_id=rid,join_status=join,decision_at=plan.get('RecommendationDate'),
                portfolio_score=row['portfolio_score'],effective_score=effective,
                side='below' if effective<70 else 'at_or_above',risk_mode=row.get('risk_mode'),
                recorded_action=row.get('portfolio_action'),recorded_reason=row.get('portfolio_action_reason'),
                feasible_incremental_contracts=asset['contracts'],actual_closed_net=None)
            known=units.get(rid,[])
            if known and all(u['status']=='CLOSED' for u in known):case['actual_closed_net']=sum(u['net_period_contribution'] for u in known)
            h=outcomes.get(rid)
            if h:
                case['stock_outcome']={'episode':h['ThesisEpisodeID'],**{str(n):number(h.get(f'Horizon{n}DDirectionalReturnPct')) if h.get(f'Horizon{n}DStatus')=='COMPLETE' else None for n in (3,5,7)}}
            cases.append(case)
    sessions=schedule('2026-09-25','2026-12-10')
    calendar={day:(op,cl) for day,op,cl in sessions}
    manifest,corrupt=read_windows(root/'data/processed/intraday_option_paths',cases,calendar,as_of.timestamp())
    matched={}
    for r in cases:
        if abs(r['effective_score']-70)<=5:matched.setdefault((r['date'],r['option_strategy']),set()).add(r['side'])
    paired={k for k,sides in matched.items() if len(sides)==2}
    paired_cases=[r for r in cases if (r['date'],r['option_strategy']) in paired]
    result=dict(as_of=as_of.isoformat(),boundary=70,new_entry_penalty=2,windows=(2,5,10),
        input_dates=43,otherwise_recorded_viable_cases=len(cases),excluded_near_boundary=dict(exclusions),
        by_window={str(w):summary(cases,w) for w in (2,5,10)},
        same_date_direction_pairs=len(paired),matched_window5=summary(paired_cases,5),cases=cases,
        quote_source_manifest=manifest,corrupt_quote_bundles=corrupt,
        source_paths=dict(penalties=str(penalty_path),attribution=str(attribution_path),hindsight=str(hindsight_path)),
        limitations=['Windows are predeclared sensitivities, not a selected optimum. Initial score gate and final admission hurdle are both represented by recorded effective score.',
          'Otherwise recorded viable means passing the recorded non-score initial checks; it does not override later capital, concentration or quantity constraints.',
          'No random assignment. Only four recent Defensive dates; matched-date/direction groups and repeated episodes remain dependent.',
          'Actual net belongs only to broker-executed closed cases; rejected cases never acquire invented broker profit.',
          'Stock horizons reuse finalized November 19 outcomes. Exact option snapshots use valid observed positive bid/ask, no interpolation, entry within fifteen minutes and endpoint in the final five session minutes.',
          'Quote changes are fixed-horizon gross price diagnostics. Bid/ask friction is a separate sensitivity, not a live-fill estimate. No STD stops, targets, slippage, cash recycling or hypothetical trade return is reconstructed.',
          'Option paths are scanned only in predeclared endpoint windows; missing or corrupt files remain explicit. Future endpoints are not treated as zeros.'])
    with (output/'review.json').open('x',encoding='utf-8') as handle:json.dump(sanitize(result),handle,indent=2,allow_nan=False)
    print(json.dumps(sanitize({k:v for k,v in result.items() if k not in ('cases','quote_source_manifest','limitations')}),indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('root','penalties','attribution','hindsight','output'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();run(a.root,a.penalties,a.attribution,a.hindsight,a.output,as_of=datetime.now(timezone.utc))
