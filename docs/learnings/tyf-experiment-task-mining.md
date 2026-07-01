# Task mining & selection — learnings (reuse for feast, dagster, …)

How tasks were actually found and filtered for the dlt pilot + round 2. This is
the field guide: what to grep for, what to keep, what to throw away, and the traps
that cost time. Mechanics live in `../setup/tyf-experiment-repo-prep.md`; this is the
judgement layer on top.

> Rule of thumb: **construct ~2× the tasks you need.** Roughly half get dropped at
> the validity gate or for leakage/infra. For 3 good tasks, mine ~8 candidates.

---

## 0. Per-repo setup facts to pin first

| Repo | core dir (`REPO_CORE`) | default offline destination | test stack source |
|------|------------------------|-----------------------------|-------------------|
| dlt  | `dlt/` | `dummy` (in-memory) and `duckdb` (embedded) | PEP-735 `dependency-groups` → `dev` |
| feast | `sdk/python/feast/` | (find the in-memory/local provider) | check pyproject / setup.cfg |
| dagster | `python_modules/dagster/dagster/_core/` | (find in-process executor) | check setup.py extras |

Pin these before mining: core dir, **what counts as an offline run** for that
project, and **how its pinned test deps install**. Getting the test stack right
(pinned, not latest) is non-negotiable — see §6.

---

## 1. Mine: bugfix commits that touch BOTH source and a test

`harness/mine_tasks.sh` is the workhorse:

```bash
git log --oneline --no-merges -n 300 -- "$CORE" \
  | grep -iE 'fix|bug|regression|incorrect|broken|raise|error|crash'
# then keep only commits that changed >=1 source .py AND >=1 test .py
```

The test file is what makes the task scorable (it becomes the held-out oracle).
No test touched → no oracle → skip. Widen the subject grep
(`incorrect|wrong|raise|crash`) — many real fixes don't say "fix" in the title.

---

## 2. The selection filters, in priority order

Apply these **before** writing any prompt — they kill most candidates cheaply.

### 2.1 Offline-testable (the #1 filter)
The oracle test must run with **no external service**. Decide per project what's
allowed. For dlt: `dummy` destination (in-memory) and `duckdb` (embedded, no
server) are **offline**; Postgres/Snowflake/BigQuery/Databricks/Athena/S3/mssql
are **not**.

Cheap pre-check — grep the commit's test files for infra imports/markers:
```bash
git show <FIX>:<test_file> | grep -iE \
  'import (duckdb|boto3|moto|psycopg|docker|snowflake|pyodbc)|create_engine|@pytest.mark.*(destination|postgres|essential)'
```
But imports lie both ways. **The real arbiter is the validity gate** (§4) — it
runs the test. If a "harder" task you like needs an embedded lib (duckdb), just
install that lib into the venv; that's still offline. Don't install a server.

Oracle-location heuristic (dlt-specific, generalizes): prefer tests under
`tests/common/`, `tests/extract/`, `tests/normalize/` (unit-level). Tests under
`tests/load/` almost always need a real destination — avoid. `tests/pipeline/`
is fine **if** the test uses `dummy`/`duckdb` (read the `dlt.pipeline(...,
destination=...)` line to check).

### 2.2 Single-concern commit (avoid "bundled" fixes)
Read the commit body. If it lists several unrelated changes —
> *propagates dataset_name … + retries rename on windows + uses spawn + adds basic types*

— **drop it.** Two real failures (`dlt-101`, `dlt-106`) came from bundled
commits: the oracle test depended on changes *outside* the clean source patch, so
"pre-fix + solution.patch + oracle" still failed the validity gate (gate 2). A
focused commit ("fix X; util for X; test for X") is what you want.

### 2.3 Bug, not feature (leak-proof prompt must exist)
If the fix adds an opt-in flag/feature (e.g. dlt's `return_validated_models`),
the only honest prompt names the feature → leaks the solution. Skip. Keep fixes
where you can describe the **symptom** (wrong output, stray characters, lingering
state) without naming the mechanism.

### 2.4 Right-sized difficulty
- Pilot/easy: single source file, obvious locality (round 1: time, coercion, retry).
- "Harder, not navigation-specific": 2–6 source files across modules, non-obvious
  fix, but still a **focused bug** (round 2: dlt-103 schema/normalize, dlt-110
  extract). Multi-file is what gives `tyf` something to navigate — without making
  the task artificially a navigation puzzle.

---

## 3. Construct, de-leak, build conditions
`make_task.sh → launder.sh → build_conditions.sh` (see repo-prep doc). Watch for
two `make_task` quirks observed on dlt:
- **Misclassified files:** a test *helper* under `tests/…/custom_normalizers.py`
  has no `test_` prefix, so the source/test split put it in SOURCE. Harmless for
  scoring but check `gold_files.txt` looks like real source.
- **Wrong oracle file in the suggestion:** the suggested test function may live in
  a *different* file than `make_task` guessed. Always confirm with
  `git show <FIX>:<path> | grep -n 'def <test_name>'` before writing
  `oracle_tests.txt` as `path::name`.

---

## 4. The validity gate is the real filter (`harness/validate.sh`)
A task only counts if **all three** hold:
1. **gate 1** — pre-fix tree + `oracle.patch` → oracle test **FAILS** (bug reproduced).
2. **gate 2** — pre-fix + `solution.patch` + `oracle.patch` → **PASSES** (the fix
   is fully captured in the source patch; if not, it's a bundled commit → drop).
3. **gate 3** — pre-fix + `oracle.patch` + `pass_to_pass` → **PASSES** (regression
   baseline is fix-independent).

Run it before committing the task. Don't hand-wave any gate — gate 2 is exactly
what caught the bundled commits.

---

## 5. `pass_to_pass` contamination (subtle, cost real time)
`PASS_TO_PASS` tests are run **after `oracle.patch` is applied**. If the
oracle.patch *modifies an existing test* (not just adds one), that test now
encodes the fix and will fail on an unfixed tree — it behaves like FAIL_TO_PASS,
not a regression check. **Never pick a `pass_to_pass` test that the oracle.patch
touches.** Auto-pick a neighbor that is *not* in the patch:
```bash
mod=$(grep -oE 'test_[a-zA-Z0-9_]+' holdout/<t>/oracle.patch | sort -u)
grep -oE '^def (test_[a-z0-9_]+)' <oracle_file> | awk '{print $2}' \
  | grep -vxF "$oracle_name" | grep -vxF $mod | head -1
```
gate 3 (which applies the oracle first) will flag contamination as `BAD`.

---

## 6. Environment gotchas that masquerade as task problems
These produced false "degraded"/"invalid" signals until fixed:

- **Point `ty`/`tyf` at the project venv.** Without `VIRTUAL_ENV` set, ty resolved
  against an *unrelated* venv on the machine and reported bogus
  `unresolved-import` → false `ty_status=degraded`. Set `VIRTUAL_ENV=$VENV` for
  every ty/tyf call.
- **Platform-optional imports aren't degradation.** A single `win_precise_time`
  (Windows-only) unresolved import shouldn't label a task tyf-degraded; filter a
  small allowlist (`launder.sh` `OPTIONAL_MODS`).
- **Install the repo's *pinned* test stack, not latest.** Latest pytest 9 broke
  `pytest-cases`; dlt pins `pytest<8`. Use the project's `dev`/test dependency
  group.
- **`import <pkg>` may read its own metadata at import** (dlt's `version.py` calls
  `importlib.metadata.version("dlt")`). So the package must be *installed*, but to
  test the agent's edits you must install it **editable against the per-run copy**
  (`install_editable` in `config.sh`) — not the pristine clone.
- **Keep the venv out of the repo tree**, or per-run `cp -a`/reset nukes it and
  reinstall dominates runtime.

---

## 7. Writing the prompt (symptom only)
- Describe the **observable symptom** + a minimal **repro shape** + the **expected**
  behavior. No file paths, no function names that reveal the fix, no rubric wording.
- Naming an *observable* internal artifact is OK (e.g. "a stray `seen-null-first`
  marker shows in the exported schema") — that's the symptom. Naming the *solution*
  (which strptime codes, which util to add, which config key) is not.
- Phrase it like a dev/user bug report, because that's the realistic input and it
  avoids steering the agent toward a specific tool.

---

## 8. Quick checklist per candidate
```
[ ] commit touches >=1 source AND >=1 test in core
[ ] single-concern (commit body isn't a grab-bag)
[ ] it's a bug, not an opt-in feature (leak-proof prompt exists)
[ ] oracle test is offline (dummy/embedded; no server)  ← verify by RUNNING it
[ ] oracle file/name confirmed via `git show <FIX>:<path>`
[ ] pass_to_pass neighbor NOT modified by oracle.patch
[ ] validate.sh: gate1 FAIL, gate2 PASS, gate3 PASS  → VALID
[ ] leak grep: oracle test name absent from the agent fixture
```
