# Project Stonks — Schwab Authentication Guide

This document explains how to maintain Schwab authentication for Project Stonks.

There are two separate Schwab authentication systems:

1. **Market Data**
   - Quotes
   - Price history
   - Option chains
   - Used heavily by `daily_run.py`

2. **Accounts & Trading**
   - Account information
   - Transactions
   - Trading-related API access

They use separate token files and should not be confused.

---

# Market Data Authentication

## Important Files

Authentication:

```text
src/schwab/market_auth.py
```

Automatic token management:

```text
src/schwab/market_token_manager.py
```

Stored tokens:

```text
data/schwab_market_tokens.json
```

Required environment variables:

```text
SCHWAB_MARKET_CLIENT_ID
SCHWAB_MARKET_CLIENT_SECRET
```

The code also supports these older fallback names:

```text
SCHWAB_CLIENT_ID
SCHWAB_CLIENT_SECRET
```

Prefer the dedicated `SCHWAB_MARKET_*` variables.

---

# How Authentication Works

There are three separate credentials/tokens involved.

## 1. Client ID and Client Secret

These identify the Schwab developer application.

They are required when:

- Performing the full OAuth authorization flow
- Refreshing an expired access token

They must NEVER be committed to Git.

Project Stonks expects them as environment variables.

---

## 2. Access Token

The Market Data access token lasts approximately:

```text
30 minutes
```

You normally DO NOT need to manage this manually.

`market_token_manager.py` automatically refreshes it when necessary.

---

## 3. Refresh Token

The refresh token is tracked by Project Stonks as valid for:

```text
7 days
```

It allows the system to automatically obtain new 30-minute access tokens.

Once the refresh token expires, the full OAuth authorization process must
be completed again.

---

# Normal Daily Operation

Normally just run:

```powershell
python src\daily_run.py
```

You do NOT need to manually refresh the 30-minute access token.

If necessary, Project Stonks will automatically print:

```text
Refreshing Schwab Market Data access token...
Schwab Market Data access token refreshed.
```

This is normal.

---

# Check Market Data Token Status

Run:

```powershell
python src\schwab\market_token_manager.py
```

Example healthy output:

```text
Schwab Market Data Token Manager

Access Token Valid: False
Refresh Token Valid: True

Requesting valid access token...
Refreshing Schwab Market Data access token...
Schwab Market Data access token refreshed.
Valid access token available: True
```

An expired access token is NOT a problem if the refresh token is still valid.

---

# Weekly Refresh Token Renewal

When the Market Data refresh token expires, perform the full OAuth flow.

First make sure the Market Data credentials are available in the current
PowerShell session.

Check without displaying the credentials:

```powershell
if ($env:SCHWAB_MARKET_CLIENT_ID) { "CLIENT ID: SET" } else { "CLIENT ID: MISSING" }
if ($env:SCHWAB_MARKET_CLIENT_SECRET) { "CLIENT SECRET: SET" } else { "CLIENT SECRET: MISSING" }
```

Expected:

```text
CLIENT ID: SET
CLIENT SECRET: SET
```

If either is missing, restore the credentials before continuing.

DO NOT paste the Client ID or Client Secret into logs, GitHub, documentation,
or ChatGPT.

Then run:

```powershell
python src\schwab\market_auth.py
```

The script will print a Schwab authorization URL.

1. Copy the URL.
2. Open it in a browser.
3. Log into Schwab.
4. Authorize the application.
5. Schwab redirects the browser to `https://127.0.0.1`.
6. The browser may display an error because no local web server is running.
   This is expected.
7. Copy the COMPLETE callback URL from the browser address bar.
8. Paste the callback URL into the PowerShell prompt.

DO NOT share the callback URL. It contains a temporary authorization code.

Successful output should resemble:

```text
Authorization code extracted successfully.
Market Data token exchange successful.
Market Data tokens saved to local storage.
Access token received: True
Refresh token received: True
Expires in: 1800 seconds
```

The new tokens are stored in:

```text
data/schwab_market_tokens.json
```

---

# Verify Authentication After Weekly Renewal

Run:

```powershell
python src\schwab\market_token_manager.py
```

You want:

```text
Refresh Token Valid: True
Valid access token available: True
```

Then `daily_run.py` can be run normally:

```powershell
python src\daily_run.py
```

---

# After a Computer Restart

Environment variables set only with PowerShell commands such as:

```powershell
$env:SCHWAB_MARKET_CLIENT_ID="..."
```

exist ONLY in that PowerShell process.

They disappear when:

- PowerShell closes
- Windows restarts
- A new terminal session is opened

The token file itself survives a restart.

Therefore, after a restart it is possible to have:

```text
Refresh Token Valid: True
```

but still receive:

```text
RuntimeError:
Schwab Market Data client ID environment variable is not set.
```

This DOES NOT mean the refresh token is bad.

It means the token manager cannot authenticate the refresh request because
the Schwab application credentials are unavailable.

Restore:

```text
SCHWAB_MARKET_CLIENT_ID
SCHWAB_MARKET_CLIENT_SECRET
```

and test again with:

```powershell
python src\schwab\market_token_manager.py
```

Do NOT perform another OAuth authorization unless the refresh token is
actually expired.

---

# Persist Credentials Across Windows Restarts

To avoid re-entering credentials after every restart, they can be stored as
Windows User environment variables.

Run locally, substituting the real values:

```powershell
[Environment]::SetEnvironmentVariable(
    "SCHWAB_MARKET_CLIENT_ID",
    "YOUR_CLIENT_ID",
    "User"
)

[Environment]::SetEnvironmentVariable(
    "SCHWAB_MARKET_CLIENT_SECRET",
    "YOUR_CLIENT_SECRET",
    "User"
)
```

Never commit the actual values to Git.

After setting these variables, open a NEW PowerShell window.

Verify:

```powershell
if ($env:SCHWAB_MARKET_CLIENT_ID) { "CLIENT ID: SET" } else { "CLIENT ID: MISSING" }
if ($env:SCHWAB_MARKET_CLIENT_SECRET) { "CLIENT SECRET: SET" } else { "CLIENT SECRET: MISSING" }
```

Both should report:

```text
SET
```

---

# Troubleshooting

## Error: Client ID environment variable is not set

Example:

```text
RuntimeError:
Schwab Market Data client ID environment variable is not set.
```

First run:

```powershell
python src\schwab\market_token_manager.py
```

If it reports:

```text
Refresh Token Valid: True
```

DO NOT redo OAuth.

Restore the Market Data Client ID and Client Secret environment variables.

Then rerun:

```powershell
python src\schwab\market_token_manager.py
```

---

## Error: Refresh token expired

If the token manager reports:

```text
Refresh Token Valid: False
```

or:

```text
Schwab Market Data refresh token has expired.
Complete OAuth authorization again.
```

run:

```powershell
python src\schwab\market_auth.py
```

and complete the weekly OAuth process.

---

## daily_run.py skips large numbers of stocks

Symptoms may look like:

```text
Skipping SO: 'SO'
Skipping LUV: 'LUV'
Skipping SBUX: 'SBUX'
...
```

followed later by errors such as:

```text
KeyError: 'ticker'
```

Do NOT assume this is an Opportunity Engine or portfolio allocator problem.

First verify Schwab Market Data authentication:

```powershell
python src\schwab\market_token_manager.py
```

If authentication is broken, fix it before troubleshooting downstream
research-engine errors.

A Market Data authentication failure can prevent price data from loading,
which then causes downstream components to fail because the expected ticker
data does not exist.

---

# Quick Recovery Checklist

If `daily_run.py` suddenly fails:

```text
1. STOP the run.

2. Run:
   python src\schwab\market_token_manager.py

3. Refresh Token Valid = True?
   YES -> Do NOT redo OAuth.
          Check SCHWAB_MARKET_CLIENT_ID and
          SCHWAB_MARKET_CLIENT_SECRET.

   NO  -> Run:
          python src\schwab\market_auth.py

4. Confirm:
   Valid access token available: True

5. Run:
   python src\daily_run.py
```

---

# Accounts & Trading Authentication

Accounts & Trading authentication is separate from Market Data.

Files:

```text
src/schwab/auth.py
src/schwab/token_manager.py
```

Token storage:

```text
data/schwab_tokens.json
```

Do not use the Accounts & Trading token files to troubleshoot Market Data
authentication.

Likewise, do not replace Market Data tokens when troubleshooting Accounts &
Trading authentication.

---

# Security Rules

Never commit or share:

- Schwab Client Secret
- Access tokens
- Refresh tokens
- OAuth callback URLs containing authorization codes
- `schwab_market_tokens.json`
- `schwab_tokens.json`

Safe information to share while troubleshooting:

- Whether a token is valid
- Expiration timestamps
- HTTP status codes
- Exception names/messages with credentials and tokens removed
- Whether environment variables report SET or MISSING