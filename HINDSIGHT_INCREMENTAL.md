# Incremental hindsight updates

Routine hindsight updates reuse completed historical outcomes instead of
reevaluating every recommendation. `research_hindsight.py` remains the entry
point; no daily task or trading policy changes.

- Each completed 3/5/7/14/30-session outcome is reused independently. A finished
  seven-day outcome stays fixed while longer horizons mature.
- Rows with complete final outcomes and all five horizons skip evaluation and
  price-history requests entirely. Non-directional rows also skip evaluation.
- New recommendations, unfinished horizons and missing benchmark outcomes
  continue updating. Input fingerprints invalidate reuse if journal inputs
  change. Historical snapshots and recommendations remain untouched.
- The first incremental update can seed from the latest existing hindsight
  CSV. This legacy import checks ID, ticker, date, strategy/action and available
  entry price; its manifest explicitly says the old full input fingerprint was
  unavailable. Subsequent outputs carry full input fingerprints and checksums.
- Completed rows retain their recorded current marks and evaluation as-of.
  Legacy rows lacking a row-level as-of say that the old source time was not
  recorded; they are not presented as freshly marked positions.
- A new timestamped full CSV preserves downstream compatibility. Its archived
  rows are carried forward; cheap local report aggregation/rendering can still
  include every week. Old CSVs and reports are never overwritten. Incomplete
  writes remain outside the latest-CSV pattern. Source/output checksums and
  reuse counts are recorded in a companion manifest.

Normal update: `.venv\Scripts\python.exe src/research_hindsight.py`

Read-only plan, no network or output writes:
`.venv\Scripts\python.exe src/research_hindsight.py --plan`

Explicit full recalculation into a new artifact:
`.venv\Scripts\python.exe src/research_hindsight.py --rebuild`

Use a rebuild for a reviewed price-basis correction, changed evaluator
semantics, or intentionally restating history. Do not silently mix new
historical prices with previously completed outcomes. A cache schema/semantic
change must update `hindsight_incremental.VERSION`; quality exclusions remain
separate derived views and do not rewrite raw outcomes.

## November 6 read-only assessment

The latest existing output has 44,261 unique recommendations. The initial plan
can reuse 35,827 complete/non-directional rows (80.9%), leaving 8,434 pending
or new rows. It can preserve 18,728 completed seven-session outcomes while
other horizons continue updating. These are work counts, not measured runtime
or token savings. No market-data fetch or production report rebuild was run
to obtain them.

## Reporting and token use

The hindsight calculation and Markdown/HTML reports use deterministic local
Python, not an LLM. Recalculation therefore costs local processing and market
data requests, rather than model tokens. Repeatedly loading and reinterpreting
full archives in chat adds model context. Future routine reviews should lead
with the current/pending weeks and changed findings, referencing archived
matured-week summaries. Reopen archived analysis only for a specific comparison,
correction or requested audit. This reporting convention does not omit old
losses or remove historical weeks from cumulative totals.
