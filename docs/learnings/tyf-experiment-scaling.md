# Scaling the tyf experiment — sizing, power, and variance control

How to run *enough* tests to get a real answer, and why the round-2 pilot (n=3)
couldn't. Companion to `tyf-experiment-lessons.md` (§3–4); this is the deep dive on N.

---

## 1. Why n = 3 was a dead end

A Mann–Whitney U on 3-vs-3 has a **minimum two-sided p of 0.10** — even if the two
arms are perfectly separated with zero overlap. So *no* 3×3 cell can reach p < 0.05,
regardless of how clean the effect is. Round 2 was structurally incapable of producing
a significant result; the "32 vs 46 KB" gap on dlt-110 is a direction, not a finding
(and the arms didn't even separate — A/rep2 = 29 KB sits inside D's range).

Rule of thumb for rank tests, two groups:

| n per arm | min achievable two-sided p |
|-----------|----------------------------|
| 3         | 0.10  (never significant)  |
| 4         | 0.029                      |
| 5         | 0.008                      |
| 6+        | < 0.01, room for overlap   |

**Floor: never run fewer than 5 reps/cell** if you intend to claim anything. 5 is the
bare minimum that *can* be significant; it tolerates near-zero overlap. Real power
(tolerating the overlap we actually see) needs more — see §3.

---

## 2. Know the variance before sizing N

The metric variance here is **not** clean Gaussian noise around a condition mean. It
has two parts:

1. **Baseline scatter** — within-condition CV of bytes/tokens ≈ **15–25%**.
2. **Trajectory-shape outliers** — fat tail from runs that *thrash* (A/rep3: 15 greps,
   47 KB) or do *extra verification* (D/rep1: long repro loop, 576 s). These swing a
   cell median more than the condition does.

Sizing off the baseline CV alone under-powers you, because the outliers dominate.
Two consequences:

- Use **medians + rank tests** (robust to the tail), not means + t-tests.
- **The biggest win is cutting the variance, not adding N** (see §4). Halving the CV
  is worth ~4× the reps.

---

## 3. How many reps for a real answer

Target: detect the effect size tyf would need to justify its context cost — call it a
**~20–30% reduction** in the primary metric (input tokens). Against a 15–25% CV with a
fat tail, rough power sizing:

| reps/cell | detects (80% power, rank test) | verdict |
|-----------|-------------------------------|---------|
| 3         | nothing (p-floor 0.10)        | ✗ pilot only |
| 5         | ~40%+ effect, only if near-zero overlap | weak |
| **10**    | ~25–30% effect                | **minimum credible** |
| 15        | ~20% effect, tolerates the tail | comfortable |
| 20+       | <15%, and supports subgroup cuts | if budget allows |

**Recommendation: 12–15 reps/cell.** This matches the pre-reg (§6: N ≥ 8–10) and buys
headroom for the outlier tail that the pilot revealed. Below 10 is not worth running.

---

## 4. Cut the variance — worth more than raw N

Reducing per-run variance raises power faster than adding reps. Levers, in order of
payoff:

1. **Control the work-size confound.** The expensive runs are the ones that made more
   edits/wrote more test files/thrashed grep — orthogonal to condition. Either:
   - hold the task tighter (constrain scope so every rep does ~the same work), or
   - **record `edits`, `writes`, `grep_count` as covariates** and analyze the primary
     metric *conditional on work done* (ANCOVA / regression), not the raw total.
2. **Pair within task.** Task is the dominant variance axis (dlt-103 ≈ 2× dlt-110 on
   every metric). Always compare A vs D **within the same task**, as paired deltas —
   never pool across tasks. Task as a blocking factor (or random effect) removes that
   variance from the contrast for free.
3. **Adherence-gate before analyzing.** A run where tyf never fired is not a treatment
   run. Drop / relabel `WARN_NO_TYF` runs (on dlt-103 that was *all* C/D runs). Analyze
   adherence-gated and raw separately.
4. **Drop C, run A vs D only.** The standard snippet is unreliable (C/rep1 didn't
   invoke tyf → collapsed to A). Spend the whole rep budget on the two clean arms.

---

## 5. Concrete next-round matrix

Adherence-screen candidate tasks first (only keep tasks where tyf demonstrably fires,
like dlt-110), then:

```
arms   : A, D                      (2)   — drop C
tasks  : 3–4 tyf-firing tasks      (3–4) — pre-screened for adoption
reps   : 12                        (12)
-------------------------------------------------
cells  : 2 × 3 × 12 = 72  … to  2 × 4 × 12 = 96 runs
```

Cost anchor from round 2 (opus): dlt-110 cell ≈ $2.5, dlt-103 cell ≈ $5. Budget
**~$250–500** for a 72–96-run opus round; less on sonnet. Keep the invisible wall-clock
`timeout` backstop (no visible budget cap — a cap induces token-fear and biases
behavior).

---

## 6. Analysis plan (decide before running)

- **Primary = mechanism metrics**, not just totals (totals are noise-dominated — see
  `tyf-experiment-lessons.md` §2): `locate_phase_len`, `grep_count`, `distinct_files`,
  `max_rereads`, `first_nav_tool`. These move iff tyf actually changes behavior.
- **Secondary = input_tokens / bytes_read**, analyzed *conditional on work-size covariate*.
- **Contrast:** paired A−D within task; report bootstrapped CIs on the paired delta,
  not p-values alone. With ≥3 tasks, a mixed model with task as random effect for the
  headline contrast.
- **Report direction + spread** at every N; only claim significance when the CI
  excludes zero and the arms actually separate.

---

## TL;DR

- **≥ 12 reps/cell** (n=3 literally cannot be significant; 5 is the absolute floor).
- **Cutting variance > adding N**: control the work-size confound, pair within task,
  adherence-gate, drop C.
- **A vs D only, on pre-screened tyf-firing tasks**, ~72–96 opus runs, ~$250–500.
- **Score mechanism metrics as primary**; treat token totals as covariate-adjusted
  secondary.
