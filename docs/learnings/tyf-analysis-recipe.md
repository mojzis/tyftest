# tyf analysis recipe — split runs + A-vs-D quick read (to be scripted)

Reusable know-how for turning a harness result `.jsonl` into an A-vs-D read-out, plus the
introspect join for distinct-file metrics. For the full paired-stats notebook (reads
introspect's DuckDB directly via a `bridge.csv`) see `tyf_analysis.py`; the significance
method is in `tyf-significance-test.md`. This doc is the lightweight, jsonl-only path — the
bit worth turning into a `harness/analyze_ad.py`.

Each jsonl row = one rep. Fields used: `cond` (A/D), `rep`, `cost_usd`, `turns`,
`tool_calls_total`, `tool_counts.{Read,Edit,Bash,Bash_tyf}`, `bytes_read`, `input_tokens`,
`output_tokens`, `tyf_invocations`, `oracle_pass`, `gate`.

## 1. Detect a conflated / truncated run

A file that ran twice has duplicate `(cond,rep)` keys and each run is a full A1–5/D1–5 block
(10 lines). Session-limit truncation shows as rows with `final_answer` = "You've hit your
session limit …", `is_error:true`, all-zero tool counts, `gate:"WARN_NO_TYF"`. Split at the
block boundary: `head -10` / `tail -n +11`.

## 2. Adherence gating

D reps with `tyf_invocations == 0` are `WARN_NO_TYF` — the treatment didn't happen. Always
report both raw D and **gated D** (tyf fired). Never average a no-op treatment into the effect.

## 3. Ratios (confound-normalizers)

Totals are noise-dominated (`tyf-experiment-lessons.md` §2–3); normalize intake by work done:

- `reads_per_edit = tool_counts.Read / max(tool_counts.Edit, 1)`
- `bytes_per_edit = bytes_read / max(edits, 1)`

Caveat: both get skewed by non-firing D runs — compute on gated D too before trusting them.

## 4. A-vs-D table (python, jsonl only)

```python
import json, statistics as st
rows = [json.loads(l) for l in open("results/round3-dlt120-opus-run2.jsonl") if l.strip()]
tc = lambda r, k: r["tool_counts"].get(k, 0)
A  = [r for r in rows if r["cond"] == "A"]
D  = [r for r in rows if r["cond"] == "D"]
Dg = [r for r in D if r["tyf_invocations"] > 0]            # adherence-gated
g    = lambda r, k: tc(r, k) if k in ("Read", "Edit", "Bash") else r[k]
mean = lambda xs, k: st.mean([g(r, k) for r in xs])
for k in ("cost_usd","turns","tool_calls_total","Bash","Read",
          "bytes_read","input_tokens","output_tokens"):
    a, d, dg = mean(A, k), mean(D, k), mean(Dg, k)
    print(f"{k:20} A={a:.2f} D={d:.2f} D/A={d/a:.2f} Dg/A={dg/a:.2f}")
```

## 5. Introspect distinct-file metrics

The harness jsonl only has Read *call* counts, not distinct files. introspect's
`session_stats` has `files_read` / `files_edited` (distinct files). `read_not_edited =
files_read − files_edited` = files opened but never modified (exploration/dead-end breadth).

Map each rep to its `session_id` from the run transcript, then join `session_stats`:

```bash
# rep -> session_id  (transcript's first line is the init record)
for f in $(find runs/dlt-120 -name transcript.jsonl | sort); do
  rep=$(echo "$f" | sed -E 's#runs/dlt-120/([AD])/rep([0-9]).*#\1\2#')
  sid=$(head -1 "$f" | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
  echo "$rep $sid"
done
```

```sql
-- introspect run_sql (call refresh_data first). session_stats.cost_usd should match the
-- harness jsonl per-run — use it as a cross-check that rows map to the right sessions.
WITH m(cond_rep, sid) AS (VALUES ('A1','<uuid>'), ('A2','<uuid>'), ...)
SELECT m.cond_rep, s.files_read, s.files_edited,
       s.files_read - s.files_edited AS read_not_edited,
       round(s.cost_usd, 3) AS usd, s.tool_count
FROM m LEFT JOIN session_stats s ON s.session_id = m.sid
ORDER BY m.cond_rep;
```

Note: run transcripts under `runs/<task>/<cond>/rep*/transcript.jsonl` are **overwritten each
run**, so they only reflect the *latest* run — fine when the latest is the canonical one, but
you can't recover an earlier conflated run's sessions this way.

## 6. Real analysis (not this pilot)

n=5/cell is directional only. For a defensible read: pair by rep (same task/checkout under both
variants), exact sign-flip permutation (2^10 = 1024) as primary + Wilcoxon + seeded bootstrap
CI, Holm across metrics. Full method: `tyf-significance-test.md`. Full notebook: `tyf_analysis.py`.
