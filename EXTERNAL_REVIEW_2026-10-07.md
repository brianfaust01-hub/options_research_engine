# External Architecture Review — October 7, 2026

## Status and governance

This document preserves external feedback for the six-week Project Stonks
review. It is a hypothesis register, not an instruction set, approved policy,
or finding. Nothing in this review changes production research, contract
selection, allocation, execution guidance, exits, the current policy era, or
the twelve-week readiness clock.

Any proposed change must be evaluated against immutable current-policy
evidence, data-quality coverage, sample sufficiency, nearby-threshold
sensitivity, and a prospective challenger period. No configuration should be
selected merely because it would have improved the first six weeks.

## External feedback received

The reviewer identified four principal concerns:

1. Long-premium options can lose despite a correct directional equity thesis
   because theta, implied-volatility contraction, and execution friction can
   offset delta gains. The reviewer proposed an IV Rank/Percentile entry filter.
2. One-minute option snapshots and paper fills may overstate executable
   liquidity, particularly during fast moves or wide/stale markets. The
   reviewer proposed a fixed slippage adjustment around the mid price.
3. Integer contracts and a $15,000 paper-capital base may cause expensive
   contracts to consume large portfolio weights or be rejected, potentially
   affecting which recommendations receive allocation. The reviewer proposed a
   larger test NAV or a lower-priced equity universe.
4. A broad SPY regime adjustment may suppress stock-specific opportunities.
   The reviewer proposed sector-relative-strength context.

The reviewer also suggested that risk-defined spreads, matched thesis/contract
horizons, tick-level data, and API-based execution are common alternatives to
the present long-premium, longer-DTE, polled-quote, manual-broker workflow.

## Project Stonks disposition

### H1 — Directionally correct but financially losing option trades

**Disposition: genuine and already measurable in part.**

Project Stonks intentionally distinguishes the underlying thesis from the
option expression. It captures option returns separately from underlying
direction, plus broker Greeks, exact-contract IV, theta drag, vega per premium,
execution quality, DTE, and intraday bid/ask paths. This makes the proposed
failure mode testable rather than hidden.

The material gap is historical IV context. Conventional IV Rank and IV
Percentile are explicitly recorded as `UNAVAILABLE_NO_HISTORY`; exact-contract
IV must not be mislabeled as underlying constant-maturity IV rank. A reviewed
constant-maturity/moneyness benchmark and roll policy are prerequisites before
an IVR/IVP challenger can be evaluated.

The claim that 45+ DTE necessarily creates an inferior horizon mismatch is too
strong. Longer DTE can reduce daily theta and preserve optionality while adding
vega exposure and premium cost. The appropriate question is empirical: which
DTE, theta, delta, vega, IV, and holding-period combinations improve net option
returns and tail risk after execution friction?

### H2 — Execution optimism from mid-price snapshots

**Disposition: important risk, but the review misread current naming.**

`ResearchPrice` uses the mid for analytical comparison. Production execution
guidance uses the displayed **ask for entry** and **bid for exit**, and records
entry execution cost, immediate-liquidation loss, spread dollars/percent,
volume, open interest, and broker-confirmed fills. A proposed entry at
mid + 10% of spread and exit at mid - 10% of spread would ordinarily be less
conservative than the existing ask/bid convention, which is approximately
mid +/- 50% of spread for a symmetric market.

The residual concern remains valid: displayed quotes can be stale or
non-executable, paperMoney may not reproduce queue priority or live slippage,
and one-minute polling cannot establish every intervening market state.
Intraday evidence must remain quote-age filtered, gap-aware, bid-liquidation
based, and explicitly labeled not broker fills. Live execution calibration is
still required before real-money automation.

### H3 — Integer sizing and the $15,000 capital base

**Disposition: genuine constraint, not evidence that arbitration is broken.**

Integer contracts create real indivisibility for the intended initial capital
base. The allocator already records contract cost, rejection/pass reasons,
unallocated high-ranking opportunities, capital utilization, intentional cash,
position limits, expected stop loss, and concentration context. Those records
allow the six-week review to distinguish signal quality from affordability.

Increasing NAV to $100,000 would remove a real operating constraint and change
the intended deployment problem. Restricting the universe by share price is
also an imperfect proxy because option premium depends on volatility,
moneyness, DTE, and contract liquidity. Appropriate counterfactuals include
fractional/notional shadow allocation, alternative NAVs, contract-budget bands,
and performance of unaffordable qualifying candidates, while leaving the
observed $15,000 baseline unchanged.

### H4 — Broad regime and missing relative-strength dimensions

**Disposition: high-priority six-week hypothesis.**

Recent evidence confirms that put candidates continue to be generated but can
lose allocation rank after a broad bullish/risk-on directional multiplier.
Weak breadth can coexist with strong index trend and stock-specific bearish
opportunities. The six-week review should compare the frozen baseline with
shadow rankings that remove, shrink, or decompose the categorical multiplier.

Sector-relative and ticker-relative strength are logical candidate features,
but incomplete sector classification and correlated feature proliferation are
risks. Any challenger should prefer a small, interpretable set of continuous
components and prove incremental value beyond existing trend, breadth,
momentum, and ticker-level direction.

### Strategy-vehicle expansion

**Disposition: future research, not an immediate baseline repair.**

Vertical spreads or delta hedging may reduce premium/vega exposure, but they
introduce additional legs, execution assumptions, assignment mechanics, and a
different payoff structure. Long premium remains a coherent initial mandate.
Strategy expansion requires its own captured evidence and prospective policy
era; it should not be introduced simply to improve the current sample.

## Six-week analyses prompted by this review

The checkpoint should add the following analyses without automatically changing
production policy:

1. Decompose underlying directional success from exact option financial return.
2. Cut option returns by DTE, holding period, delta, theta drag, vega per
   premium, exact-contract IV, spread, execution grade, and quote quality.
3. Report whether IV Rank/Percentile is unavailable, partially available, or
   supported by an approved benchmark; do not silently substitute raw IV.
4. Compare broker fills with contemporaneous ask/bid guidance and sampled quote
   paths where timestamps overlap; quantify slippage without imposing an
   arbitrary constant.
5. Run shadow allocation at the observed $15,000 NAV and alternative notional
   NAVs; separate affordability rejection from signal/quality rejection.
6. Compare allocated results with qualifying unallocated expensive contracts,
   using deduplicated thesis episodes and acknowledging selection dependence.
7. Evaluate the regime multiplier as a whole and its trend, breadth, volatility,
   risk-mode, ticker-relative, and sector-relative components separately.
8. Test stability by week and market condition, with and without extreme
   outcomes, rather than selecting the best aggregate cut.
9. Limit promotion to simple challengers supported across multiple cohorts;
   freeze accepted challengers before prospective validation.

## Questions preserved for the checkpoint

- Does long-premium option return diverge systematically from underlying thesis
  correctness, and which measured sensitivities explain the divergence?
- Are high-IV contracts actually worse after controlling for direction,
  liquidity, DTE, and execution, or is raw IV only proxying for opportunity and
  risk?
- How much do broker fills differ from ask-entry/bid-exit guidance and from
  sampled quotes at comparable timestamps?
- How many high-quality opportunities are rejected only because one contract
  cannot fit the $15,000 portfolio constraints, and how do they mature?
- Does the directional regime multiplier improve expected return, profit factor,
  and tail risk out of sample, or merely suppress valid idiosyncratic trades?
- Does sector-relative strength add information beyond existing ticker trend,
  momentum, breadth, and market context?
