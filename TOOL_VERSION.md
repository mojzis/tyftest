# Tested commit (the tool under evaluation)

> Findings in this repo are valid **only** as of the tyf commit below.
> tyf moves fast — before reusing any result, diff `ty-find` HEAD against this
> SHA; if the navigation/parsing logic changed, re-pilot. (Discipline inherited
> from `~/git/pp`.)

| Field | Value |
|-------|-------|
| Tool | `tyf` (binary name) from `ty-find` |
| tyf version | `0.4.0` |
| tyf SHA | `cda1468` |
| tyf describe | `v0.4.0-11-gcda1468` |
| `ty` version | `0.0.49` |
| Built with | cargo 1.94.1 |
| Pilot model | _set at run time; recorded per result row_ |
| Date pinned | 2026-06-30 |

The C-condition CLAUDE.md snippet is taken verbatim from
`~/git/ty-find/docs/shared/claude-snippet.md` at this same SHA.

Rebuild the pinned binary with `harness/build_tyf.sh` (writes `bin/tyf` and
`bin/.tyf_sha`).
