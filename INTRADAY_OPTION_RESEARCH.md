# Intraday option research

This is market-data instrumentation, not a trading service. It never submits
orders, sends emails, reruns research, changes allocations, or changes the
current policy era. One-minute bid/ask samples cannot prove every intervening
threshold crossing or actual fills.

## Activate once, in Brian's Windows terminal

```powershell
cd C:\Users\brian\Documents\Codex\options_research_engine
.\setup_intraday_schedule.ps1
```

This registers **Project Stonks Intraday Option Research**, independently of
the daily scan. An existing research task is not overwritten unless `-Replace`
is supplied. The setup starts one invocation immediately; the repeating daily
trigger invokes the runner every minute. The runner's Eastern-hours gate avoids
off-hours Python/API work. The NYSE calendar restricts quotes to conservative
09:30–16:00 equity regular hours, adjusted for holidays and early closes; this
does not include any product-specific extended option sessions.

The laptop must be awake, Brian signed in, network available, and Schwab OAuth
valid. Wake-to-run cannot overcome this laptop's Modern Standby limitation.
Restart recovery does not backfill missing quotes. The wrapper pauses while
the scheduled daily scan is Running, avoiding its shared OAuth-refresh window;
those minutes are gaps. Pause the research task before manual OAuth renewal or
manual scans, then resume it afterward if necessary.

```powershell
Disable-ScheduledTask -TaskName "Project Stonks Intraday Option Research"
Enable-ScheduledTask -TaskName "Project Stonks Intraday Option Research"
Get-ScheduledTaskInfo -TaskName "Project Stonks Intraday Option Research"
Get-Content .\logs\intraday_options_2026-09-18.log -Tail 5
.\.venv\Scripts\python.exe src\intraday_option_paths.py --health-date 2026-09-18
```

`--health-date` is read-only and never contacts Schwab. It reports elapsed
expected minute slots, missing slots, partial/empty slots, corrupt artifacts,
and per-contract usable slot counts. Missing entry coverage remains unknown;
session coverage is not the same as recommendation-to-exit coverage.

## Evidence and bounds

- Tracks exact selected long-call/put symbols from the last 60 calendar days,
  allocated and unallocated, excluding expired/future recommendations. Missing
  symbols remain counted; alternative selection snapshots are not automatically
  added to the longitudinal quote universe.
- Up to 50 symbols per request, five-second request timeout, 30-second soft
  budget, rotated batch priority, 45-second wrapper deadline, and a Windows OS
  lock plus scheduler IgnoreNew prevent overlapping collector invocations.
- Only explicitly realtime, valid bid/ask quotes aged 0–60 seconds qualify.
  Quote/receipt timestamps and all unusable/failure statuses are preserved.
- Exclusive compact gzip artifacts live in ignored
  `data/processed/intraday_option_paths/YYYY-MM-DD/`. Each includes exact-symbol
  recommendation IDs, allocation/era/fingerprint lineage, quote/Greek/IV values,
  and recommendation reference prices labeled **not broker fills**.
- No historical records are edited. No automatic deletion/retention purge is
  enabled; keep raw evidence through baseline and challenger review and check
  storage size and coverage weekly. Logs rotate by day without deletion.
- `sampled_path` is a pure research helper for ordered bid-liquidation returns
  given a separately attributed entry time/price. It preserves gaps and reports
  only first **observed** hits. It does not infer a fill at the trigger, true
  first-event order, a completed maturity horizon, or complete overnight paths.
- No output is automatically exported to `option_exit_paths.csv`. The existing
  empirical exit policy remains uncalibrated until a separately reviewed,
  entry-aligned, gap-aware sampled-path analysis is accepted. Tick-complete
  first-event inference would require richer evidence than polling.

## Verify before relying on accumulation

After activation during regular hours, confirm a new gzip artifact, successful
task invocation, and usable quotes in the health report. Audit coverage again
after the daily scan and the next morning. Fixture tests validate code only;
they do not establish live authorization or unattended laptop reliability.
