# Why dlt-103 never invoked tyf (root cause)

Follow-up to `tyf-experiment-lessons.md`, which recorded *that* tyf fired zero
times on dlt-103 in every condition. This is *why*. Evidence: `runs/dlt-103/{A,C,D}/rep*`
and `runs/dlt-110/{C,D}/rep*` transcripts, `results/round2-opus.jsonl`.

## It was not a setup failure

- Snippet present and correct in the fixtures: `fixtures/dlt-103/C/CLAUDE.md` (9 tyf
  mentions), `.../D/CLAUDE.md` (12) — identical to dlt-110's C snippet.
- tyf on PATH. Real invocation count in every 103 cell = **0** (the 100+ "tyf"
  substrings in a transcript are all `tyftest` path fragments and the CLAUDE.md
  snippet text, not `tyf ` commands).
- Strong wording (D) did not move it off zero.

## Root cause: the task's discovery surface is string/marker-anchored, not symbol-anchored

tyf answers "where is symbol X / what's its signature / who calls it." A task only
pulls tyf if its natural first move is *locate a named symbol*. The two round-2
tasks differ exactly on this axis:

| | dlt-110 (tyf=21) | dlt-103 (tyf=0) |
|---|---|---|
| First thing you search for | a distinctive **symbol** `materialize_table_schema` | an internal **marker string** `seen-null-first` |
| Natural first move | `grep materialize_table_schema` → `tyf find/show/refs` on it | `grep "seen-null-first"` / `"placeholder"` / `"child table"` |
| Snippet's own verdict | symbol lookup → **use tyf** | string literal → **"fall back to Grep"** |

dlt-103's prompt is written in terms of behavior and data markers — the
`seen-null-first` normalizer marker, "placeholder column," a field that "becomes a
nested/child table," "shortened table names." None are Python symbols. Every
opening grep in every 103 run was a string/concept search (`seen-null-first`,
`placeholder`, `nested`, `child table`), which is **exactly the case the snippet
carves out for Grep** ("Only fall back to Grep for genuinely non-symbol text:
string literals … log messages"). So the mandatory-tyf instruction never bit —
correctly, by its own rules.

dlt-110 had one uniquely-named function at the center of the fix
(`materialize_table_schema`) — a textbook `tyf find`/`tyf show` target. That is
what pulled 21 tyf calls.

## Secondary: the snippet doesn't reliably redirect grep-for-def either

Even where 103 *did* do a symbol lookup (`grep "def normalize_table_identifier"`,
`normalize_path`), the model reached for `grep "def …"` via Bash instead of
`tyf find`. The same slippage shows up in dlt-110's early turns. So the snippet is
weak even in-territory; 103 just also lacked the dominant distinctive symbol that
made the pull obvious in 110.

## Measurement note

Grep-tool count is 0 across all 103 and 110 cells not because no searching
happened, but because the model runs `grep` **through Bash**, not the Grep tool.
The `tool_counts.Grep` column understates text-search activity; look at Bash
command strings to see the real search behavior.

## Implications for task selection

- tyf adoption is **task-shaped, not snippet-shaped**. Stronger wording can't
  rescue a task that poses no symbol-find question.
- To measure tyf's value, favor prompts anchored on **named symbols** (like
  dlt-110). Marker/behavior-anchored tasks (like dlt-103) null out adoption
  regardless of snippet strength.
- dlt-103 also gives tyf no room to *show* benefit: all 9 cells passed oracle
  without it. It's a poor discriminator and a candidate to prune or rewrite.
- Next round: classify each candidate task as symbol-anchored vs marker-anchored
  before including it; a pool dominated by marker tasks will report low adoption
  that says nothing about the tool.
