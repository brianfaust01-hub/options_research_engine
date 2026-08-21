# Project Stonks Codex Instructions

## Governing context

Before planning, reviewing, or changing this repository, read `PROJECT_STATUS.md` completely. It is the governing document. Align work with its Vision, Engineering Principles, current milestone, backlog governance, and subsystem ownership.

Do not change the Vision, Engineering Principles, or architectural decisions without explicit discussion with the user.

## Required workflow

1. Inspect the current Git status and preserve all existing user changes.
2. Identify the owning subsystem and relevant backlog item before proposing a sprint.
3. State the evidence, learning value, data-integrity impact, regression risks, and success criteria for material changes.
4. Preserve backward compatibility whenever practical.
5. Run focused validation plus an appropriate regression suite before reporting completion.
6. Update `PROJECT_STATUS.md` only when sprint state, backlog state, capabilities, or governance genuinely changes.

## Data and safety

- Historical recommendations and research snapshots are immutable. Never rewrite, delete, or silently normalize them.
- Rejected, watchlist, pass, non-executable, and unallocated recommendations are research evidence and must be preserved.
- Never make production scoring, allocation, or strategy changes automatically from learning-system output.
- Do not expose, print, commit, or overwrite Schwab credentials or OAuth tokens. Token files under `data/` are local secrets.
- Treat portfolio, journal, report, log, and historical data as user-owned state. Do not regenerate or modify it during tests unless the user explicitly requests a production run.
- Prefer temporary test directories and fixtures for validation.

## Engineering boundaries

- Each subsystem owns one responsibility.
- Prefer architectural coherence over isolated feature additions.
- Capture fields needed for future hindsight before using them in optimization.
- Require evidence before adding complexity or changing weights.
- Full-file replacements are acceptable for substantial revisions; use small patches for small, isolated changes.

## Environment

- Supported local environment: Windows with a repository-local `.venv`.
- Install dependencies from `requirements.txt`.
- `run_daily_stonks.bat` launches the daily workflow from the repository root.
- External market-data validation may require network access and valid local Schwab authorization.
