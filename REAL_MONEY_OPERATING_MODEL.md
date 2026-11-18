# Project Stonks — Real-Money Operating Model

**Status:** Design catalog only  
**Current authorization:** Paper trading only  
**Promotion authority:** Explicit human approval after readiness gates pass

## Purpose

This document catalogs how Project Stonks should operate if it is eventually
approved for real-money use. It is not approval to place trades, enable broker
trading permissions, or relax any current safeguard.

The real-money system should reuse the existing research, contract selection,
portfolio arbitration, risk, reporting, and hindsight components. Broker
execution must be a separate adapter and controlled workflow rather than logic
embedded in the research engine.

## Promotion Stages

### Stage 0 — Clean Paper Evidence

- Continue paper trading under an explicit policy-era ID
- Satisfy the documented duration, matured-episode, regime, predictive-quality,
  loss-control, execution, data-integrity, and operational-reliability gates
- Keep broker submissions entirely manual

### Stage 1 — Read-Only Broker Shadow

- Connect to real account data with no order-writing permission
- Reconcile NAV, cash, buying power, positions, working orders, fills, fees, and
  realized and unrealized P/L
- Generate proposed orders and compare them with actual human decisions
- Prove that repeated runs are idempotent and cannot duplicate instructions

### Stage 2 — Human-Approved Order Tickets

- Produce broker-ready entry, adjustment, and exit tickets
- Require the user to review and explicitly approve each ticket
- Re-read account and order state immediately before submission
- Block stale, conflicting, duplicate, oversized, or no-longer-valid tickets
- Record the proposed, approved, submitted, acknowledged, filled, canceled, and
  rejected states separately

### Stage 3 — Constrained Live Pilot

- Use a separately configured pilot capital limit below the full strategy NAV
- Permit only defined-risk, long-premium calls and puts
- Retain manual approval and an immediate kill switch
- Scale only after live fills, slippage, reliability, and realized risk reconcile
  with the paper and shadow evidence

### Stage 4 — Evidence-Gated Expansion

- Increase capital or reduce manual steps only through explicit review
- Change one bounded policy family at a time
- Preserve the prior policy, decision record, and matched shadow comparison
- Never allow learning analytics to promote production settings automatically

## Required Functional Capabilities

### Intraday Profit Protection and Overnight Hold Decisions

**Short-Term Rule Test (November 10 design).** Mirror the daily paper
portfolio using broker-confirmed entries, actual quantities, and carried
positions. Keep the original exit policy as the modeled control and actual
broker P/L as a separate reconciliation. A trigger at the working sell limit
duplicates the existing target signal. Compare actions at a distinct point
before the target: keep the original orders, raise the stop, or try to close.
Any fraction of the distance from fill to target is a candidate threshold.

For the historical feasibility check, match actual fills to exact-contract
quotes, check coverage before and after the proposed trigger, and inventory
order-history and quote-size gaps. Treat same-quote fills as a modeling
assumption, and test delayed execution and partial fills when data supports
them. For a forward mirror, record position and order state at the time of
each decision. Use the same entry tape in the paired comparison. Report any
capital freed separately unless a qualified replacement could actually use it.

The October 6 close to November 10 close feasibility check covered 140 new
long entry groups. It found exact-contract quotes for 139 and sufficient
coverage through the first actual reduction or statement cutoff for 49
(95% of market minutes, gaps no longer than five minutes, and endpoints
within two minutes). The halfway-to-recorded-target probe was observed in
27 groups before a sampled original stop or target touch. Six met the coverage
standard. None of 111,276 usable quote records checked for November 6–10
contained bid size. All 25 statement exports in the window include Account
Order History, which can help recover actual bracket prices. Verify order
changes and timing before treating that history as a working-order timeline.
This supports a limited historical screen. The audit ends at first reduction
and omits starting inventory. A full portfolio replay also needs those
positions, later quotes where an arm stays open, and execution assumptions.

Sensitivity across 25%, 35%, 50%, 65%, 75%, and 90% of fill-to-target distance
found 52, 42, 27, 17, 12, and 5 observed triggers. The respective counts were
33, 26, 16, 11, 10, and 4 with at least 90% market-minute coverage, gaps no
longer than 15 minutes, and endpoints within three minutes. With the 95% / five
minute / two minute standard, counts fell to 12, 9, 6, 3, 3, and 2. All strict
65% and higher observations came from one entry date. Use the full grid to
screen candidate rules and report paired net P/L on a common cohort, including
positions that never activate each rule. Coverage counts measure how well we
can observe a threshold. Profit, giveback, and execution cost determine its value.

The historical replay is implemented in `src/short_term_rule_test.py`. Run it
with the statement directory, journal, intraday archive, existing verified
quote projection, start and end statement names, and a new output path. An
earlier origin statement recovers entry lots for the starting holdings. The
November 10 run produced `reports/short_term_rule_test_20261110/paired_replay.md`
and `paired_replay.json`. It evaluated 140 eligible entry groups, including
nine carried groups, and recovered 117 initial brackets and 20 groups with
linked replacements. The main cohort contains 87 groups across 15 entry dates.
Actual net on that cohort was $3,232.28 and the simulated control was
-$2,957.89 at $0.01 slippage. The actual-exit overlay therefore provides a
second reference, replacing only rule-driven sales before the first actual
reduction. None of the tested rules improved the broad cohort against that
reference across the five execution settings. The strict subset spans two
dates and produces some positive comparisons. Use the results as historical
evidence and retain the control mismatch when interpreting threshold effects.

**Added November 2, 2026 at Brian's request. Status: backlog/design only.**
The example is an AMZN-style large same-day option gain with little planned
upside left before the target. Position management should evaluate whether
the remaining reward justifies current downside and overnight exposure,
without waiting for the next 10:30 research run. This is not approval to
change the current twelve-week experiment or enable broker orders.

**Before the twelve-week review — prepare evidence and the test design:**

- Preserve the frozen baseline and current shadows. Document where existing
  minute quotes, targets, stops, timestamps and actual fills can support
  analysis, and identify missing coverage without inventing overnight prices
  or between-sample threshold crossings.
- Define comparable outcomes: profit captured, profit given back, missed
  subsequent upside, overnight changes, net expectancy, drawdown, execution
  costs and time/capital released. Distinguish actual broker fills from
  quote-based counterfactuals.
- Specify candidate decision inputs: executable option bid, net gain versus
  actual entry, fraction of planned target achieved, remaining reward versus
  loss to the protective stop, speed/time in trade, signal condition, spread,
  volatility, session time and known event exposure.
- Design a bounded prospective comparison against the existing exit policy.
  A universal fixed "close at X%" is a hypothesis to test, not the agreed
  solution. Do not choose a rule by optimizing today's winning trade.

**After the twelve-week review — implement and validate in stages:**

- Build an intraday position-management service independent of the morning
  discovery scan, with explicit regular-session cadence and near-close
  review that respects holidays, early closes and unavailable quotes.
- Evaluate holding, raising a protective stop, closing, and partial exits
  where contract quantity permits. Make the remaining reward/downside and
  overnight-hold rationale explainable. A stop does not guarantee protection
  against an overnight gap.
- Run the proposed dynamic policy in an isolated shadow before considering
  promotion. Compare net outcomes and trade-offs over matched windows and
  retain uncertainty, missing observations and sensitivity to large winners.
- Connect broker execution only through the approved operating stages below:
  fresh position/order reconciliation, deterministic recommendation and order
  IDs, quantity-aware OCO links, cancel/replace acknowledgments, partial fills,
  restart idempotence and stale-feed handling. Never sell more contracts than
  remain held or assume an old exit order has been canceled before confirmed.
- Require explicit review before promotion, with versioned policy and rollback.
  Completing twelve weeks does not itself authorize real-money trading or
  establish that a particular exit policy works.

**Ownership:** Portfolio Management defines the decision policy; Execution
owns broker order lifecycle; Outcome Review / Learning evaluates outcomes.
The authoritative backlog entry is in `PROJECT_STATUS.md` under P2.

### Broker Account State

- Broker-derived total NAV, deployable NAV, settled and unsettled cash, buying
  power, reserved order capital, and unavailable capital
- Exact option positions by account, symbol, expiration, strike, type, quantity,
  cost basis, and broker position ID
- Complete working-order inventory, including parent/child and OCO relationships
- Freshness timestamps and explicit unavailable or stale states

### Capital and Performance Ledger

- Append-only deposits, withdrawals, entries, partial fills, exits, fees,
  assignments, expirations, adjustments, and canceled/rejected orders
- Daily beginning NAV plus flows and P/L equals ending NAV reconciliation
- Realized, unrealized, strategy-base, time-weighted deployed-capital, and total-
  NAV returns with clearly different labels
- Separate strategy outcomes from operational or user execution errors without
  changing the broker-truth record

### Order Lifecycle

- Stable decision and order-intent IDs across retries
- Explicit state machine: proposed, approved, submitted, acknowledged, partially
  filled, filled, cancel pending, canceled, rejected, expired, and reconciled
- Cancel/replace rather than additive submission when modifying working orders
- Broker confirmation before local portfolio state changes
- Recovery behavior for timeouts and uncertain submission results

### Quantity-Aware Entry and Exit Plans

Multi-contract positions require contract-level exit quantities at entry.

- Split each position into explicit exit tranches where appropriate
- Give each tranche its own profit target and protective stop/OCO relationship
- State exactly how many contracts each target or stop controls
- Ensure one tranche filling does not cancel protection for unrelated remaining
  contracts
- For `CLOSE`, cancel or replace every conflicting working order and exit the
  full remaining quantity
- For `REDUCE`, identify the quantity to sell immediately and rebuild protection
  for the retained quantity
- Reconcile fast fills before issuing a later daily recommendation

The September 8 FCX result is the motivating example: an existing OCO target
covered all three contracts, so the fast price move closed the complete position
before a later one-contract reduction could preserve a runner. The fill was
profitable, but the order structure did not express the intended staged exit.

### Risk Controls

- Long-premium calls and puts only until a separate strategy approval exists
- No naked short options, margin-defined short strategies, or implicit strategy
  expansion
- Per-position premium, expected stop loss, aggregate stop loss, concentration,
  exposure, liquidity, earnings, and stale-quote gates
- Full-premium loss stress remains visible because stops do not guarantee fills
- Configurable pilot capital, position limits, and order-size limits
- Pre-submit validation plus post-fill reconciliation
- User-accessible pause and kill-switch controls

### Human Decision Surface

The primary view should remain action-first:

- `CLOSE`: exact quantity to exit now and conflicting orders to cancel
- `REDUCE`: exact quantity to exit and protection for the retained quantity
- `HOLD`: exact stop action and target for the remaining position
- `OPEN` or `ADD`: contract, quantity, entry limit, tranche plan, maximum premium,
  stop, target, time stop, earnings date, and expiration
- Clear reasons, freshness, broker state, and approval status without presenting
  subordinate calculations as competing instructions

### Audit, Security, and Operations

- Secrets stored outside source control and logs
- Separate market-data and account/trading authorization scopes
- Immutable recommendation, approval, order-intent, broker-response, fill, and
  reconciliation artifacts
- Structured run status, alerts, retries, and failure diagnostics
- No email or scheduler success claim without an acknowledged final state
- Restore and disaster-recovery procedures tested before live activation

## Real-Money Go/No-Go Review

The November 2–12 audit resolved the concern that delayed manual entry leads
to paying above the morning ceiling. All 46 matched same-session fills were
limit orders at or below the recommended entry price, and four submitted limits
at the ceiling were canceled without a recorded fill. Treat the verified price
discipline as part of the manual workflow when assessing a pilot. See
`reports/entry_workflow_audit_20261112.md`.

Passing the evidence tracker permits a review; it does not automatically produce
a `GO` decision. Approval additionally requires:

- Complete broker-state and capital-ledger reconciliation
- Successful read-only shadow operation
- Sufficient clean paper round trips and controlled loss behavior
- Reliable scheduling, authentication, reporting, and recovery
- Documented order lifecycle and quantity-aware bracket behavior
- Explicit pilot capital and risk configuration
- Manual review of legal, tax, data-license, broker-permission, and operational
  considerations applicable at that time

Until these conditions are reviewed and approved, Project Stonks remains a paper
research and decision platform.
