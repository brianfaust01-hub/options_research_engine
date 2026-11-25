# Original exit plans and daily collection recovery — November 24, 2026

## Applied repairs

Broker Reconciliation / Paper Portfolio now preserve `ProfitTarget`, `StopLoss`
and `TimeStopDTE`, with the exact originating recommendation ID and resolution
status. `original_exit_plans.py` fills missing plan fields only after matching
ID, contract, direction and chronology. Conflicting IDs, wrong contracts and
unverified times remain unresolved. Existing explicit levels and separately
ratcheted `RecommendedStop` values are preserved. Closed historical rows are
not backfilled; immutable recommendations and broker statements are untouched.

Portfolio loading restores missing original plans for the existing morning
review, without a read operation writing the portfolio file. Reconciliation
persists those fields for new and refreshed positions. `allocate_position`
accepts optional explicit entry-plan fields without breaking legacy callers.
Legacy rows without a recoverable origin retain the existing fallback behavior
and have an explicit unresolved status in the portfolio. This repair does not
redefine exit percentages or reprice original levels from a different actual fill.

The current mutable portfolio was backed up, verified and repaired:

| Position | Original target | Original stop | Recorded stop retained | Time stop |
|---|---:|---:|---:|---:|
| JPM January $310 put | $13.33 | $8.23 | $8.23 | 14 DTE |
| UBER January $65 put | $4.56 | $2.74 | $2.74 | 14 DTE |

The previous missing-target fallback would have shown $17.15 for JPM and
$5.60 for UBER. Future holding guidance now reads the originating plans.
Quantities, entry/mark prices, P/L and existing stops were verified unchanged.
No broker orders were submitted or edited and no old report was restated.

## Daily research collector

The recurring exception came from
`sample_20261104T153819_879f8196041b_002350.json`: 114,828 bytes, malformed JSON
at line 2746 / column 108. Its SHA-256 is
`b83ce48b5253e1a739f2f08786fa9c8de62da2b101b7065b53713cd6575ad73e`.

The new normal-run entry point `option_observation_recovery.py` validates
historical sample structure before calling the existing collector. Unreadable
stable files are moved into the observation directory's `quarantine/`, with
exclusive planned/completed provenance manifests, original/new paths and a
verified identical byte hash. It never silently repairs quotes, overwrites a
sample or treats missing observations as successful capture. Recent files that
may still be actively written are left untouched and recovery defers visibly.
Resolved move paths must remain inside the observation directory.

The identified file has been preserved in quarantine. All 1,146 remaining
historical sample bundles validate. No missing historical quotes were backfilled.

The adapter also installs a process-local atomic artifact writer while the
legacy collector runs in its dedicated subprocess, then restores the original
writer even on failure. New JSON is written/flushed to a non-sample temporary
name before an atomic, non-replacing Windows rename. An interrupted write
therefore cannot expose a half-written `sample_*.json` to the next run. Quote
requests, normalization, sampling rules and timestamps are unchanged.

`daily_run.py` points to this recovery entry point. The 45-second isolation from
the already-sent email remains. Historical validation took approximately 1.25
seconds in the local check. Manual normal collection can use the new entry
point too; `--inspect-only` validates without moving files or requesting quotes.

## Frozen experiment isolation and verification

The frozen `position_review.py` and `option_observation_collector.py` sources
were not changed. The source/dependency fingerprints for both the broad
comparison and SPY remain unchanged; the broad release manifest and current
ledger fingerprint match. Existing shadows and policy rules were not reset,
rebound or migrated. This is normal portfolio-state and collection-IO repair.

Fixture coverage includes original-ID/contract/time conflicts, missing plans,
legacy fallback, creation/refresh persistence, preservation of raised stops,
quarantine hash/manifest/idempotency, active-writer protection, atomic interrupted
writes and a real collector run with injected fixture quotes. Full repository
regression and boundary-review validation accompany the change: all 341 tests
pass, plus a final recovery-fixture rerun after schema-reader hardening. Tests use
temporary data; no test sends email or accesses a broker.

Backups and the applied repair manifest are in the chat outputs
`repairs-20261124/`. That manifest records before/after portfolio hashes,
preserved corrupt artifact paths and protected-source/fingerprint checks.
Next-session capture still needs normal operational observation; this repair
does not claim a live post-market collection or inbox delivery.
