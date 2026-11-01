**Later implementation update:** The option-return comparison is now implemented and tested; see SHADOW_OPTION_COMPARISON.md. The checkpoint evidence and earlier readiness assessments below are retained as a dated record. Activation remains off until Sunday.

# Configuration combinations — clarified checkpoint scope

Prepared October 29, 2026, after Brian clarified that the six-week review should identify specific configuration combinations to test. **The probability diagnostic is not the proposed trading challenger. The previous forecast-only package is not ready as a return-comparison release.** Nothing is activated.

## Actual candidate combinations

Use post-September-24 matured episodes and retain execution score >=70 for this analysis. This execution condition alone is not the full portfolio eligibility test.

| Combination | Episodes / dates | Directional win rate | Mean 7-session stock-direction return | Early / later mean |
|---|---:|---:|---:|---:|
| All execution-qualified candidates | 83 / 18 | 56.6% | +0.59% | — |
| Research Score 90–99 AND theta drag <1% per day | 20 / 11 | 70.0% | +2.20% | -0.08% (3) / +2.60% (17) |
| Absolute delta >0.35 and <=0.50 AND IV >20% and <=40% | 28 / 16 | 71.4% | +1.68% | +1.71% (12) / +1.66% (16) |
| Either profile | 37 / 17 | 70.3% | +2.03% | +1.66% (13) / +2.23% (24) |
| Both profiles | 11 / 7 | 72.7% | +1.46% | -0.64% (2) / +1.93% (9) |

Early ends October 6; later starts October 7. These are discovery diagnostics on inspected history, not an untouched holdout. Date/direction-matched comparisons and a descriptive date bootstrap are saved in combination_evidence.json. All three-field/two-field exploration involved many comparisons; a positive bootstrap interval is not selection-adjusted proof.

The moderate-delta/IV profile is more consistent across the halves than high-score/low-decay. A separate train-only pair-profile mining exercise produced only five later matched observations. That search is too thin to claim a validated algorithm.

## Turning a good-looking group into a trading rule is a separate test

A retrospective same-date top-three ranking audit replaced legacy ordering with profile preference, holding selection counts equal. It changed nine slots across 48 selections and **reduced** average underlying return from +0.71% to +0.47%. A better-looking broad subgroup does not automatically improve an already selective allocator. Therefore do not deploy an arbitrary profile bonus or label that ranking experiment successful.

## Exact-option replay

The archive was re-extracted for all 83 execution-qualified episode contracts, including symbols missing from the earlier broker/allocated-only quote database. Of 83 opportunities, 48 have coverage-qualified completed sampled execution proxies; 21 are partial and 14 have unknown entry coverage. Missing opportunities are not zero returns.

The replay buys at the first observed ask at or below the recorded entry limit within five minutes of recommendation, uses recorded initial stop/target prices, and exits at the first observed stop bid, capped target, or the seven-session endpoint. Stop overshoots remain. It assumes $0.70 per contract per side, with entry/exit penny-slippage sensitivities. It does not model guaranteed fills, daily profit ratchets, incumbent recycling, actual broker execution or a capital-constrained portfolio.

| Profile | Qualified option proxies | One-contract net P/L total | Net dollar profit factor | Mean per-trade percentage return |
|---|---:|---:|---:|---:|
| All execution-qualified | 48 | -$3,217.20 | 0.34 | -13.68% |
| High-score / low-decay | 10 | -$677.00 | — | -14.46% |
| Moderate delta / IV | 14 | +$134.40 | 1.14 | -7.09% |
| Either | 19 | -$432.60 | — | -10.06% |

The positive dollar total for moderate delta/IV is not inconsistent with its negative average percentage return: entry premiums differ, so one contract does not mean equal dollars invested. Its summed entry debits were $7,743.80; $134.40 divided by those debits is +1.74%, a cohort cash ratio, not a portfolio or time-weighted return. Removing the largest winner ($464.60) turns the net total negative. No profitability claim is justified from these 14 observations. Nevertheless, this is a concrete, interpretable hypothesis supported by more than an underlying-only screen.

The high-score/low-decay hypothesis is not the first proposed trading experiment because its option results do not improve on the broader proxy cohort. The OR combination adds that weaker branch. No whole broker trades or excessive-quantity losses have been silently erased: these are quantity-neutral recommendation-contract simulations; actual-account attribution remains separate.

## Recommended first configuration experiment

**Moderate-delta / moderate-IV candidate eligibility, followed by the existing allocator.**

1. Control: current candidate qualification, ranking and allocator.
2. Challenger: a copy of that same daily candidate set, additionally requiring recorded absolute delta >0.35 and <=0.50 and IV >0.20 and <=0.40.
3. Both: same contract candidates, original research/portfolio scores, execution/liquidity/earnings gates, sizing formula, sector/theme constraints, capital and stop-risk limits, entry limits and exit rules. No probability model controls selection or risk.
4. Nonmatching challenger candidates stay preserved as evidence and receive no new allocation. Cash can increase; the same sizing algorithm can produce different total exposure because eligibility differs. This is an intended consequence to measure, not a reason to force equal deployment.
5. Compare full NAV/cash/open and closed P/L, drawdown, turnover, costs, exposure and return on deployed capital. Prefer risk-adjusted improvement rather than win rate alone.

These numerical bands are a **frozen research hypothesis**, not permanent optimal settings or a replacement for the requested dynamic architecture. Dynamic exits and continuous feature responses remain in scope; changing them simultaneously would obscure whether this specific configuration combination helps.

configuration_profile_shadow.py implements these isolated research allocations using the existing allocation engine. It changes copies only. It is not connected to the daily run and does not yet create a persistent trading portfolio.

## Concrete decision illustration

Using October 29's saved morning candidates, two freshly empty $15,000 portfolios and the existing allocator:

- Control selects MMM, GOOG, KO, EQT, MDT, MSFT, SLB, NOW, WMT and DIS: $8,022 planned premium.
- Moderate-delta/IV challenger selects GOOGL, GOOG, EQT, JNJ, JPM, MDT, PYPL, PM, SLB and WMT: $8,038 planned premium.
- For example, the challenger drops KO/MSFT/NOW/DIS/MMM and adds GOOGL/JNJ/JPM/PYPL/PM under this controlled starting state.

This is a retrospective decision illustration, not actual October 29 holdings, a recommendation to trade now, a guaranteed fill set or prospective evidence. The portfolios were deliberately initialized empty; the actual broker account has its own holdings and capital. Exact contracts, quantities and rules are saved in oct29_flat_capital_policy_illustration.csv.

## Readiness and remaining implementation

The **configuration hypothesis, historical evidence, isolated allocation adapter and illustrative decision differences are prepared**. The earlier assertion that the forecast-only package was the completed Sunday trading release was too broad.

Before activating a returns comparison, connect the selected policy to a persistent, independent control/challenger cash-and-position ledger; freeze actual decision availability times; consume the existing quote collector; handle fees, unfilled orders, gaps, marks, fills and idempotent restarts; then validate the full daily/minute workflow. A separate attribution view continues to track actual broker performance. No historical result is relabeled as forward evidence.

The old activation file remains disabled and now marks the release as requiring review. The activation helper refuses enabling it until the completed trading-comparison scope is explicitly marked ready. No commit, push, email or production scan was performed.

Validation: 148 repository tests pass, including three new profile/isolation checks. All 83 opportunities have explicit statuses; entry limits, coverage and fee arithmetic are asserted. Eight entry/exit observations across four contracts were independently verified against original gzip files and hashes. Sources remain unchanged.
