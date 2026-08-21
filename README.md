# Project Stonks

Project Stonks is an evidence-driven options research, trade scoring, portfolio allocation, and learning platform.

`PROJECT_STATUS.md` is the governing project document. Read it before proposing or implementing changes.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the daily research workflow with `run_daily_stonks.bat`. Schwab OAuth token files live under `data/` and are intentionally ignored by Git.

Run the read-only hindsight integrity audit with:

```powershell
.\.venv\Scripts\python.exe -B src\hindsight_data_audit.py
```

Run the read-only allocation-capacity audit with:

```powershell
.\.venv\Scripts\python.exe -B src\allocation_capacity_audit.py --recent-files 20
```

## Development

- Preserve immutable recommendation history.
- Capture information needed for future hindsight before optimizing behavior.
- Do not change production scoring without evidence and explicit approval.
- Include regression validation with every sprint.
- Keep generated research artifacts and credentials out of commits unless their inclusion is deliberate and reviewed.
