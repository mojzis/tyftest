# Pilot read-out (directional only — N=3, debugging + variance, not CIs)

> Tested tyf commit: `cda1468` (v0.4.0). Model: `claude-sonnet-5`.
> Repo: `dlt-hub/dlt` @ `0955489a3` (1.28.1). 27 runs, randomized order.
> Reproduce the table: `python3 harness/analyze.py`.

## Outcomes

- **pass@1: A 9/9, B 7/9, C 8/9.** Condition A (no tyf) is already at ceiling.
- The B/C accuracy dip is **entirely dlt-003** (retry): A 3/3, B 1/3, C 2/3.
  Almost certainly retry-test timing variance, not a tyf effect — flagged for
  inspection, not treated as signal.
- **0 non-converged, 0 regressions (pass_to_pass all green), 0 ty-degraded.**

## The headline: tyf adoption is low even when offered

- Of 9 **C** cells (snippet present), only **dlt-002/C** invoked tyf at all.
  dlt-001/C (3/3 reps) and dlt-003/C (2/3 reps) ignored the snippet and used
  Read/Grep.
- **B** cells never invoke tyf — expected: no snippet tells the agent it exists.
  This is the H2 picture: the binary alone changes nothing; the instruction
  lines are the only lever, and even they don't reliably fire on these tasks.
- Gate note: the harness flags every B-no-tyf cell as `WARN_NO_TYF`, but for
  condition B that is the *predicted* behavior, not an error. Only **C-no-tyf**
  is a meaningful adherence miss. (analyze.py lumps them; read accordingly.)

## Tokens

No consistent tyf signal. dlt-001 C/B medians sit ~300k input tokens below A,
but tyf was **not invoked** in those C cells — so that gap is variance, not tyf.
dlt-002/C (the one cell that used tyf) was *not* cheaper than A/B.

## Honest conclusion (pilot)

On easy, well-localized single-file bugs, sonnet fixes them without tyf, and the
snippet does not reliably trigger tyf use. This is the **null** the
pre-registration said to report. To actually test tyf's value you need tasks
where navigation dominates — many call sites, project-wide rename, "find every
caller of X" — and larger N. The current 3 tasks are not discriminative.

## Harness caveats surfaced by the run

- `test_tampered` = 22/27: agents routinely add their own repro tests. Harmless
  — scoring restores `tests/` and applies the held-out oracle — but worth knowing.
- Near-ceiling accuracy means the pilot validated the *machinery*, not tyf's
  value. Next iteration: harder T2 + dedicated T1 navigation-accuracy tasks.
