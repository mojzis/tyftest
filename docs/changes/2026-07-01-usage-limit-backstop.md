# 2026-07-01 — usage-limit backstop in the drive loop

## What changed

The matrix driver now detects when a cell's headless `claude -p` run ended
because the **Claude usage limit** was hit (distinct from a wall-clock timeout,
which stays a real convergence failure). On detection it does **not** score the
cell — a limited run is not a valid result — and instead:

- parses the reset time, then
- if the reset lands within `LIMIT_WAIT_MAX` seconds (default 1800), sleeps until
  the reset (+15s) and **retries the same cell**;
- otherwise reports the reset time and remaining cell count and aborts with
  exit code 3, so the run can be resumed later.

## Why

A usage-limit termination invalidates the cell and every following cell would
hit the same wall, silently polluting results with non-converged rows. Better to
pause/resume than to record garbage.

## Files touched

- `harness/limit_check.py` (new) — scans a transcript for the limit signal and
  extracts the reset epoch. Signals: a `result` event whose `result`
  (final_answer) matches `usage limit reached[|<epoch>]`; a `rate_limit_event`
  with `rate_limit_info.status == "rejected"`; or the same text in `claude.err`.
  Exit 0 if limited, 1 if not. Reset epoch from the final_answer `|<epoch>` if
  present, else the rejected event's `resetsAt`.
- `harness/drive.sh` — per-cell retry loop wrapping run→score; env
  `LIMIT_WAIT_MAX` knob; exit code 3 on report-and-abort.

## What it invalidates

Nothing in existing results. Purely a run-discipline addition; scoring, gating,
and row schema are unchanged. Rows that would previously have been written from a
limited run (subtype/terminal_reason null, converged=false) are now skipped
instead — so future rounds won't contain limit-induced non-converged rows.
