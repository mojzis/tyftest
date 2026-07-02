# tyftest

Controlled experiment: does the `tyf` CLAUDE.md snippet earn its keep? See
`README.md` and `docs/setup/tyf-experiment-protocol.md`.

## Analyzing

- Result rows carry `session_id` + `session_name` (`<RUN_TAG>-<task>-<cond>-rep<rep>`,
  also the session's `claude -n` display name) — join keys between
  `results/*.jsonl` and introspect/session searches.

## Conventions

- **Document methodology/harness changes.** When you change the experiment design
  or harness behavior in a way that affects results or reproducibility, add a
  short dated note under `docs/changes/` (`YYYY-MM-DD-<slug>.md`): what changed,
  why, files touched, and what it invalidates. Keep it brief.
