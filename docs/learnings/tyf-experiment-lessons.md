# Lessons learned — tyf experiment (round 2, opus)

Applied notes from analyzing the 18 round-2 opus runs (`results/round2-opus.jsonl`,
sessions under `runs/dlt-{103,110}/{A,C,D}/rep*`). Read this before designing the
next round so we don't re-learn it the expensive way.

Conditions: **A** = no tyf. **C** = tyf + standard snippet. **D** = tyf + strong snippet.
tyf only ever fired on `dlt-110` (extract task); on `dlt-103` it was invoked **zero**
times in every condition.

---

## 1. The headline finding: tyf was *additive*, not *substitutive*

When the strong snippet did get tyf invoked (dlt-110 / D), tyf did **not replace**
the existing navigation — it was layered on top of an unchanged grep+read sequence.
Evidence from the per-run trajectory frames:

- **Every D run opens `tyf … tyf … grep … Read`.** Claude ran tyf and then grepped
  anyway, for the same symbol. No run swapped a grep for a tyf.
- **The locate phase got *longer*, not shorter.** Tool calls before the first Edit:
  A = 4–7, D = 8–9. tyf calls were prepended to the same work, adding round-trips.
- **The file footprint was identical across conditions.** A and D read the same core
  set (`extractors.py`, `extract.py`, `test_extract.py`, `schema.py`, `utils.py`) and
  both **re-read the hot files 2–4×** (A/rep2: extractors ×4; D/rep2: extractors ×3).
  tyf produced no "locate precisely, read once" behavior.

**Implication:** the mechanism tyf is supposed to provide (skip the grep-and-read
navigation) did not occur. Slightly lower byte/token totals in D are a second-order
effect of unchanged reads pulling marginally less text — not a changed strategy.

**The upstream question to fix or measure:** *why does Claude grep right after a
successful tyf call?* If the snippet can't suppress the reflexive grep, tyf cannot
save the navigation cost it exists to save. Solve this before scaling reps.

---

## 2. Totals lie; measure the *trajectory*, not the aggregate

`input_tokens` / `bytes_read` per run are dominated by **trajectory shape**, not by
condition. The expensive runs were:

- **grep-thrash** (A/rep3: 15 greps, pipeline test-files read 4× → 47 KB), and
- **repro-heavy** (D/rep1: long python-repro loop, 576 s) —

both orthogonal to whether tyf was present. So condition effects sit *underneath* the
run-to-run "how much work did this rep decide to do" noise, and any total-based
comparison will keep swinging on which arm happened to draw the thrash run.

**Log these mechanism metrics per run next time** (they move iff tyf actually helps;
totals don't):

| metric | what it catches |
|---|---|
| `locate_phase_len` | tool calls before first Edit — should *shrink* if tyf helps |
| `grep_count` | reflexive grep-after-tyf — should *drop* if tyf substitutes |
| `distinct_files` + `max_rereads` | "read once precisely" vs re-reading hot files |
| `first_nav_tool` | did the run *start* with tyf or with grep? |

The trajectory-frame view (glyph strip per run, first-Edit marker) surfaces all of
this at a glance; the byte total hides it. Emit frames for every run in the batch.

---

## 3. n = 3 cannot be significant — stop treating 3×3 gaps as results

A Mann–Whitney on 3-vs-3 has a **minimum possible two-sided p of 0.10**, even with
perfect separation. No 3×3 cell can clear p < 0.05 by construction. The dlt-110
"32 vs 46 KB" gap is a *direction*, not a result — and the arms don't even separate
(A/rep2 = 29 KB sits inside D's range). Report direction + spread; never a single
median as if it were an effect.

**Sizing for the real run:** within-condition CV of bytes/tokens is ~15–25% plus
fat-tailed thrash outliers. To detect a ~30% effect at 80% power you need roughly
**10–15 reps/cell**, which is what the pre-reg (§6, N ≥ 8–10) already said. More N
alone won't help if the work-size confound isn't controlled — record edits/writes as
a covariate and compare bytes *conditional on work done*, or hold the task tighter.

---

## 4. Only compare clean arms — drop contaminated cells

- **Drop C.** The standard snippet is unreliable: C/rep1 (dlt-110) never invoked tyf
  and collapsed to A behaviorally. Mixing tyf-used and tyf-unused runs under one label
  poisons the cell. **A vs D** is the only clean "tyf actually used" contrast.
- **Gate on adherence, then analyze.** Runs where the treatment didn't happen
  (`WARN_NO_TYF`) are not treatment runs. On dlt-103 *no* C/D run used tyf, so those
  cells measure snippet overhead only — and there the snippet *added* ~1 M tokens
  (~20%) for zero navigation benefit. Report adherence-gated and raw separately; don't
  average a no-op treatment into the effect.
- **Pick tasks where tyf actually fires.** dlt-103 taught us that on some tasks the
  model never reaches for tyf regardless of snippet strength. Pre-screen candidate
  tasks for tyf adoption before spending the rep budget.

---

## 5. Harness gotcha: `--setting-sources project` strips global CLAUDE.md

The runner passes `--setting-sources project`, so the operator's global
`~/.claude/CLAUDE.md` is ignored. This is correct for isolation, but it means
**behaviors driven by the global config do not reproduce in the harness.** Concretely:
the "read exact line-ranges with `sed` off a tyf position" pattern seen in real IRL
sessions does **not** appear here (11 trivial `sed -n` slices total, ~18 KB combined,
mostly in the *no-tyf* control, none following a tyf call). Neither the standard nor
strong snippet mentions sed/offset.

**Apply:** if a behavior you want to test lives in global config or is a learned
interactive habit, it must be written into the *condition snippet* (or the neutral
CLAUDE.md) explicitly, or it won't happen in-harness. Don't infer harness results back
onto IRL behavior that depends on stripped config.

---

## TL;DR for the next round

1. Measure **trajectory mechanism metrics** (locate-phase length, grep count, rereads),
   not just token/byte totals — totals are noise-dominated.
2. **A vs D only**, adherence-gated; drop C; pick tasks where tyf demonstrably fires.
3. **10–15 reps/cell**, with work-size (edits/writes) as a covariate.
4. The real target is behavioral: **kill the reflexive grep-after-tyf.** If the snippet
   can't, tyf can't pay for itself — and that's the finding, not a measurement bug.
5. Anything that depends on global CLAUDE.md must be baked into the snippet or it won't
   reproduce in-harness.
