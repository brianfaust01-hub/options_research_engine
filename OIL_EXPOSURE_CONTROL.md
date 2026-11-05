# Oil-linked exposure control — November 4, 2026

Brian approved immediate oil concentration control; national-election
overnight restrictions are deferred to the backlog.

The normal daily entry point now runs `src/production_scan.py` through
`src/daily_run.py`. Its separately versioned risk overlay permits one
concurrent oil-linked ticker. Existing holdings consume the slot even if a
sale is recommended; a proposed sale is not a confirmed fill. Adds to the
same name remain subject to all original quantity, premium and stop-risk
limits. Existing over-limit holdings are flagged, not automatically sold.

Coverage includes integrated companies, producers, refiners, oilfield
services/drillers, midstream/pipelines and energy/oil funds. The reviewed
symbol inventory is in `src/production_risk_controls.py`; industry/theme
metadata catches oil/petroleum/refining/drilling/pipeline classifications
outside that inventory. This is a conservative shared-driver group, not a
claim that every member has identical crude beta. Unknown companies with
missing metadata require map maintenance; coverage is not universal.

The highest forward-scored feasible oil allocation gets the available slot.
Other oil candidates remain research observations with explicit block
reasons; the allocator can select qualified non-oil alternatives. There is
no crude-price API dependency or inferred volatility threshold. One ticker
is a precautionary policy limit, not a statistically calibrated optimum.

The overlay runs only in the normal scan caller. It does not patch the
allocator module or change the frozen config/SPY sources. Research action
fields remain executable so shadows independently recompute their original
allocations. Both frozen policy fingerprints were verified unchanged.
New observations carry `ProductionRiskPolicyVersion`, source SHA-256,
scope and oil-block fields, distinguishing normal recommendations from the
pre-overlay research fingerprint. Historical evidence is not rewritten.

Use `run_daily_stonks.bat` / `daily_run.py` for normal operation. Directly
executing legacy `weekly_scan.py` bypasses this production entry point.
No broker orders are placed. Rollback: restore the daily runner's scan path
to `weekly_scan.py`; retain observations and overlay provenance.

Owning subsystem: Portfolio Allocation / Portfolio Risk. Evidence:
November 3 carried XOM and CVX together; November 4 broker daily P/L was
-$160 and -$175 respectively. Existing exposure mappings omitted both.
Regression risks: shadow contamination, counting recommended closes as
completed, suppressing research evidence, and inconsistent summary totals.
Fixture tests cover broad symbols/metadata, feasibility/ranking, actual
incumbents, preserved inputs and independent frozen-shadow allocation.
