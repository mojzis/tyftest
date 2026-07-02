# Significance test — tyf variant effect (dlt-110, opus)

**Date:** 2026-07-01
**Data:** `results/round2-opus.jsonl`, task `dlt-110`, conditions **A** (no tyf) vs
**D** (tyf + strong snippet). C and dlt-103 excluded (see below).
**Question:** does the tyf snippet produce a *statistically detectable* difference in
cost, tool usage, or context intake — not just a favourable point estimate?

This note is written to be lifted into a notebook: each analysis step maps to a cell,
and the statistical choices are justified inline so the reasoning survives the port.

---

## TL;DR

At n=10 paired reps, tyf (**D**) significantly reduces **context intake** but shows
**no detectable cost effect**.

| metric | A | D | D/A | mean Δ | 95% CI (Δ) | perm p | wilcox p |
|---|--:|--:|--:|--:|--:|--:|--:|
| **cost $** (primary) | 2.375 | 2.144 | 0.90 | −0.231 | [−0.65, +0.16] | 0.336 | 0.508 |
| tool calls | 43.3 | 38.1 | 0.88 | −5.25 | [−11.9, +0.8] | 0.176 | 0.221 |
| **Bash calls** | 27.2 | 21.1 | 0.78 | −6.05 | [−10.5, −1.5] | **0.043** | 0.041 |
| **bytes read** | 40.5k | 28.1k | 0.69 | −12.4k | [−18.8k, −6.2k] | **0.006** | 0.009 |
| input tok (cache) | 2.34M | 1.97M | 0.84 | −366k | [−835k, +72k] | 0.189 | 0.333 |
| output tok | 23.7k | 23.3k | 0.98 | −412 | [−5.3k, +3.7k] | 0.871 | 0.878 |

- **Cost — not significant** (p=0.336, CI crosses 0). The 10% saving is real-looking
  but n=10 cannot resolve it. Do **not** claim tyf is cheaper.
- **Bytes read — significant** (p=0.006), and it survives Holm correction across all
  six metrics (0.006 × 6 = 0.036 < 0.05). D reads ~31% fewer bytes; CI entirely below 0.
- **Bash calls — significant unadjusted** (p=0.043) but does **not** survive Holm
  (rank 2: 0.043 × 5 = 0.21). Suggestive only.
- **output tok — flat** (0.98): tyf's own calls do not inflate output.

**Finding:** tyf changes *how* the agent works (less filesystem flailing — fewer bytes
read, directionally fewer Bash/tool calls) more than *what it costs*. Consistent with
the "additive, not substitutive" result in `tyf-experiment-lessons.md`.

---

## 1. Design: why this is a *paired* test

A and D are **not** two independent groups. Each rep is the *same task on the same
repo checkout* run under both variants. So the right unit is the **within-rep
difference** `dᵢ = Dᵢ − Aᵢ`, not a two-sample comparison.

Pairing removes between-rep nuisance variance (some checkouts/tasks just run longer and
read more, regardless of variant). At n=10 that variance would otherwise swamp the
~10% effect. A paired test conditions it out and is materially more powerful here.

**Notebook cell 1 — load & filter:** read the JSONL, keep `task == "dlt-110"` and
`cond in {"A","D"}`.

## 2. Collapsing double-logged reps

Reps 1–3 were logged **twice** each (harness retries) → 13 raw rows per variant. To
keep one observation per experimental unit, **average the two logged runs** within each
(cond, rep) before differencing. Result: 10 clean A-values and 10 D-values, paired by
rep. (Sensitivity option: keep all 13 as independent — a robustness check, not the
primary analysis, because the doubles are not independent replicates.)

**Notebook cell 2 — collapse:** group by `(cond, rep)`, take the mean of each metric.

## 3. Metrics

Pulled per run from the harness jsonl:

- `cost_usd` — **primary endpoint** (pre-declared; everything else is exploratory).
- `tool_calls_total`, and the `tool_counts.Bash` sub-count (Bash is the navigation
  workhorse, so most sensitive to a locate-behaviour change).
- `bytes_read` — total bytes pulled into context (the intake proxy tyf should shrink).
- `input_tokens` (dominated by cache reads) and `output_tokens`.

Cost/token/byte metrics are **right-skewed and multiplicative**, so alongside the raw
difference we also track the **log-ratio** `ln(Dᵢ/Aᵢ)` and report `D/A`.

## 4. The tests (n=10, non-normal, paired)

Three procedures, primary + two cross-checks. Ten differences will not support a
normality assumption, so the *primary* test is distribution-free.

### 4a. Primary — exact paired permutation (sign-flip) test
Under H₀ (variant has no effect) each `dᵢ` is equally likely to carry a + or − sign.
Enumerate **all 2¹⁰ = 1024** sign assignments, recompute the mean each time, and set

    p = fraction of sign-flips whose |mean| ≥ |observed mean|.

Because n is small the enumeration is **exact** (no Monte-Carlo sampling), assumption-
free, and robust to the skew. This is the number to quote.

### 4b. Cross-check — Wilcoxon signed-rank
Rank-based paired test. Standard and familiar, but with n=10 and ties its p is coarse
(here via a normal-approximation z, two-sided). Used only to confirm the permutation
result isn't an artefact.

### 4c. (Optional) paired t-test
Fine as a *third* cross-check but **not** primary — 10 diffs can't justify normality.
Not run in the table above; add it in the notebook as a column if desired.

### 4d. Effect size + uncertainty — bootstrap CI
p-values alone are the wrong headline at this n. For each metric, **resample the 10
pairs with replacement 10,000×** and take the 2.5/97.5 percentiles of the mean
difference → a 95% CI. The CI (does it cross 0? how wide?) carries the actual message.

### 4e. Multiplicity
Six metrics tested. **Cost is the pre-declared primary endpoint**; the rest are
exploratory. Report raw p's, then apply **Holm** across the six for anything claimed as
a confirmed effect. Only **bytes read** survives Holm. Do not cherry-pick the smallest p.

## 5. Reproducibility

- Seed the bootstrap (`random.seed(0)`) so CIs are stable across runs.
- Permutation test is deterministic (full enumeration) — no seed needed.
- Exact script used to produce the table: see the inline python in the 2026-07-01
  analysis session; port target is `docs/learnings/tyf_analysis.py` /
  a `notebooks/tyf-significance.ipynb`.

## 6. Power / what it would take

Cost sits at D/A ≈ 0.90, p ≈ 0.34, with the paired-diff SD roughly the same magnitude
as the effect. Rough paired-power arithmetic puts detection of a ~10% cost effect at
**n ≈ 40–60 pairs** — 4–6× the current sample. Cheaper path to a defensible headline:
lead with **bytes read**, which is already clean and significant.

## 7. Scope caveats

- **dlt-110 only.** tyf fired zero times on dlt-103 (see `tyf-nonadoption-dlt103.md`),
  so a variant contrast there tests nothing. Adding it would only dilute.
- **C excluded** — this note is the A-vs-D (no-tyf vs strong-snippet) contrast.
- The effect is measured on a single task/repo; treat magnitudes as indicative, not
  transferable, until replicated on feast/dagster.

## 8. Notebook port checklist

1. cell 1 — load JSONL → dataframe, filter task/cond.
2. cell 2 — collapse (cond, rep) means → 10 paired rows.
3. cell 3 — per-metric paired diffs + log-ratios.
4. cell 4 — `perm_p(diffs)` exact enumeration.
5. cell 5 — Wilcoxon (and optional t-test) cross-checks.
6. cell 6 — bootstrap CI (seeded).
7. cell 7 — assemble results table + Holm adjustment.
8. cell 8 — CI forest plot per metric (visual headline).
