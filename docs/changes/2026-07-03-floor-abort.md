# 2026-07-03 — opt-in floor-abort: stop a task's reps once both arms floor

## What changed

`drive.sh` gained an **opt-in** backstop that skips a task's remaining reps once
a small pilot shows the task fails in **every** condition — no arm passed, so the
cell can't discriminate A vs D and the extra reps only burn spend (dlt-140 spent
~$45 across 10 opus runs to score 0/0). Off by default; behavior with
`FLOOR_ABORT=0` is byte-identical to before.

Design constraints that shaped it:
- **Failure-only.** Never triggers on a pass — all-pass is the desired outcome,
  and a clean comparison is the *happier* result. Abort fires only when the
  pilot is unanimous failure.
- **Comparison-safe.** The most valuable result in the experiment is
  "A fails, D passes". So the abort requires failure across **both** arms; if
  either condition's pilot rep passes, the full matrix runs. An asymmetric win
  is never thrown away.
- **Same results file.** No separate pilot phase/file. Pilot cells write their
  normal per-invocation row to the same `$OUT`; abort just stops launching the
  rest. A floored task simply shows a thin `n` (2 rows instead of 10).

Mechanism: when `FLOOR_ABORT=1`, the cell list is split into a PILOT phase
(rep `1..FLOOR_PILOT_PER_COND` of every cond, shuffled) that runs **before** the
BULK (shuffled), so a both-arms floor is known before the pricey reps launch.
Per-task counters tally pilot outcomes; once all of a task's pilot cells have
*scored* and none passed, the task is marked aborted and its remaining cells are
skipped with a log line. A pilot cell that never scores (run/API failure) leaves
the task inconclusive → no abort (conservative: run the full matrix).

Knobs (config.sh):
- `FLOOR_ABORT` (default `0`) — master switch.
- `FLOOR_PILOT_PER_COND` (default `1`) — reps per condition in the pilot.
  `1` → 2-run A/D pilot; `2` → 4-run pilot, fewer false aborts on borderline
  (~30%-pass) tasks at the cost of 2 extra runs before the decision.

`analyze.py` now lists **floored tasks** (no arm passed on the whole task) in the
diagnostics block; a thin `n` there marks a pilot-aborted task.

## Files touched

- `harness/config.sh` — `FLOOR_ABORT`, `FLOOR_PILOT_PER_COND` knobs
- `harness/drive.sh` — pilot/bulk cell split, both-arms floor detection + skip
- `harness/analyze.py` — floored-tasks diagnostic line

## What it invalidates

Nothing retroactively; run-discipline only, and off by default so existing round
scripts are unchanged. When enabled, floored tasks yield fewer rows than the full
matrix — analysis already reports per-cond *rates*, so uneven `n` is fine, and
the new diagnostic flags which tasks were cut short.
