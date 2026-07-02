# 2026-07-01 — session naming + session_id in result rows

**What:** Every headless run now passes `claude -n <RUN_TAG>-<task>-<cond>-rep<rep>`
(display name), and each result row gains two columns:

- `session_id` — extracted from the transcript's first event carrying one
  (exact join key to Claude Code session logs / introspect).
- `session_name` — the same name passed via `-n`, rebuilt from
  `session_name()` in `config.sh`.

`RUN_TAG` defaults to `adhoc`; each round script exports its own
(`round2-opus`, `round2-sonnet`, `round3-dlt120-opus`, `round4-dlt131-opus`).

**Why:** Connecting introspect/session searches to result rows previously
required matching timestamps by hand. Names make sessions human-findable;
`session_id` makes the join exact.

**Files:** `harness/config.sh` (RUN_TAG + `session_name()`), `harness/run.sh`
(`-n` flag; DRY canned transcript carries a fixed dummy session_id),
`harness/parse_transcript.py` (`session_id` field), `harness/score.sh`
(`session_name` column), `harness/run_{opus_round,sonnet_round,dlt120_opus,dlt131_opus}.sh`
(RUN_TAG exports).

**Invalidates:** Nothing. The name is display-only metadata — not injected
into model context, so no condition leak; held constant in form across
conditions. Rows from earlier rounds simply lack the two columns
(`analyze.py` doesn't read them). Verified end-to-end via DRY run + a tiny
live haiku call confirming `-n` composes with `-p`.
