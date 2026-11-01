"""Research-only configuration profiles, evaluated with the existing allocator.

Never writes the production journal or portfolio and never places orders.
Profile thresholds are test hypotheses, not calibrated probabilities or optima.
"""
from __future__ import annotations
import pandas as pd
from portfolio_arbitrator import arbitrate_portfolio

POLICY_VERSION='CONFIG-PROFILES-2026-10-29-v1'
POLICIES={'baseline','quality_decay','moderate_delta_iv','quality_or_contract'}


def _column(frame,*names):
    value=pd.Series(float('nan'),index=frame.index,dtype=float)
    for name in names:
        if name in frame:value=value.fillna(pd.to_numeric(frame[name],errors='coerce'))
    return value


def profile_flags(frame):
    score=_column(frame,'ResearchScore','research_score')
    theta=_column(frame,'theta_drag_pct_per_day','ThetaDragPctPerDay')
    delta=_column(frame,'broker_delta','BrokerDelta').abs()
    iv=_column(frame,'implied_volatility','ImpliedVolatility')
    quality=score.between(90,100)&theta.ge(0)&theta.lt(.01)
    contract=delta.gt(.35)&delta.le(.5)&iv.gt(.20)&iv.le(.40)
    return pd.DataFrame({'QualityDecayProfile':quality,'ModerateDeltaIVProfile':contract,
                         'QualityOrContractProfile':quality|contract},index=frame.index)


def allocate_profile(candidates,positions,*,policy,account_nav,market_context=None,market_breadth=None):
    if policy not in POLICIES:raise ValueError('Unknown configuration-profile policy')
    shadow=candidates.copy(deep=True);flags=profile_flags(shadow)
    for name in flags:shadow[name]=flags[name]
    masks={'baseline':pd.Series(True,index=shadow.index),'quality_decay':flags.QualityDecayProfile,
           'moderate_delta_iv':flags.ModerateDeltaIVProfile,'quality_or_contract':flags.QualityOrContractProfile}
    shadow['ShadowProfileEligible']=masks[policy];shadow['ShadowProfilePolicy']=policy
    shadow['ShadowProfileVersion']=POLICY_VERSION
    if policy!='baseline':
        excluded=~masks[policy]
        shadow.loc[excluded,'action']='Watch'
        shadow.loc[excluded,'ShadowExclusionReason']='Outside frozen test profile; retained as evidence'
    # All original liquidity, execution, contract, position, exposure, full-premium,
    # dynamic-utilization and risk rules remain owned by the existing allocator.
    return arbitrate_portfolio(shadow,positions.copy(deep=True),account_nav,
                               market_context=market_context,market_breadth=market_breadth,paper_trading=True)
