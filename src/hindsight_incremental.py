"""Reuse completed hindsight outcomes without altering historical artifacts."""
import hashlib
import json
import math
from pathlib import Path
import pandas as pd

VERSION = 'COMPLETED-HORIZONS-v1'
HORIZONS = (3,5,7,14,30)


def finite(value):
    try: return math.isfinite(float(value))
    except (TypeError,ValueError): return False


def fingerprint(row):
    # All journal fields: changes to inputs invalidate reuse for that ID.
    values = {str(k):None if pd.isna(v) else str(v) for k,v in row.items()}
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


def reusable_horizon(row, days):
    prefix=f'Horizon{days}D'
    return (row.get(prefix+'Status')=='COMPLETE'
            and pd.notna(row.get(prefix+'EvaluationDate'))
            and finite(row.get(prefix+'DirectionalReturnPct'))
            and finite(row.get(prefix+'SPYReturnPct')))


def frozen(row):
    if not row: return False
    if row.get('EvaluationStatus')=='NO_DIRECTION': return True
    return (row.get('EvaluationStatus')=='COMPLETE'
            and finite(row.get('FinalDirectionalReturnPct'))
            and finite(row.get('FinalSPYReturnPct'))
            and all(reusable_horizon(row,d) for d in HORIZONS))


def load_previous(directory):
    candidates=sorted(Path(directory).glob('research_hindsight_*.csv'),key=lambda p:p.stat().st_mtime,reverse=True)
    if not candidates: return {},None
    source=candidates[0]
    frame=pd.read_csv(source,low_memory=False)
    if 'RecommendationID' not in frame or frame['RecommendationID'].duplicated().any():
        raise ValueError('Previous hindsight must have unique recommendation IDs')
    if 'HindsightCacheVersion' in frame:
        manifest=json.loads(source.with_suffix('.manifest.json').read_text(encoding='utf-8'))
        if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['output_sha256']:
            raise ValueError('Previous hindsight checksum mismatch; preserve source and review or explicitly rebuild')
    return {str(r['RecommendationID']):r for r in frame.to_dict('records')},source


def prior_for(row, prior):
    old=prior.get(str(row['RecommendationID']))
    if not old: return None
    version=old.get('HindsightCacheVersion')
    if pd.notna(version):
        if version!=VERSION or old.get('HindsightInputFingerprint')!=fingerprint(row): return None
    else:
        # One-time import from an existing immutable output. No fabricated
        # old input hash: identity checks and provenance remain explicit.
        ticker=str(row.get('ticker','')).strip()
        a=pd.to_datetime(row.get('RecommendationDate'),utc=True,errors='coerce')
        b=pd.to_datetime(old.get('RecommendationDate'),utc=True,errors='coerce')
        if ticker!=str(old.get('Ticker','')).strip() or pd.isna(a) or a!=b: return None
        for source,target in (('option_strategy','OptionStrategy'),('action','Action'),('opportunity_type','OpportunityType')):
            left,right=row.get(source),old.get(target)
            if pd.notna(left) and pd.notna(right) and str(left)!=str(right): return None
        if finite(row.get('EntryUnderlyingPrice')) and finite(old.get('EntryUnderlyingPrice')):
            if not math.isclose(float(row['EntryUnderlyingPrice']),float(old['EntryUnderlyingPrice']),rel_tol=1e-10): return None
    return old


def preserve_completed(result, old):
    """Keep finished fields even if a fresh provider call is missing or revised."""
    if not old: return result
    for d in HORIZONS:
        prefix=f'Horizon{d}D'
        if reusable_horizon(old,d):
            result.update({k:v for k,v in old.items() if k.startswith(prefix)})
    if old.get('EvaluationStatus')=='COMPLETE' and finite(old.get('FinalDirectionalReturnPct')) and finite(old.get('FinalSPYReturnPct')):
        result.update({k:v for k,v in old.items() if k.startswith('Final')})
        result['EvaluationStatus']='COMPLETE'
    return result
