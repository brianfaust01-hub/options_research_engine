PROJECT STATUS — Project Stonks

Version: v0.3.0-alphaCurrent Milestone: Institutional Research PlatformCurrent Sprint: Sprint 33C – Institutional Trade Scoring & Portfolio Decision EngineStatus: ACTIVE DEVELOPMENT

Vision

Project Stonks exists to maximize long-term risk-adjusted returns by continuously learning which research signals, option structures, execution techniques, portfolio decisions, and risk management practices outperform through evidence—not intuition.

Project Stonks is not an options screener.

Project Stonks is an institutional-quality decision engine that:

Generates investment ideas

Constructs trades

Evaluates execution quality

Allocates capital

Tracks outcomes

Learns from historical performance

Continuously improves itself

Every recommendation must produce a permanent research artifact regardless of whether capital is allocated.

Recommendations that are never executed are still valuable because they provide counterfactual evidence that improves future research, execution, and portfolio decisions.

The system learns from every hypothesis, not just executed trades.

Governance

This document is the governing document for Project Stonks.

Every development session begins by reading this document.

Architecture will evolve.

Implementation details may change.

Engineering Principles, Vision, and Architectural Decision Records (ADRs) only change after explicit discussion.

Every sprint proposal must:

Align with the Vision

Reference the Engineering Principles

Include regression validation

Explain how it improves learning, confidence, execution, returns, or risk management

Long-Term Architecture

Research Engine
        │
        ▼
Market Thesis
        │
        ▼
Strategy Optimizer
        │
        ▼
Contract Optimizer
        │
        ▼
Execution Engine
        │
        ▼
Trade Scoring Engine
        │
        ▼
Portfolio Allocation Engine
        │
        ▼
Paper Portfolio
        │
        ▼
Outcome Review
        │
        ▼
Learning Engine
        │
        ▼
Research Engine

The Learning Engine remains the center of the product.

Every release should strengthen this feedback loop.

Current Capabilities

Research

Full S&P 500 scan

Market regime analysis

Market breadth analysis

Trend engine

Momentum engine

Opportunity scoring

Research confidence scoring

Contract Selection

Horizon-aware contract selection

Liquidity-aware contract ranking

DTE optimization

Contract scoring

Research pricing

Execution

Conservative execution modeling

Bid/Ask spread analysis

Execution scoring

Execution grading

Immediate liquidation analysis

Research price vs expected fill comparison

Trade Scoring

Trade Quality Engine

Institutional Trade Score

Institutional Trade Grade

Research component scoring

Contract component scoring

Execution component scoring

Trade Quality component scoring

Portfolio

Paper portfolio

Market-aware allocation

Portfolio Score

Position sizing

Automatic portfolio ranking

Learning

Immutable recommendation snapshots

Trade journal

Outcome review

Weekly learning reports

Historical validation

Structured learning dataset

Automation

Daily batch execution

Windows Task Scheduler

Automated journal updates

Automated portfolio updates

Automated weekly learning

Current Milestone

Institutional Decision Engine

Current focus:

Institutional Trade Score

Portfolio Decision Quality

Learning Feedback

Data Integrity

Product Roadmap

Phase 1 ✅

Build the Engine

Completed

Research Engine

Options Engine

Contract Selection

Paper Trading

Automation

Phase 2 ✅

Build the Scientist

Completed

Learning Pipeline

Weekly Learning

Immutable Research History

Outcome Review

Execution Analysis

Phase 3 (Current)

Build the Institutional Portfolio Manager

Current priorities

Institutional Trade Scoring

Portfolio Allocation

Execution Quality

Portfolio Decision Quality

Phase 4

Adaptive Portfolio Management

Future

Correlation management

Sector balancing

Industry balancing

Adaptive position sizing

Strategy optimization

Learning-driven score optimization

Completed Sprints

Sprint 30A

Recommendation snapshots

Learning validation

Weekly learning

Outcome review

Sprint 31A

Atomic journal writes

Snapshot integration

Journal repair utilities

Data integrity validation

Sprint 32A

Execution scoring

Bid/Ask analysis

Execution grades

Conservative pricing

Execution reporting

Sprint 33A

Institutional Trade Score

Institutional Trade Grade

Component scoring

Trade scoring engine

Sprint 33B

Portfolio Score

Allocation refactor

Market-aware portfolio ranking

Institutional Trade Score integration

Sprint 33C

Single risk budget

Simplified position sizing

Position sizing cleanup

Engineering Principles

Every subsystem owns one responsibility.

Learning is prioritized over feature growth.

Historical recommendations are immutable.

Evidence precedes optimization.

Every sprint includes regression validation.

Every release should increase confidence.

Subsystem ownership:

Research Engine → Finds opportunities.

Contract Optimizer → Chooses contracts.

Execution Engine → Evaluates tradability.

Trade Scoring Engine → Produces Institutional Trade Score.

Portfolio Allocation Engine → Chooses what to own.

Learning Engine → Improves future decisions.

Immediate Priorities

Portfolio diversification

Sector concentration

Industry concentration

Correlation penalties

Existing holdings

Validate Institutional Trade Score as a predictor of future performance.

Broker reconciliation (ThinkOrSwim / Schwab).

Strategy optimization beyond long calls/puts.

Experiment Queue

High Priority

Institutional score validation

Sector concentration engine

Portfolio correlation engine

Broker reconciliation

Strategy optimizer

Medium Priority

Learning-driven score weights

Adaptive position sizing

Portfolio optimization

Historical execution analysis

Strategy attribution

Low Priority

Advanced volatility strategies

Multi-leg optimization

Portfolio hedging

Dynamic capital allocation

Weekly Learning Objectives

Every weekly report should answer:

What happened?

Why did it happen?

What did we learn?

Which scores best predicted success?

Did execution help or hurt?

Which experiment should be prioritized next?

Did any subsystem regress?

The Learning Engine proposes experiments.

It never automatically changes production behavior.

Success Criteria

Project Stonks succeeds when it continuously improves because of evidence generated from its own research, execution quality, portfolio decisions, and historical outcomes.

The objective is not simply to predict stock prices.

The objective is to build an institutional-quality decision engine that becomes more accurate, more disciplined, and more evidence-driven every week.

# Working Style

When contributing to Project Stonks:

- Read PROJECT_STATUS.md before proposing changes.
- Prefer architectural improvements over isolated feature additions.
- Preserve backwards compatibility whenever practical.
- Minimize technical debt.
- Prefer evidence over intuition.
- Full-file replacements are preferred over partial patches unless only a few lines change.
- Every new subsystem should have a single, well-defined responsibility.
- Every sprint should identify regression risks and define how success will be validated.
- When appropriate, propose future extensibility even if it is not implemented immediately.