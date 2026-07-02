# Round 4 — dlt-131 (opus): tyf front-loads navigation, cuts cost, and the efficiency story returns

**Date:** 2026-07-02
**Data:** `results/round4-dlt131-opus.jsonl`, conds **A** (no tyf) vs **D** (tyf +
strong snippet), 5 reps each, opus, dlt repo, task `dlt-131` (re-declaring a
resource's `primary_key`/`merge_key` accumulates the old key instead of
replacing it — stale key columns linger in the computed schema and at the
destination).
**Metrics source:** introspect DuckDB (turns/tokens/duration/tool order) + CLI
`cost_usd`. **Read `docs/changes/2026-07-02-round4-data-collection-issues.md`
first** — two rows are corrupt/confounded in the raw jsonl and this report uses
the corrected values throughout.

## Headline

| metric (corrected) | A (n=5) | D (n=5) | D/A |
|---|--:|--:|--:|
| **solve rate** (fail_to_pass) | 2/5 (A-rep2 = artifact → **2/4**) | **3/5** | — |
| cost $ (CLI, cumulative) | 9.20 | 6.49 | **0.71** |
| duration s | 1988 | 1566 | 0.79 |
| tool calls | 99.6 | 78.2 | 0.79 |
| Bash calls | 63.8 | 54.4 | 0.85 |
| Read calls | 9.4 | 7.0 | 0.74 |
| **grep (bash) calls** | 26.4 | 15.6 | **0.59** |
| Edits (churn) | 14.4 | 9.4 | 0.65 |
| output tokens | 81,646 | 61,904 | 0.76 |
| cache-read tokens | 10.29M | 7.12M | 0.69 |

Every efficiency dimension points the same way: **D is ~30% cheaper, edits ~35%
less, and greps ~40% less.** This is the opposite of round-3 (dlt-120), where D
cost *more* and did *more* tool calls (D/A cost 1.04). Same snippet, different
task → opposite efficiency sign. The effect is task-dependent, not a property of
the snippet alone.

Statistical caveat: cost difference is large (Cohen's d ≈ 1.25) but at n=5 the
permutation p = 0.11 — not significant. Solve rate p = 1.00 (noise). See
`tyf-significance-test.md`; ~13 reps/arm would power the cost effect.

## The mechanism — tyf changes the *first* navigation reflex

The cleanest, most reproducible finding, straight from the trajectory frames
(`harness/trajectory.py --glob '%runs/dlt-131/%'`):

- **All 5 A runs open navigation with `grep`** (`nav1=grep`).
- **All 5 D runs open navigation with `tyf`** (`nav1=tyf`).

tyf is a symbol-lookup CLI (`tyf show <sym>`, `tyf find <name>`, `tyf refs
<sym>`). When present, the model reaches for it *first* to jump to a definition,
instead of grepping the tree and reading around the hit. Every D session also
bootstraps it once (`which tyf && tyf --help`). The downstream effect is fewer
greps and fewer Reads — but note tyf does **not** eliminate grep: reflexive
grep-after-tyf is still visible (e.g. D-rep1 `T T b R R T g g g g`). It
front-loads and reduces navigation rather than replacing it.

## Within-D: tyf *dose* tracks success

| D rep | tyf calls | fail_to_pass | cost $ |
|---|--:|:--:|--:|
| rep3 | 1–2 | FAIL | 6.67 |
| rep2 | 2 | FAIL | 3.86 |
| rep1 | 4–5 | PASS | 7.17 |
| rep5 | 6 | PASS | 7.27 |
| rep4 | 7–8 | PASS | 7.43 |

Clean split at the threshold: the three D reps that used tyf ≥4× all solved it;
the two that barely touched it (essentially `--help` + one probe) both failed.
Unlike round-3, there was **no hard non-adoption** — all 5 D runs fired tyf at
least twice (`nav1=tyf` everywhere) — but low-dose D looks like baseline A. n=5,
so suggestive not significant; worth watching whether low-dose D fails resemble
A fails.

## Session-by-session

Diagnosis was **not** the differentiator — every run, both arms, correctly
identified "accumulate vs replace" and the two leak layers (computed schema +
destination/stored schema). Pass/fail came down to whether the fix reached the
destination-schema layer the oracle checks, and how much thrash it took.

**A-rep1 — PASS, $9.52, 115 tools, 25 edits.** Recognized the known bug and
*"ported the upstream fix (dlt PR #3431)"*. Correct, but the highest edit churn
in the set — the implement phase is a long `E … R … g … E` thrash (edit,
re-read, grep, edit again). Right answer, expensive route.

**A-rep2 — FAIL\*, $4.79, 74 tools.** **Grading artifact, not a model failure**
(see data-issues doc). Hit the `_storage` 0200 lock 6× — more than any run — and
its final answer is entirely about the lock blocking the autouse storage
fixture. Only run with `pass_to_pass=FAIL` / `regression_ok=false`: the
signature of pytest erroring on *every* test in a locked run dir, which is also
where `score.sh` grades. Its patch quality is unknown.

**A-rep3 — PASS, $10.04, 96 tools.** Longest locate phase in the set: **48 tool
calls before the first edit** (`nav1=grep`, 36 greps). Explored exhaustively,
then a relatively clean implement, then ran the full suite (1438 passed).
Correct but slow-to-commit.

**A-rep4 — FAIL, $13.24, 111 tools, 3506 s.** The expensive rabbit-hole and the
most A-flavored run: 0 tyf, most Bash (81), dove in early (first edit at tool
12), then over-engineered — a 3-part fix (`_merge_key` + a new
`_remove_key_from_columns` helper + `apply_hints` empty-clear + rewrote the
oracle test's own assertions) and reasoned itself into a "scope note" about
dlt's accumulate-don't-delete semantics. `p2p=PASS` (no regression) but
`f2p=FAIL` — wrong layer/behavior. **Also the run that tripped the usage-limit
backstop and resumed** (why the raw jsonl shows a bogus turns=9 / out_tok=4227;
true ≈113 turns / 114.7k tokens).

**A-rep5 — FAIL, $8.23, 102 tools, 20 edits.** Incomplete fix, second-highest
churn. `p2p=PASS`, `f2p=FAIL` — genuine.

**D-rep1 — PASS, $7.17, 91 tools, tyf×4–5.** `nav1=tyf`, two-layer fix
(computed + destination). Clean.

**D-rep2 — FAIL, $3.86, 51 tools, tyf×2.** Cheapest run in the whole set, but
low-dose tyf and shortest locate — a fast, incomplete fix. `p2p=PASS`.

**D-rep3 — FAIL, $6.67, 72 tools, tyf×1–2.** Low-dose; correct diagnosis,
incomplete at the destination layer. `p2p=PASS`.

**D-rep4 — PASS, $7.43, 91 tools, tyf×7–8.** Highest tyf dose; three-layer fix
(`_merge_key` + `apply_hints` empty-key retention + destination). Heavy tyf use
front-loaded (`. T T R T … T R T`).

**D-rep5 — PASS, $7.27, 86 tools, tyf×6.** `nav1=tyf`, two-layer fix, tight
locate. Clean.

## Trajectory frames (glyph strips)

`T`=tyf `g`=grep `R`=Read `E`=Edit `v`=pytest `p`=python-repro `.`=git
`b`=other-bash; `│`=first edit, `‖`=first pytest.

```
A/rep1  locate=23 grep=33 tyf=0  nav1=grep   → PASS, 25 edits (max churn)
A/rep2  locate=14 grep=18 tyf=0  nav1=grep   → FAIL* (storage-lock artifact)
A/rep3  locate=48 grep=36 tyf=0  nav1=grep   → PASS (longest explore)
A/rep4  locate=11 grep=24 tyf=0  nav1=grep   → FAIL (over-eng, resumed run)
A/rep5  locate=28 grep=21 tyf=0  nav1=grep   → FAIL
D/rep1  locate=23 grep=21 tyf=5  nav1=tyf    → PASS
D/rep2  locate=16 grep=11 tyf=2  nav1=tyf    → FAIL (low dose, cheapest)
D/rep3  locate=23 grep=11 tyf=2  nav1=tyf    → FAIL (low dose)
D/rep4  locate=27 grep=19 tyf=8  nav1=tyf    → PASS (high dose)
D/rep5  locate=29 grep=16 tyf=6  nav1=tyf    → PASS (high dose)
```

Two structural reads:
1. **locate-phase variance collapses under tyf.** A's pre-first-edit length
   ranges 11–48 (σ huge: dive-bomb rep4 vs 48-call rep3). D's is 16–29 — tyf
   gives a more consistent "look it up, then edit" rhythm.
2. **A's grep column is uniformly heavier** (18–36 vs D's 11–21). The snippet's
   whole footprint is visible as the missing greps.

## What this round adds to the arc

- **Efficiency effect is real but task-dependent.** dlt-131 gives D a clear
  ~30% cost/edit/grep win; dlt-120 (round 3) gave the opposite. The snippet's
  value depends on how much the task rewards precise symbol navigation. Don't
  generalize a single task's sign.
- **The robust, cross-run signal is behavioral, not outcome:** tyf
  deterministically flips the first-navigation reflex from grep→tyf and
  front-loads/reduces navigation. That replicates 5/5 here.
- **Solve-rate is not a usable endpoint at n=5** — one flipped run, and one of
  A's "fails" is a harness artifact.
- **Adoption improved vs round 3:** 0 hard non-adopters here (all `nav1=tyf`)
  vs 2/5 `WARN_NO_TYF` in round 3 — consistent with the strong-snippet rewrite
  (`docs/changes/2026-07-01-strong-snippet-rewrite.md`). But *low-dose* adoption
  (rep2/rep3) still behaves like baseline, so "fired tyf ≥1×" is too weak a bar;
  dose matters.

## To firm this up

1. Fix the two data bugs (resume-aware parse; `_storage` unlock in `score.sh`)
   and re-grade A-rep2 — it may move A to 3/5.
2. More reps (~13/arm) to power the cost effect, or switch to the
   lower-variance endpoints (tool-count, grep-count) that separate the arms more
   cleanly than dollars.
3. Test whether tyf *dose* (not just presence) predicts success across tasks —
   the within-D split here is the most interesting lead.
