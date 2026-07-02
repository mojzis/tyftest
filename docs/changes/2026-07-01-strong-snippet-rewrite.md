# 2026-07-01 — Strong snippet (condition D) rewritten: soft power, fewer words

**What:** `harness/claude-snippet-strong.md` rewritten ~290 → ~150 words.
Dropped MANDATORY/"is a mistake" framing; now leads with the payoff (one call →
exact definition + signature + real refs vs. text matches needing verification)
and intercepts the observed slippage point directly ("catch yourself before
`grep \"def X\"` … — that's a `tyf` call"). Command list kept as bullets;
batching and grep carve-out kept, one line each.

**Why:** Round-3 dlt-120 D1/D4 never fired tyf despite the strong snippet;
dlt-103 analysis showed the reflex is `grep "def X"` via Bash, which the
shouty wording never redirected. Hypothesis: motivation + reflex interception
beats imperatives.

**Files:** `harness/claude-snippet-strong.md`.

**Invalidates:** D-condition results across snippet versions are not directly
comparable — prior D rows (round2, round3-dlt120) reflect the old wording (see
git history). New runs test the rewritten snippet.
