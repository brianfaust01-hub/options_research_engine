# PROJECT STATUS — Project Stonks

Version: v0.3.0-alpha
Current Milestone: Paper Trading MVP
Current Sprint: Sprint 30A - Learning & Feedback Loop Foundation
Status: ACTIVE DEVELOPMENT

---

# Vision

Project Stonks exists to maximize long-term risk-adjusted returns by continuously learning which research signals, option structures, execution techniques, and portfolio decisions outperform through evidence—not intuition.

Project Stonks is NOT an options screener.

Project Stonks is an institutional-quality research platform that:

- Generates investment ideas
- Constructs trades
- Assists execution
- Tracks outcomes
- Learns from historical performance
- Continuously improves itself

Every generated recommendation must produce a permanent research artifact, regardless of whether capital is allocated. Unexecuted recommendations provide counterfactual evidence that is essential for evaluating research quality, strategy selection, and portfolio decisions. The system learns from all hypotheses, not only executed trades.

---

# Governance

This document is the governing document for Project Stonks.

Every development session must begin by reading this document.

Implementations may change.

Architecture may evolve.

Engineering Principles, Vision, and ADRs should only change after explicit discussion and documented rationale.

Every sprint proposal must:

- Align with the Vision
- Reference the Engineering Principles
- Include regression validation
- Explain how it improves learning, confidence, returns, or risk management

# Long-Term Architecture

Research Engine
↓

Market Thesis

↓

Strategy Optimizer

↓

Contract Optimizer

↓

Execution Assistant

↓

Outcome Tracker

↓

Learning Engine

↓

Research Engine

The learning engine is the center of the product.

Every release should strengthen this feedback loop.

---

# Current Capabilities

## Research

- Full S&P 500 scan
- Market regime analysis
- Breadth analysis
- Trend engine
- Momentum engine
- Opportunity scoring
- Confidence scoring

## Options

- Horizon-aware contract selection
- Liquidity-aware scoring
- DTE optimization
- Paper portfolio allocation

## Automation

- Daily batch execution
- Windows Task Scheduler
- Daily logging
- Paper trade journal
- Open trade review

---

# Current Open Paper Trades

(Currently maintained automatically)

Example:

- IBKR
- UPS

(C should now be manually marked closed until broker reconciliation exists.)

---

# Product Roadmap

## Phase 1 ✅

Build the Engine

Completed

- Research engine
- Options engine
- Portfolio allocation
- Automation
- Paper trading

---

## Phase 2 (Current)

Build the Scientist

Current priorities:

1. Learning feedback loop
2. Execution quality
3. Data integrity
4. Weekly research review

---

## Phase 3

Build the Portfolio Manager

Future:

- Correlation management
- Portfolio optimization
- Sector balancing
- Risk budgeting

---

# Sprint 30A

Objective:

Validate that Project Stonks is actually learning correctly.

Before adding new trading features we must confirm:

- recommendations are stored correctly
- outcomes are updated correctly
- historical data is preserved
- weekly insights are accurate
- experiments are evidence based

---

# Immediate Priorities

## 1

Audit learning pipeline.

Verify:

Recommendation

↓

Journal

↓

Outcome Review

↓

Weekly Learning

↓

Insight Generation

---

## 2

Improve execution quality.

Future work:

- better limit pricing
- slippage measurement
- broker reconciliation
- execution guidance

---

## 3

Dynamic stop recommendations.

NOT fixed percentages.

Future stop logic should consider:

- Delta
- Gamma
- Theta
- Vega
- IV
- Expected move
- ATR
- Standard deviation
- Time remaining

---

## 4

Strategy Research

Long-term Project Stonks should determine not only:

"What contract?"

but

"What strategy?"

Examples:

- Long Call
- Long Put
- Bull Call Spread
- Bear Put Spread
- Cash Secured Put
- Covered Call
- Iron Condor
- Calendar
- etc.

The learning engine should determine which structure best expressed the thesis.

---

# Engineering Principles

## Vision Alignment

Every sprint must explicitly state:

- why it exists
- which long-term objective it advances
- what future capability it unlocks

---

## Regression Validation

Every release must validate:

✓ Research engine

✓ Market regime

✓ Opportunity scoring

✓ Option selection

✓ Capital allocation

✓ Trade journal

✓ Outcome review

✓ Learning dataset

✓ Automation

No release is complete without regression validation.

---

## Learning First

When forced to choose between:

adding features

or

improving learning

prefer improving learning.

---

## Evidence Before Optimization

Do not modify:

- thresholds
- scoring
- indicators
- strategies

without sufficient historical evidence.

Ideas enter the Experiment Queue first.

---

## Preserve Historical Truth

Historical recommendations are immutable.

Never overwrite historical recommendations.

Future versions should explain differences, not rewrite history.

---

## Backwards Compatibility

Prefer wrappers and compatibility layers over breaking interfaces.

Avoid downstream regressions.

---

## Validation Before Completion

A sprint is complete only when:

- code executes
- outputs exist
- automation succeeds
- learning data is preserved
- regression checklist passes

---

## Every Release Must Increase Confidence

Every sprint should increase confidence in at least one of:

- research
- execution
- automation
- learning
- data integrity

Not every sprint must improve returns.

Every sprint must improve confidence.

---

# Experiment Queue

Current High Priority

☐ Validate learning pipeline

☐ Broker reconciliation (CSV)

☐ Execution quality improvements

☐ Dynamic stop framework

☐ Weekly learning report

Medium Priority

☐ Strategy optimizer

☐ DTE optimization

☐ Position sizing optimization

☐ Portfolio optimization

Low Priority

☐ Additional strategy library

☐ Advanced volatility strategies

---

# Weekly Learning Objectives

Every weekly report should answer:

1. What happened?

2. Why did it happen?

3. What did we learn?

4. Did we collect enough data?

5. What should we test next?

6. Which experiment should be prioritized?

7. Did any system regress?

The weekly report should propose experiments—not automatically change the model.

---

# Success Criteria

Project Stonks succeeds when it continuously improves because of evidence generated from its own historical decisions.

The objective is not to predict stocks.

The objective is to build an institutional-quality research platform that becomes better every week.