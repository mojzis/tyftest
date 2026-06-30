# Experiment: Does the `tyf` CLAUDE.md snippet earn its keep?

**Status:** pre-registration draft. Fill the bracketed blanks, freeze, commit, *then* run.
**Core claim under test:** the `tyf` setup (tool + CLAUDE.md instructions) improves Claude Code (CC) task outcomes by enough to justify the permanent context cost of the snippet — measured across a *realistic* task mix, not a navigation-only one.

---

## 1. Hypotheses (state direction before running)

- **H1 (whole package):** Condition C beats Condition A on accuracy and/or input tokens, with the gap widening as repo size grows.
- **H2 (the literal challenge):** Condition C beats Condition B — i.e. the *instruction lines* add value beyond merely having the binary installed.
- **H3 (no harm):** On tyf-irrelevant tasks (T3), C is not meaningfully worse than A (the snippet's fixed overhead is small).
- **Null we must be willing to report:** on small repos, or under tyf-degraded environments, C ≤ A. If true, say so.

---

## 2. Conditions

| ID | tyf binary | `Bash(tyf:*)` allowed | CLAUDE.md snippet |
|----|-----------|----------------------|-------------------|
| A  | absent    | n/a                  | no                |
| B  | present   | yes                  | **no**            |
| C  | present   | yes                  | **yes**           |

- **C − B** = marginal value of the instruction lines (the literal "worth the extra lines" question).
- **C − A** = value of the whole package.
- If **B ≈ A** behaviorally (CC never invokes tyf without the snippet), that is a *result*: the lines are doing the work. Record it explicitly.

---

## 3. Factors

### 3.1 Repo size (real, pinned-commit OSS)
| Tier | Target LOC | Repo (pin a commit) | `ty check` env status |
|------|-----------|---------------------|-----------------------|
| Small | ~5k   | [repo @ sha] | [resolves clean? Y/N] |
| Medium | ~50k | [repo @ sha] | [Y/N] |
| Large | ~200k+ | [repo @ sha] | [Y/N] |

- **Pre-flight each repo with `ty check`.** Label every run *tyf-working* or *tyf-degraded* (unresolved imports → empty navigation). Do not mix silently.
- Pick repos you don't control and didn't tune for. Bonus credibility: let the challenger pick one.

### 3.2 Task type (must include all of T1–T3)
- **T1 — navigation / comprehension** (tyf home turf): "What is the exact signature of `X`?" / "List every caller of `Y`." / "What public methods does `Z` expose?"
- **T2 — edit requiring navigation:** "Add param `p` to `X` and update all call sites." / "Rename `Y` project-wide." (Score with the repo's own test suite where possible.)
- **T3 — tyf-irrelevant** (overhead control): edit a config string, fix a regex, modify a non-Python file, locate a TODO. The snippet is pure cost here.
- **T4 — trap (optional):** symbols ty can't see (getattr/metaclass/runtime-generated). Tests graceful fallback vs being misled.

Minimum ~4 tasks per type per repo. **Write tasks before deciding which condition you hope wins.**

---

## 4. Metrics (pre-register; do not add post-hoc)

**Primary**
- `success` — blind-graded against ground truth (binary or 0–3 rubric). Accuracy dominates; a cheaper wrong answer is a loss, not a win.
- `input_tokens` — total prompt tokens consumed for the task.

**Secondary**
- `tool_calls` total, and broken out: `Read`, `Grep`, `Glob`, `Bash(tyf)`, other.
- `bytes_read` (sum of Read tool output).
- `turns`, `wall_clock_s`, `output_tokens`, `cost_usd`.

**Adherence (B/C only)**
- `tyf_invocations` per task. Note: adherence is diagnostic, **not** an outcome. "CC used tyf" ≠ "tyf helped."

---

## 5. Ground truth & grading

- For every task, hand-author the correct answer **before** any run (signature text, exact caller set, file:line, or the test-suite pass criterion for edits).
- **Blind grading:** export all final answers, strip condition/repo labels, shuffle, grade against the rubric. Grader should not be able to infer the condition.

---

## 6. Run discipline (kills the "you fooled yourself" objection)

- **N ≥ 8–10 reps** per (repo × condition × task) cell. Report **median + IQR**, never a single run.
- **Fresh session per run** — no `--resume`, clean git worktree each run, restore repo state between runs.
- **Pin the model version string**; record it in every result row.
- **Randomize run order** across conditions (avoid all-A-then-all-C drift / rate-limit artifacts).
- **Daemon state:** decide and document — warm the tyf daemon before timed runs (steady-state, realistic) OR measure cold (one-time penalty). Don't let it vary run-to-run.
- **Pilot first:** 1 repo × 3 conditions × 3 tasks × 3 reps. Debug the harness, estimate variance, then size N for the full matrix.

---

## 7. Harness (spec — hand this to CC to implement)

Build a headless runner that, for each `(repo, condition, task, rep)`:

1. Checks out the pinned repo at a clean state (fresh worktree or `git reset --hard && git clean -fdx`).
2. Applies the condition: install/remove the `tyf` snippet in `CLAUDE.md`; write/remove `.claude/settings.json` `Bash(tyf:*)` allow; ensure tyf binary present/absent per condition.
3. (B/C, warm mode) pre-warms the daemon with one throwaway `tyf` call.
4. Runs the task headless and captures the full transcript:
   `claude -p "<task prompt>" --output-format json`
5. Parses the transcript JSON for: per-tool `tool_use` counts, Read byte totals, input/output token usage, turn count; extracts the final answer text.
6. Writes one row to a results table: all factor columns + all metrics + model string + tyf/degraded label.
7. Tears down and restores repo state.

Outputs: one tidy CSV/JSONL, one row per run. (Let CC write the actual script — keep it dependency-light.)

---

## 8. Analysis plan (decide before seeing data)

- Per cell: median + IQR for each metric.
- **C vs B** and **C vs A:** pair by `(repo, task)`; report effect sizes with bootstrapped CIs. With small N, report direction + spread — do **not** over-claim significance.
- **Scaling check:** plot each metric against repo size; the H1 prediction is a widening gap.
- **Cost accounting for the challenge:** `snippet_token_cost × turns` (fixed overhead) vs tokens saved, computed **per task type**, then weighted by *your* real task distribution → net expected value. This single number is the honest answer to "worth the extra lines."
- **Degraded-mode sub-analysis:** report tyf-working and tyf-degraded runs separately. If degraded kills the win, that's an adoption caveat, not a measurement bug.

---

## 9. Threats to validity (acknowledge up front)

- **Task selection bias** — mitigated by pre-registration + challenger-approved task list + mandatory T3.
- **Non-determinism** — mitigated by N, medians, randomized order.
- **Experimenter-blind grading** — mitigated by label stripping + pre-labeled ground truth.
- **Environment confound** — `ty` failing to resolve a repo is real-world; labeled, not hidden.
- **Prompt-cache / order effects** — fresh sessions + randomized order.
- **Generalization** — results are conditional on the chosen repos, model version, and task mix. State the scope; don't extrapolate past it.

---

## 10. Minimum credible version (if time-boxed)

2 repos (1 medium, 1 large) × 3 conditions × 12 tasks (4× T1/T2/T3) × 5 reps = 360 headless runs, pre-registered task list approved by the challenger, blind-graded. Underpowered for tight CIs but defensible as directional — and far more than "I ran it a few times and it felt faster."
