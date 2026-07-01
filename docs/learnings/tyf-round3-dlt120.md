# Round 3 — dlt-120 (opus): tyf efficiency story does NOT replicate

**Date:** 2026-07-01
**Data:** `results/round3-dlt120-opus-run2.jsonl` (canonical), conds **A** (no tyf) vs
**D** (tyf + strong snippet), 5 reps each, opus, dlt repo, task `dlt-120`
(JSON normalizer spurious-schema-update bug).

## The results file was conflated — split first

`results/round3-dlt120-opus.jsonl` originally had **20 lines = two back-to-back runs**.
Run 1 (lines 1–10) was truncated by the **4:40pm session limit**: 5 of its 10 reps are
empty/errored (`final_answer` = "You've hit your session limit …", `is_error:true`,
all-zero tool counts, `gate:"WARN_NO_TYF"`). Run 2 (lines 11–20) is a clean full grid.

Each run is a complete A1–5 / D1–5 block, so the split is a clean boundary:

```bash
head -10 round3-dlt120-opus.jsonl > round3-dlt120-opus-run1-capped.jsonl  # unusable
tail -n +11 round3-dlt120-opus.jsonl > round3-dlt120-opus-run2.jsonl      # canonical
```

## Results (run 2)

| metric | A (n=5) | D (n=5) | D/A | D-gated¹ (n=3) | Dg/A |
|---|--:|--:|--:|--:|--:|
| cost $ | 2.600 | 2.709 | 1.04 | 2.790 | 1.07 |
| turns/steps | 37.4 | 44.4 | 1.19 | 49.3 | 1.32 |
| tool calls | 36.4 | 43.4 | 1.19 | 48.3 | 1.33 |
| Bash | 24.2 | 27.6 | 1.14 | 27.3 | 1.13 |
| Read calls | 10.0 | 11.4 | 1.14 | 15.0 | 1.50 |
| bytes read | 66.9k | 65.0k | 0.97 | 54.1k | 0.81 |
| in_tok (cache) | 2.25M | 2.60M | 1.16 | 2.72M | 1.21 |
| out_tok | 30.1k | 28.3k | 0.94 | 30.1k | 1.00 |
| reads/edit² | 4.57 | 3.88 | 0.85 | 4.47 | 0.98 |
| distinct files read³ | 6.0 | 5.6 | 0.93 | 6.0 | 1.00 |
| read-not-edited³ | 4.4 | 3.8 | 0.86 | 4.0 | 0.91 |

¹ **D-gated** = the 3 D reps that actually fired tyf (D2/D3/D5). D1 and D4 were
`WARN_NO_TYF` (0 invocations) — non-adoption again, 2 of 5.
² **reads/edit** = `Read calls / max(Edit calls,1)` — intake-per-unit-of-work ratio, the
confound-normalizer from `tyf-experiment-lessons.md` §3. See `tyf-analysis-recipe.md`.
³ From introspect `session_stats` (distinct files, not call counts): `read-not-edited =
files_read − files_edited` = files opened but never modified (exploration/dead-end breadth).

## Finding

**dlt-120 does not replicate the round-2 (dlt-110) efficiency result.** Round 2 had D
~10% cheaper and reading ~31% fewer bytes (the only Holm-surviving effect —
`tyf-significance-test.md`). Here:

- **Cost flat / slightly up** (D/A 1.04); **D does ~19% *more* work** (turns, tool calls).
  Consistent with the round-2 "tyf is additive, not substitutive" lesson: tyf gets
  prepended onto unchanged navigation and *lengthens* the run rather than replacing steps.
- The round-2 intake signal only reappears in **gated D**: bytes read 0.81, read-not-edited
  ~0.86–0.91 — when tyf fires, the agent opens slightly fewer dead-end files. Small, and
  the churn (turns/Bash) moves the wrong way.
- The **reads/edit 0.85** looks like a D win but is an artifact of the two non-firing D
  runs; gated it's ≈1.0. Not a tyf effect.
- **Non-adoption persists** (D1, D4 never fired tyf). Always report gated separately.
- **n=5/cell → nothing is significant** (need ~10–15/cell). Quality a wash: A 3/5, D 3/5
  oracle_pass; D-gated 3/3.

**Takeaway:** the tyf efficiency win is task-dependent, not general. dlt-110 showed it;
dlt-120 doesn't — and where tyf fires without displacing the reflexive grep/read, it adds
cost. Reinforces `tyf-experiment-lessons.md` §1 and §4.
