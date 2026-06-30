# tyftest — does the `tyf` CLAUDE.md snippet earn its keep?

A controlled A/B/C experiment measuring whether the `tyf` CLAUDE.md snippet
(and the tyf binary itself) improves Claude Code task outcomes enough to justify
its permanent context cost.

- **Design / pre-registration:** `docs/tyf-experiment-protocol.md`
- **Construction & run mechanics:** `docs/tyf-experiment-repo-prep.md`
- **Tested tool commit:** `TOOL_VERSION.md` (the thing being judged is tyf's SHA)

## Conditions

| Cond | tyf binary on PATH | CLAUDE.md snippet |
|------|--------------------|-------------------|
| A | absent | no |
| B | present | no |
| C | present | yes |

`C−B` = value of the instruction lines. `C−A` = value of the whole package.

## Current scope

**Pilot:** repo `dlt-hub/dlt`, T2 reverted-PR edit tasks, 3 tasks × 3 conditions
× 3 reps = 27 headless runs. Held-out oracle tests (SWE-bench style): the agent
sees the pre-fix tree, never the verifier.

## Layout

```
docs/        pre-registration (read first)
harness/     all scripts (build / setup / mine / make / launder / run / score / drive)
holdout/     per-task record: prompt, solution.patch, oracle.patch, gold_files, manifest  [TRACKED]
results/     results.jsonl (one row per run) + pilot-notes.md                              [TRACKED]
bin/tyf      pinned binary                                   [gitignored, rebuild via harness]
repos/       pristine pinned clones                          [gitignored]
fixtures/    laundered A/B/C snapshots per task              [gitignored, regenerable]
runs/        per-run working dirs + transcripts             [gitignored]
```

## Reproduce

```bash
harness/build_tyf.sh          # build + pin tyf, record SHA
harness/setup_repo.sh         # clone+pin dlt, out-of-tree venv
harness/mine_tasks.sh         # list candidate reverted-PR bugfixes
harness/make_task.sh <FIX>    # build one task fixture (+ validity gate)
harness/launder.sh <task>     # de-leak + neutral CLAUDE.md + git re-init + ty check
harness/build_conditions.sh <task>   # snapshot A/B/C
harness/drive.sh              # run the 27-cell pilot -> results/results.jsonl
```

Set `DRY=1` to exercise the whole pipeline with a canned transcript at $0.

## Round 2 — opus, harder tasks, conditions A / C / D

After the round-1 pilot showed near-ceiling accuracy and low tyf adoption, round 2
raises difficulty and tests a stronger snippet, opus-only:

- **Conditions:** A (no tyf) · C (standard snippet) · D (**stronger** snippet,
  `harness/claude-snippet-strong.md`). B is dropped — in the pilot it never used tyf.
- **Tasks (harder, multi-file, offline):**
  - `dlt-103` — empty column that later becomes a child table is left in the parent
    schema as a partial column (schema + normalize internals; dummy destination).
  - `dlt-110` — empty-table materialization is wrong for multi-table resources
    (extract internals; duckdb).
- **Model:** opus only.

**Run it (outside the session — you control the spend):**

```bash
bash harness/run_opus_round.sh          # REPS=3 -> 2 tasks × {A,C,D} × 3 = 18 cells
REPS=5 bash harness/run_opus_round.sh   # more reps
```

Each opus cell ≈ $0.4–0.8 and a few minutes. Results → `results/round2-opus.jsonl`
(separate from the pilot). Read-out prints automatically, or rerun:
`python3 harness/analyze.py results/round2-opus.jsonl`. The script pre-flights
(tyf built, venv, duckdb, fixtures) and fails fast before spending anything.

**Key question D answers:** does stronger wording (D) raise tyf adoption and/or
outcomes vs the standard snippet (C)? The `ΔC-A` / `ΔD-A` columns and the per-cell
`tyf` counts in the read-out are where to look.
