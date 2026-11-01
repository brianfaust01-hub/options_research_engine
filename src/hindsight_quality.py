"""Explicit reviewed price-basis exclusions; immutable source rows remain untouched."""
from __future__ import annotations
import pandas as pd

RULE_VERSION = 'PRICE-BASIS-REVIEW-2026-10-29-v1'


def reviewed_quality_view(frame):
    if not {'Ticker','RecommendationDate'}.issubset(frame):
        raise ValueError('Ticker and RecommendationDate required for reviewed price-basis gate')
    dates=pd.to_datetime(frame.RecommendationDate,errors='coerce',format='mixed')
    ticker=frame.Ticker.astype(str).str.upper()
    excluded=ticker.eq('CTVA') & dates.lt(pd.Timestamp('2026-10-01'))
    audit=frame.loc[excluded,[c for c in ['RecommendationID','Ticker','RecommendationDate'] if c in frame]].copy()
    audit['ExclusionRule']=RULE_VERSION
    audit['Reason']='Unresolved mixed historical entry / adjusted price basis around corporate action; both directions excluded'
    return frame.loc[~excluded].copy(),audit
