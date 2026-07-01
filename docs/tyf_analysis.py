# %% [markdown]
# # tyf experiment — analysis notebook
#
# Reads per-run data straight from introspect's materialized DuckDB, joins the
# per-task manifest, computes trajectory metrics, runs paired stats.
#
# introspect needs **no changes**: we open our own read-only connection on the
# same on-disk DB it already builds. Our connection has no ATTACH/COPY validator
# (that was only the MCP `run_sql` tool), so the manifest join is just SQL/pandas.
#
# Run order: §1 setup → §2 discovery (LOOK before trusting queries) → §3 the
# manifest-free per-run frame (works today) → §4–5 manifest join + stats
# (need your two files — see the note at §4).

# %% [markdown]
# ## §1 Setup
#
# Prereq: the DB must exist + be materialized (`introspect serve` or
# `introspect materialize`). If the read-only connect raises a lock error,
# introspect is mid-refresh/writing — either set
# `INTROSPECT_REFRESH_INTERVAL_SECONDS=0`, run `introspect materialize` and stop
# the server, or just analyze a copied snapshot of the .duckdb file.

# %%
import duckdb
import pandas as pd
from pathlib import Path

INTROSPECT_DB = Path("~/.introspect/introspect.duckdb").expanduser()
con = duckdb.connect(str(INTROSPECT_DB), read_only=True)


# %% [markdown]
# ## §2 Discovery — see the REAL columns first
#
# I don't know introspect's exact column names (the architecture doc lists views,
# not full schemas) and `read_json_auto` may have nested some result-object
# fields. Run this, eyeball it, and reconcile the column names used in §3 against
# what you actually see. This is the 30-second step that saves you debugging guesses.

# %%
schema = con.sql("""
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    ORDER BY table_name, ordinal_position
""").df()
for t, g in schema.groupby("table_name"):
    print(f"{t}: " + ", ".join(g.column_name))

# %%
# Peek at the tables §3 leans on — confirms column names AND whether `input`/
# `usage` are STRUCT (use input.command) vs JSON text (use input ->> 'command').
for tbl in ["assistant_message_costs", "tool_calls", "file_reads"]:
    print(f"\n=== {tbl} ===")
    print(con.sql(f"SELECT * FROM {tbl} LIMIT 3").df().T)


# %% [markdown]
# ## §3 The manifest-free per-run frame (runs today)
#
# Everything here is derivable from the transcript alone — the tidy one-row-per-run
# table minus the gold-dependent columns. Confirm it looks right before §4.

# %% [markdown]
# ### Result-object fields — turns, durations, billed cost, status
# These live on `type='result'` records. If a column is missing below, find its
# real path in §2 (it may be `raw_data.<col>`, a struct field, or need
# `json_extract(value,'$.num_turns')`). **Prefer `total_cost_usd` here over
# introspect's computed cost** — this one is the authoritative billed number.

# %%
results = con.sql("""
    SELECT
        sessionId                  AS session_id,
        subtype,
        num_turns,
        duration_ms,
        duration_api_ms,
        total_cost_usd,
        COALESCE(is_error, FALSE)  AS is_error
    FROM raw_data
    WHERE type = 'result'
""").df()
results["capped"] = results.subtype.isin(["error_max_turns", "error_max_budget_usd"])
results["converged"] = (~results.is_error) & (~results.capped)

# %% [markdown]
# ### Cost & token decomposition (introspect's strong suit)
# `input_tokens` already excludes cache → that IS `input_tokens_fresh`.
# `peak_turn_input_tokens` ≈ max per-message input (turn ≈ assistant API call).

# %%
tokens = con.sql("""
    SELECT
        session_id,
        SUM(input_tokens)                 AS input_tokens_fresh,
        SUM(cache_read_input_tokens)      AS cache_read_tokens,
        SUM(cache_creation_input_tokens)  AS cache_creation_tokens,
        SUM(output_tokens)                AS output_tokens,
        MAX(input_tokens)                 AS peak_turn_input_tokens
    FROM assistant_message_costs
    GROUP BY 1
""").df()

# %% [markdown]
# ### Tool counts, tyf adherence, first-nav
# Adjust `input ->> 'command'` to `input.command` if `input` is a STRUCT (§2).

# %%
tool_counts = con.sql("""
    SELECT session_id, 'n_' || tool_name AS col, COUNT(*) AS n
    FROM tool_calls GROUP BY 1, 2
""").df().pivot(index="session_id", columns="col", values="n").fillna(0).reset_index()

tyf = con.sql("""
    SELECT session_id,
           COUNT(*) FILTER (WHERE is_tyf)                  AS tyf_invocations,
           COUNT(*) FILTER (WHERE is_tyf AND NOT is_error) AS tyf_success_count
    FROM (
        SELECT session_id, is_error,
               (tool_name = 'Bash' AND (input ->> 'command') LIKE 'tyf%') AS is_tyf
        FROM tool_calls
    ) GROUP BY 1
""").df()

first_nav = con.sql("""
    WITH nav AS (
        SELECT session_id, timestamp,
               CASE WHEN tool_name = 'Bash' AND (input ->> 'command') LIKE 'tyf%'
                    THEN 'tyf' ELSE tool_name END AS nav_tool,
               ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY timestamp) AS rn
        FROM tool_calls
        WHERE tool_name IN ('Read', 'Grep', 'Glob')
           OR (tool_name = 'Bash' AND (input ->> 'command') LIKE 'tyf%')
    )
    SELECT session_id, nav_tool AS first_nav_tool, (nav_tool = 'tyf') AS tyf_used_first
    FROM nav WHERE rn = 1
""").df()

# Read order kept for the ordering metrics in §4 (needs a timestamp on file_reads;
# if absent, order by tool_calls timestamp joined on tool_use id instead).
reads = con.sql("""
    SELECT session_id, file_path,
           ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY timestamp) AS read_order
    FROM file_reads
""").df()
files_read = reads.groupby("session_id").file_path.nunique().rename("files_read").reset_index()

# %% [markdown]
# ### Assemble — the working slice
# %%
per_run = (results
    .merge(tokens, on="session_id", how="left")
    .merge(tool_counts, on="session_id", how="left")
    .merge(tyf, on="session_id", how="left")
    .merge(first_nav, on="session_id", how="left")
    .merge(files_read, on="session_id", how="left"))
per_run.head()


# %% [markdown]
# ## §4 Manifest join — NEEDS YOUR TWO FILES
#
# I can't finalize these without:
#  1. **bridge.csv** (your harness emits this per run; the transcript can't recover
#     `condition` — the CLAUDE.md snippet treatment isn't a reliable per-message field):
#       `session_id, task_id, condition, rep_index, size_tier, task_type,
#        model_string, cc_version`
#  2. **manifest.csv** (your per-task file). Columns + the gold_files delimiter
#     drive the code below — adjust the `.str.split(";")` to match:
#       `task_id, gold_files, oracle_tests, pass_to_pass, ty_status, pin_sha`

# %%
bridge = pd.read_csv("bridge.csv")
manifest = pd.read_csv("manifest.csv")
runs = per_run.merge(bridge, on="session_id", how="inner").merge(manifest, on="task_id", how="left")

# %% [markdown]
# ### Gold set-metrics (recall / precision / reads_outside_gold / time-to-gold)
# Reminder from the spec: report `reads_outside_gold` as a **paired delta within
# task** (§4 caveat), never as a standalone absolute.

# %%
gold = (manifest.assign(gold_path=manifest.gold_files.str.split(";")).explode("gold_path"))
gold["gold_path"] = gold.gold_path.str.strip()
gold_total = gold.groupby("task_id").gold_path.nunique().rename("gold_total")

reads_t = (reads.merge(bridge[["session_id", "task_id"]], on="session_id")
                .merge(gold[["task_id", "gold_path"]],
                       left_on=["task_id", "file_path"], right_on=["task_id", "gold_path"], how="left"))
reads_t["in_gold"] = reads_t.gold_path.notna()

distinct_gold = reads_t[reads_t.in_gold].groupby("session_id").file_path.nunique().rename("distinct_gold_hits")
agg = reads_t.groupby("session_id").agg(task_id=("task_id", "first"),
                                        reads_total=("file_path", "size"),
                                        gold_hits=("in_gold", "sum"))
set_metrics = (agg.join(distinct_gold).fillna({"distinct_gold_hits": 0})
                  .reset_index().merge(gold_total, on="task_id"))
set_metrics["gold_read_recall"] = set_metrics.distinct_gold_hits / set_metrics.gold_total
set_metrics["gold_read_precision"] = set_metrics.gold_hits / set_metrics.reads_total
set_metrics["reads_outside_gold"] = set_metrics.reads_total - set_metrics.gold_hits

# reads before first gold-file read (time-to-right-place)
ro = reads_t.sort_values(["session_id", "read_order"]).copy()
ro["seen_gold"] = ro.groupby("session_id").in_gold.cumsum()
rbfg = ro[ro.seen_gold == 0].groupby("session_id").size().rename("reads_before_first_gold")
set_metrics = set_metrics.merge(rbfg, on="session_id", how="left").fillna({"reads_before_first_gold": 0})

runs = runs.merge(set_metrics.drop(columns="task_id"), on="session_id", how="left")


# %% [markdown]
# ## §5 Stats — descriptive first, inferential as the next slice
#
# DuckDB/pandas handle the descriptive layer. Mixed-effects / bootstrap CIs /
# mediation are statsmodels territory — left as the explicit next step, not faked.

# %%
METRICS = ["total_cost_usd", "input_tokens_fresh", "num_turns", "reads_outside_gold"]

# Censoring: keep capped/error OUT of token/turn central tendency; report rates separately.
rates = runs.groupby("condition").agg(
    n=("session_id", "size"),
    cap_rate=("capped", "mean"),
    error_rate=("is_error", "mean"),
    converged_rate=("converged", "mean"),
)

# median + IQR + n per (task × condition), converged runs only
def iqr(s): return s.quantile(.75) - s.quantile(.25)
cell = (runs[runs.converged].groupby(["task_id", "condition"])[METRICS]
        .agg(["median", iqr, "size"]))

# Paired contrasts C−A and C−B, task as the unit (collapse reps to the cell median first)
med = runs[runs.converged].groupby(["task_id", "condition"])[METRICS].median().unstack("condition")
paired = pd.DataFrame({
    m: {"C_minus_A_med": (med[(m, "C")] - med[(m, "A")]).median(),
        "C_minus_B_med": (med[(m, "C")] - med[(m, "B")]).median()}
    for m in METRICS
}).T

print(rates, "\n\n", paired)

# %% [markdown]
# ### Next (deliberately not built yet)
# - Mixed-effects with task as random effect for the headline contrasts (statsmodels `mixedlm`).
# - Bootstrap CIs on the paired deltas.
# - Mediation: does `first_nav_class` predict downstream cost *within* each condition?
# - Hard gate: drop/relabel condition-C runs where `tyf_success_count == 0` (collapsed to B),
#   logged to an exclusion table.
