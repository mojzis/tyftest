# 2026-07-01 — Baseline CLAUDE.md is the repo's real file, not a neutral stub

## What changed

The harness no longer deletes the target repo's shipped `CLAUDE.md` and replaces
it with a fixed neutral stub. It now **keeps the repo's real `CLAUDE.md`
verbatim** as the baseline for all conditions.

- **A/B** = repo's real `CLAUDE.md`, unchanged.
- **C** = real `CLAUDE.md` + standard tyf snippet appended.
- **D** = real `CLAUDE.md` + strong tyf snippet appended.

Fallback: if a repo ships no `CLAUDE.md`, the neutral stub
(`harness/neutral_claude.md`) is installed as before.

## Why

The design intent is a **within-project A-vs-D contrast** — does the tyf snippet
earn its keep *on top of the onboarding a real user already has* — not a
snippet-vs-neutral-baseline comparison. Replacing the real file with a neutral
stub measured the wrong thing: it stripped the project's actual instructions
(for dlt: principles + "use `uv`/`uv run`, see @Makefile" + branch-from-devel)
that any real user of the tool would have in context.

Because the same real `CLAUDE.md` is handed to **both** A and D, anything it
carries (incl. the `@Makefile` import and uv/make guidance) hits both conditions
symmetrically and therefore does **not** confound the snippet contrast.

## Files touched

- `harness/launder.sh` — keep repo `CLAUDE.md` verbatim; stub only as fallback.
- `harness/build_conditions.sh` — comment only (append logic already correct).
- `docs/tyf-experiment-repo-prep.md` — §4/§5 updated to match; A–D table.

## Consequence

All existing **A and D** runs used the old neutral baseline and are now stale for
the CLAUDE.md dimension — they must be re-run. Affects `results/round2-opus.jsonl`
(A/C/D) and the sonnet pilot.
