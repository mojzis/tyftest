# 2026-07-02 — per-invocation results files (stamped, merge explicitly)

## What changed

Resuming a round after a usage-limit abort meant re-running the round script,
which appended a second full matrix into the SAME results jsonl — duplicate
cells with no way to tell attempts apart. Now every invocation gets its own
log:

- **`run_dlt140_opus.sh`**: `OUT` and `RUN_TAG` carry the script's start stamp
  (`results/round5-dlt140-opus.<YYYYmmdd-HHMMSS>.jsonl`,
  `RUN_TAG=round5-dlt140-<stamp>`). Session names therefore stay unique across
  attempts, so introspect joins are unambiguous.
- **`drive.sh`**: the ad-hoc default `OUT` is likewise stamped
  (`results/adhoc.<stamp>.jsonl`) instead of a shared `results/results.jsonl`.
- **`analyze.py`**: accepts multiple jsonl paths and concatenates them —
  merging attempts is an explicit `analyze.py results/round5-dlt140-opus.*.jsonl`,
  never an implicit append.

## Files touched

`harness/run_dlt140_opus.sh`, `harness/drive.sh`, `harness/analyze.py`.

## What it invalidates

Nothing. Existing single-file results still analyze the same way (analyze.py's
single-path usage unchanged). Older round scripts (dlt-110/120/131 rounds) keep
their fixed OUT names; they are historical — apply the stamp pattern if reused.
When merging multiple attempt files, dedup/cell-selection is still a manual
step (e.g. drop the incomplete attempt's rows or keep first N reps per cell).
