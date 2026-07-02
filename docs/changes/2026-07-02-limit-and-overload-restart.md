# 2026-07-02 — limit detection fixed for new CLI message; overload runs discarded + re-run fresh

## What changed

1. **`limit_check.py` now catches the current CLI limit message.** The backstop
   added on 07-01 only matched `usage limit reached[|<epoch>]`, but the CLI
   actually emits `You've hit your session limit · resets 4:40pm
   (Europe/Prague)` (seen in all 11 limited rows of round-3 dlt-120 run1) — so
   the backstop never fired: garbage rows were scored and every following cell
   burned against the same wall. The check now also matches `hit your …
   limit` and parses the human reset time (`resets H[:MM]am/pm (Zone)`, IANA
   zone via zoneinfo, next occurrence of that wall-clock) into an epoch.

2. **`drive.sh` waits out any reset and re-runs the cell fresh.** Defaults
   retuned for unattended overnight runs: `LIMIT_WAIT_MAX` 1800→21600 s (a
   5h-window reset is at most ~5h away, so we always sleep through it, even
   twice a night), `LIMIT_FALLBACK_WAIT=3600` when limited but no reset time
   parses, `LIMIT_MAX_RETRIES=4` per cell before aborting with exit 3.
   Nothing is ever resumed: `run.sh` wipes `$RUN` on every invocation, so a
   retry is a byte-identical fresh restart of the same cell.

3. **New `interruption_check.py` + drive-loop backstop for transient API
   failures.** Round-4 A-rep4 hit a 529 Overloaded mid-session and the CLI
   auto-resumed in place (2 init + 2 result events in one transcript,
   per-segment stats — see 2026-07-02-round4-data-collection-issues.md issue
   1). Such runs are not comparable to clean ones, so they are now detected
   (multiple result/init events, or a result text that *is* an API error —
   anchored match so a real answer mentioning "API error" doesn't trigger)
   and the cell is discarded and re-run fresh after exponential backoff
   (`OVERLOAD_BACKOFF=180` s doubling, `OVERLOAD_MAX_RETRIES=3`; after that
   the cell is skipped with a loud log, not scored).

Ordering in the loop: limit check first (wait-for-reset semantics), then
interruption check (quick-backoff semantics), then score.

## Files touched

- `harness/limit_check.py` — new message format + wall-clock reset parsing
- `harness/interruption_check.py` (new)
- `harness/drive.sh` — retuned limit backstop, new overload backstop, per-cell
  retry counters

## What it invalidates

Nothing retroactively; run-discipline only. But it explains two known bad
artifacts: the round-3 run1 "capped" rows (limit message unmatched → scored
garbage) and round-4 A-rep4's per-segment stats (in-place 529 resume). Future
rounds cannot produce either: limited/interrupted runs are never scored — the
cell is re-run fresh or the matrix stops with a clear resume message.
