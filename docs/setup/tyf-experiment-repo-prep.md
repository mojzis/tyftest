# tyf Experiment — Repo Prep, Task Construction & Clean-Reset Runbook

Operational mechanics for the reverted-PR / held-out-test design. Goal: the agent sees a **normal-looking repo at the pre-fix state**, the verifying test is **never in its tree**, and every run starts from a **byte-identical pristine fixture**.

---

## 0. Mental model — what the agent sees vs. what's held out

For each task, the fix commit (`FIX`) touched **source files** (the solution) and **test files** (the verifier). Split them:

- **Agent sees:** working tree at `FIX~1` (pre-fix source), laundered and de-leaked. Never sees the solution patch or the verifier.
- **You hold aside (outside the repo):**
  - `solution.patch` — used only to compute the *gold file set* for early-read precision. Never applied to the agent's tree.
  - `oracle.patch` — the test diff. Applied **at scoring time only**.
- **Oracle test** = SWE-bench `FAIL_TO_PASS`: fails on the buggy tree, passes once the bug is fixed.
- **Regression set** = `PASS_TO_PASS`: existing tests that must stay green.

---

## 1. One-time per repo

```bash
# pin and clone pristine (keep this untouched as the source of truth)
git clone <url> repo-src && cd repo-src
git checkout <PIN_SHA>          # record this SHA in every result row
```

- **Keep the Python env OUTSIDE the repo tree** (separate `.venv`, or rely on uv's shared cache). If `.venv` lives in-tree, the per-run reset deletes it and reinstall dominates your runtime.
- Resolve deps once against a warm uv cache so per-run setup is seconds, not minutes.

---

## 2. Identify candidate tasks (mine reverted PRs)

```bash
CORE=<core_dir>   # dlt/  |  sdk/python/feast/  |  python_modules/dagster/dagster/_core/

# bugfix commits in core
git log --oneline --no-merges -- "$CORE" | grep -iE 'fix|bug|regression'

# keep ones that changed BOTH source and a test
git show --stat <FIX>
git show <FIX> --name-only --pretty=format: | grep -E '/tests?/|test_'      # test files
git show <FIX> --name-only --pretty=format: | grep '\.py$' | grep -vE '/tests?/|test_'  # source files
```

Keep a candidate only if it has ≥1 test file **and** ≥1 source file. Aim for 10–15 viable candidates/repo (you'll drop some).

---

## 3. Construct one task fixture

```bash
SRC=$(git show <FIX> --name-only --pretty=format: | grep '\.py$' | grep -vE '/tests?/|test_')
TST=$(git show <FIX> --name-only --pretty=format: | grep -E '/tests?/|test_')

# the solution (NEVER shown to the agent; only for the gold file set)
git diff <FIX>~1 <FIX> -- $SRC > holdout/<task>/solution.patch
# the verifier (applied only at scoring)
git diff <FIX>~1 <FIX> -- $TST > holdout/<task>/oracle.patch

# gold file set for early-read precision = the source files in the solution
printf '%s\n' $SRC > holdout/<task>/gold_files.txt

# pre-fix tree = what the agent will start from
git checkout <FIX>~1
```

**Validity gate (do this now, once):**
- Pre-fix tree + `oracle.patch` applied → oracle test **FAILS** (bug is present). If it passes, the task is invalid — discard.
- `FIX` tree → oracle test **PASSES** (oracle is correct).
- Record the exact oracle test id(s) (`path::test_name`) and a `PASS_TO_PASS` subset (a handful of nearby existing tests).

**Prompt** = the original issue/PR *problem description only* — symptom, repro, expected behavior. No solution, no file hints, no rubric language. Phrase as an ordinary dev/user report.

---

## 4. Launder & de-leak the agent-visible tree

Run on the pre-fix working copy **before** snapshotting.

**De-leak (strip anything that reveals the answer):**
```bash
# issue refs, "fixed/workaround/regression" near the task area
grep -rInE 'fixe?[ds]|work[- ]?around|regression|issue ?#?[0-9]+|#[0-9]{3,}' "$CORE" tests/
# changelogs / release notes / news
find . -maxdepth 3 -iregex '.*\(changelog\|history\|news\|release\).*'
```
- Neutralize/remove comments, docstrings, changelog entries, and **other tests/fixtures** that encode the fixed behavior.
- Confirm the oracle's fixed assertions are **not present anywhere** in the agent tree (pre-fix tests are fine; they lack the fix).

**Keep the repo's own `CLAUDE.md` verbatim (the within-project baseline):**
- The experiment is a within-project **A-vs-D** contrast, so the repo's real
  onboarding file *is* the baseline — do **not** replace it with a neutral stub.
- A/B get it verbatim; C/D are the same file **+ the tyf snippet appended** (see §5).
- Any uv/make guidance the file carries hits A and D symmetrically, so it does
  not confound the snippet contrast. Fall back to the neutral stub only if the
  repo ships no `CLAUDE.md` at all.

**Launder git (kills `git log` mining; absence of git is itself a tell):**
```bash
rm -rf .git
git init -q && git add -A
GIT_AUTHOR_DATE="2025-09-01T12:00:00" GIT_COMMITTER_DATE="2025-09-01T12:00:00" \
  git -c user.name=dev -c user.email=dev@example.com commit -qm "Initial import"
```
Now `git log` shows one neutral commit — no revert, no fix, no issue numbers.

**Pre-flight ty:**
```bash
ty check $SRC    # record: resolves clean (tyf-working) or unresolved imports (tyf-degraded)
```
Label the task; degraded tasks are reported separately, not discarded silently.

---

## 5. Build the three condition fixtures

From the laundered tree, make three snapshots:

| Cond | tyf binary on PATH | `.claude/settings.json` allow | CLAUDE.md |
|------|--------------------|-------------------------------|-----------|
| A | absent | — | repo CLAUDE.md verbatim, no snippet |
| B | present | `Bash(tyf:*)` | repo CLAUDE.md verbatim, no snippet |
| C | present | `Bash(tyf:*)` | repo CLAUDE.md **+ standard tyf snippet** |
| D | present | `Bash(tyf:*)` | repo CLAUDE.md **+ strong tyf snippet** |

- The `Bash(tyf:*)` allow in `.claude/settings.json` is **mandatory for B/C headless** — without it tyf won't execute and C silently collapses to B.
- Snapshot each as a read-only reference: `fixtures/<task>/<cond>/`.

---

## 6. Per-run clean reset (the core loop)

Never reuse a dirtied directory — the agent edits files, may run git, and state bleeds across runs. **Copy fresh every run:**

```bash
RUN=runs/<task>/<cond>/rep<k>
rm -rf "$RUN" && cp -a "fixtures/<task>/<cond>/" "$RUN"
# point env at the out-of-tree venv / warm uv cache (no reinstall)

# tyf daemon: hold warm/cold policy constant across ALL runs (B/C only)
tyf daemon restart    # new run dir = new workspace; restart keeps state clean & policy fixed

# run headless, FRESH session (no --resume), with a turn cap
claude -p "$(cat holdout/<task>/prompt.txt)" --output-format json > "$RUN/transcript.json"
```

- **Turn cap:** required, but record cap-hits as a separate *failure-to-converge* outcome — do **not** fold a capped run's tokens into the median.
- Cheaper alternative to `cp -a`: `git reset --hard && git clean -fd` (note: **no `-x`**, or you delete the venv). Fresh copy is more reliable; reset is faster if the env is fully out-of-tree.

---

## 7. Score (after the agent finishes)

```bash
# 1. restore tests to pristine so any agent test-tampering can't affect the oracle
cp -a "fixtures/<task>/<cond>/tests" "$RUN/tests"   # or git checkout -- tests/
# 2. apply the held-out verifier and run it
git -C "$RUN" apply /abs/holdout/<task>/oracle.patch
pytest "$RUN/<oracle_test_id>" -q          # FAIL_TO_PASS  -> pass@1
pytest "$RUN/<pass_to_pass...>" -q         # PASS_TO_PASS  -> regression check
```

- Flag (don't auto-fail) runs where the agent edited test files — it's a signal worth inspecting.
- Parse `transcript.json` for trajectory metrics: reads vs `gold_files.txt` (early-read precision, wasted_reads), turns-to-first-correct-edit, backtracks, tokens.

---

## 8. Verification gates — assert BEFORE a run counts

- **C/B:** transcript contains ≥1 *successful* `tyf` invocation (else C degraded to B → exclude or relabel).
- **ty status** recorded (working / degraded).
- **Leak grep** on the fixture returned clean (no issue refs / changelog / fixed-comment in the task area).
- **Oracle validity** confirmed at construction (fails pre-fix, passes post-fix).
- Run used a **fresh session** and the **constant** daemon policy.

---

## 9. Per-task manifest (store one per task)

```yaml
task_id:        dlt-001
repo:           dlt-hub/dlt
pin_sha:        <PIN_SHA>
fix_sha:        <FIX>
prompt_file:    holdout/dlt-001/prompt.txt
gold_files:     [dlt/pipeline/pipeline.py, ...]      # from solution.patch
oracle_patch:   holdout/dlt-001/oracle.patch
oracle_tests:   ["tests/.../test_x.py::test_y"]      # FAIL_TO_PASS
pass_to_pass:   ["tests/.../test_z.py::test_w"]
ty_status:      working            # working | degraded
```

Freeze the manifest set, commit it, **then** run. No edits to tasks after the first run.
