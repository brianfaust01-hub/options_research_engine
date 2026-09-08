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
