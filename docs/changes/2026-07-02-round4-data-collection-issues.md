# 2026-07-02 — Round-4 (dlt-131 opus) data-collection issues

Cross-checking `results/round4-dlt131-opus.jsonl` against the introspect DuckDB
(authoritative: it reads the full transcript, not just the terminal `result`
event) surfaced three issues. Two corrupt specific rows; one is a scoring
confound that can flip a pass/fail. Recording them so later rounds don't average
over bad cells or over-read the 2/5-vs-3/5 headline.

## Issue 1 — resumed runs report only the final segment's `turns`/token counts

**Row affected:** `A-rep4` (`a1c93696-…`).

`parse_transcript.py` walks the transcript and keeps the **last** `result`
event (`result = ev` overwrites), then reads `num_turns` and
`usage.output_tokens` from it. A run that trips the usage-limit backstop
(`limit_check.py`, added this round) and resumes emits **two** `result` events:

```
result#1: num_turns=104  out_tok=110362  cost=$12.21   (pre-limit segment)
result#2: num_turns=9     out_tok=4227    cost=$13.24   (resumed segment)
```

- `total_cost_usd` is **cumulative** → the emitted `cost_usd=$13.24` is correct.
- `num_turns` and `usage.output_tokens` are **per-segment** → the emitted
  `turns=9`, `output_tokens=4227` are wrong. True totals ≈ 113 turns /
  ~114.6k output tokens (introspect: 113 assistant msgs, 114,744 output tokens).

So A-rep4 looks like a 9-turn, 4k-token run that somehow cost $13.24. It is
actually the **largest** run in the set by every real measure (turns, output
tokens, cache reads, duration 3506 s = 2× the next longest). Anyone eyeballing
the jsonl will misread it as a crash/anomaly; it is a normal long run that
resumed once.

**Detection:** `user_messages=2` in `session_stats` (every other run has 1) and
duration ≈ 2× median are the tells. Only A-rep4 is affected this round.

**Fix (not yet applied):** aggregate across **all** `result` events —
`sum(num_turns)`, `sum(output_tokens)`, `sum(input_tokens)`, and take the last
non-empty `final_answer`/`terminal_reason`. `cost_usd` already aggregates, keep
last. Until fixed, treat `turns` and `output_tokens` as unreliable for any row
with `user_messages > 1`; pull those two columns from introspect instead.

## Issue 2 — `_storage` filesystem lock can corrupt the oracle grade, not just the run

**Row affected:** `A-rep2` (`71244339-…`) — the only `pass_to_pass=FAIL` /
`regression_ok=false` row in the set.

Several runs hit a `_storage` directory locked at mode `0200` mid-session
(A-rep1 ×4, A-rep2 ×6, A-rep4 ×3, D-rep1 ×2, D-rep3 ×1, D-rep4 ×4 tool results
with `_storage` + "permission denied"). The autouse storage fixture can't write,
so pytest errors out for every test that touches it.

`score.sh` runs the oracle pytest **inside `$RUN`** — the same directory whose
`_storage` is locked. If the lock is active during grading, both FAIL_TO_PASS
and PASS_TO_PASS error → both report `FAIL`. That is exactly and uniquely
A-rep2's signature:

- `fail_to_pass=FAIL` **and** `pass_to_pass=FAIL`, `regression_ok=false`
- most `_storage`-lock hits of any run (6)
- final answer is entirely about the lock: *"blocks every test that uses the
  autouse storage fixture, identically on the unmodified baseline (992 errors)…
  unrelated to my change."*

Every **genuine** incomplete-fix failure in the set (A-rep4, A-rep5, D-rep2,
D-rep3) keeps `pass_to_pass=PASS` — only the fixed test fails. A double FAIL is
the artifact fingerprint. So **A-rep2 is most likely a grading artifact, not a
model failure.** Its patch may or may not be correct; we can't tell from this
run.

**Implication for headline:** the raw solve rate is A 2/5 vs D 3/5. Excluding
the A-rep2 artifact, A is **2/4 (50%)** among validly-graded runs vs D 3/5
(60%). The gap shrinks and the "D solves more" story weakens — do not report
2/5-vs-3/5 without this caveat.

**Fix (not yet applied):** (a) find why `_storage` gets chmod'd to `0200`
mid-run and stop it (likely a leftover from a prior run's teardown racing the
next); (b) in `score.sh`, `chmod -R u+rwx "$RUN/_storage"` (or `rm -rf` it)
before applying the oracle; (c) flag `p2p=FAIL` rows for manual review rather
than trusting the grade.

## Issue 3 — `cost_usd` differs slightly between jsonl and introspect

Minor. jsonl vs introspect `session_stats.cost_usd`:
A1 9.66/9.52, A3 10.07/10.04, D5 7.33/7.27; others match. Two different cost
models (CLI `total_cost_usd` vs introspect's recompute from token counts). Sub-%
and non-systematic — safe to ignore, but pick one source per analysis and stick
to it. This report uses **introspect** for tokens/turns/duration and the CLI
`cost_usd` for dollars (it is what the run actually reported and aggregates over
resumes).

## Net effect on round-4 conclusions

- **Cost / tool-count / trajectory findings stand** — they come from introspect
  or from correct jsonl columns, and A-rep4's true (larger) totals only
  *strengthen* the "A explores more / costs more" direction.
- **Solve-rate finding is fragile** — 3/5 vs 2/5 is one flipped run at n=5, and
  one of A's two "fails" is a grading artifact. Not reportable as an effect.
