"""Recover original exit plans by exact recommendation ID; never rewrite history."""
from __future__ import annotations
import csv
from datetime import datetime
import math
from pathlib import Path
from zoneinfo import ZoneInfo

PLAN_FIELDS={'ProfitTarget':'profit_target_price','StopLoss':'stop_loss_price','TimeStopDTE':'time_stop_dte'}
PLAN_COLUMNS=tuple(PLAN_FIELDS)+('ExitPlanRecommendationID','ExitPlanStatus')


def number(value):
    try:
        n=float(value)
        return n if math.isfinite(n) and n>0 else None
    except (TypeError,ValueError):return None


def identity(row,position=False):
    return (str(row.get('Ticker') or row.get('ticker') or '').upper(),
        str(row.get('Expiration') if position else row.get('expiration'))[:10],
        number(row.get('Strike') if position else row.get('strike')),
        row.get('OptionStrategy') if position else row.get('option_strategy'))


def time(value):
    d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    return d.replace(tzinfo=ZoneInfo('America/New_York')) if d.tzinfo is None else d


def restore_original_plans(portfolio,journal_path=None,*,journal_rows=None):
    result=portfolio.copy(deep=True)
    for col in PLAN_COLUMNS:
        if col not in result:result[col]=None
    for col in ('ExitPlanRecommendationID','ExitPlanStatus'):result[col]=result[col].astype('object')
    opened=result[result['Status'].astype(str).str.upper().eq('OPEN')]
    ids={str(v) for v in opened.get('RecommendationID',[]) if str(v) not in ('','None','nan','<NA>')}
    plans={};conflicts=set()
    def project(rows):
        for raw in rows:
            rid=str(raw.get('RecommendationID',''))
            if rid not in ids:continue
            row={k:raw.get(k) for k in ('RecommendationDate','Ticker','ticker','expiration','strike','option_strategy',*PLAN_FIELDS.values())}
            if rid in plans and plans[rid]!=row:conflicts.add(rid)
            plans.setdefault(rid,row)
    if ids:
        if journal_rows is not None:project(journal_rows)
        elif journal_path is not None and Path(journal_path).exists():
            csv.field_size_limit(20_000_000)
            with Path(journal_path).open(encoding='utf-8-sig',newline='') as handle:project(csv.DictReader(handle))
    for i,p in opened.iterrows():
        rid=str(p.get('RecommendationID',''));plan=plans.get(rid)
        status='ORIGIN_NOT_FOUND' if rid in ids else 'MISSING_ORIGIN_ID'
        if rid in conflicts:status='CONFLICTING_ORIGIN_ID'
        elif plan:
            if identity(p,True)!=identity(plan):status='ORIGIN_CONTRACT_MISMATCH'
            else:
                try:valid=time(plan['RecommendationDate'])<=time(p['EntryDate'])
                except (ValueError,TypeError,KeyError):valid=False
                if not valid:status='ORIGIN_TIME_UNVERIFIED'
                else:
                    for dest,source in PLAN_FIELDS.items():
                        value=number(plan.get(source))
                        if number(p.get(dest)) is None and value is not None:
                            if dest!='TimeStopDTE' or value==int(value):result.at[i,dest]=value
                    complete=all(number(result.at[i,k]) is not None for k in PLAN_FIELDS)
                    status='RESOLVED_EXACT_ID' if complete else 'PARTIAL_ORIGINAL_PLAN'
                    result.at[i,'ExitPlanRecommendationID']=rid
        result.at[i,'ExitPlanStatus']=status
    return result
