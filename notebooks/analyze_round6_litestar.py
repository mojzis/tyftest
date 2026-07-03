import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import urllib.request
    from pathlib import Path

    import marimo as mo
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    return Path, go, json, mo, pd, px, urllib


@app.cell
def _(Path):
    RESULTS_PATH = Path(
        "/home/matous/git/tyftest/results/round6-litestar-opus.20260703-042713.jsonl"
    )
    API_BASE = "http://127.0.0.1:8347"  # introspect SQL API (bd#93)
    return API_BASE, RESULTS_PATH


@app.cell
def _(API_BASE, json, pd, urllib):
    def q(sql: str, limit: int = 1000) -> pd.DataFrame:
        """Run a read-only SELECT against the introspect DuckDB via the local SQL API."""
        body = json.dumps({"sql": sql, "limit": limit}).encode()
        req = urllib.request.Request(
            f"{API_BASE}/api/query",
            data=body,
            headers={"content-type": "application/json"},
        )
        with urllib.request.urlopen(req) as r:
            payload = json.loads(r.read())
        if "error" in payload:
            raise RuntimeError(payload["error"])
        df = pd.DataFrame(payload["rows"], columns=payload["columns"])
        df.attrs["truncated"] = payload.get("truncated", False)
        return df

    return (q,)


@app.cell
def _(RESULTS_PATH, json, mo, pd):
    res = pd.DataFrame(
        json.loads(line) for line in RESULTS_PATH.read_text().splitlines() if line.strip()
    )
    # tool_counts is a dict column -> expand a couple of useful ones
    res["reads"] = res["tool_counts"].apply(lambda d: d.get("Read", 0))
    res["edits"] = res["tool_counts"].apply(lambda d: d.get("Edit", 0))
    res["bash"] = res["tool_counts"].apply(lambda d: d.get("Bash", 0))
    mo.md(f"**{len(res)} sessions** · conds {sorted(res.cond.unique())} "
          f"· tasks {sorted(res.task.unique())} · 5 reps each")
    return (res,)


@app.cell
def _(mo):
    mo.md("""
    # Round 6 — litestar / opus: does the `tyf` snippet earn its keep?

    **Design.** 3 litestar tasks × 5 reps × 2 conditions = 30 sessions, opus-4.8.
    - **A** = control (no `tyf` snippet in CLAUDE.md)
    - **D** = treatment (`tyf` snippet present, agent *expected* to invoke `tyf`)

    Per-session outcome rows live in the results JSONL; rich conversation data is
    pulled live from the **introspect SQL API** (bd#93) and joined on `session_id`.
    """)
    return


@app.cell
def _(mo, res):
    # Headline: control (A) vs treatment (D)
    cond_summary = (
        res.groupby("cond")
        .agg(
            n=("cond", "size"),
            oracle_pass_rate=("oracle_pass", "mean"),
            tyf_invoked=("tyf_invocations", lambda s: (s > 0).sum()),
            mean_cost_usd=("cost_usd", "mean"),
            mean_turns=("turns", "mean"),
            mean_edits=("edits", "mean"),
            mean_reads=("reads", "mean"),
            mean_bash=("bash", "mean"),
        )
        .round(3)
        .reset_index()
    )
    mo.vstack([
        mo.md("## Headline — A (control) vs D (treatment)"),
        mo.md("Treatment invoked `tyf` in only **1 of 15** sessions; every other "
              "metric is within noise of control. The snippet was largely ignored."),
        mo.ui.table(cond_summary, selection=None),
    ])
    return


@app.cell
def _(mo, pd, res):
    # Gate reflects the tyf expectation, not outcome quality
    _gate = pd.crosstab(res.cond, res.gate)
    _fail = res.loc[~res.oracle_pass, ["task", "cond", "rep", "fail_to_pass", "pass_to_pass"]]
    mo.vstack([
        mo.md("### Gate outcomes"),
        mo.md("`WARN_NO_TYF` = treatment session that never invoked `tyf`. "
              "14/15 D sessions warned; the lone D `ok` is the single `tyf` invocation."),
        mo.ui.table(_gate.reset_index(), selection=None),
        mo.md("### The only oracle failure (a **control** session)"),
        mo.ui.table(_fail, selection=None),
    ])
    return


@app.cell
def _(mo, px, res):
    # Cost per session, control vs treatment, faceted by task
    _c = res.assign(cond_label=res.cond.map({"A": "A control", "D": "D treatment"}))
    _fig = px.strip(
        _c, x="cond_label", y="cost_usd", color="cond_label", facet_col="task",
        stripmode="overlay", hover_data=["rep", "turns", "tyf_invocations"],
        labels={"cost_usd": "cost (USD)", "cond_label": ""},
        title="Cost per session — A vs D by task",
        color_discrete_map={"A control": "#6c757d", "D treatment": "#2f81f7"},
    )
    _fig.update_traces(marker=dict(size=11, opacity=0.8), jitter=0.3)
    _fig.update_layout(showlegend=False, height=380, margin=dict(t=60, b=30))
    mo.ui.plotly(_fig)
    return


@app.cell
def _(mo, px, res):
    # Mean effort metrics side by side
    _m = (res.groupby("cond")[["cost_usd", "turns", "edits", "reads", "bash"]]
          .mean().reset_index()
          .melt(id_vars="cond", var_name="metric", value_name="mean"))
    _fig2 = px.bar(
        _m, x="metric", y="mean", color="cond", barmode="group",
        text_auto=".1f",
        title="Mean effort metrics — A (control) vs D (treatment)",
        color_discrete_map={"A": "#6c757d", "D": "#2f81f7"},
    )
    _fig2.update_layout(height=380, margin=dict(t=60, b=30),
                        legend_title_text="cond", yaxis_title="mean per session")
    mo.ui.plotly(_fig2)
    return


@app.cell
def _(mo, pd, q, res):
    # Pull richer per-session data live from introspect and join on session_id.
    # Adds wall-clock duration (absent from the results JSONL).
    _ids = ",".join(f"\'{s}\'" for s in res.session_id)
    stats = q(f"""
        SELECT session_id, duration, tool_count, files_edited, files_read,
               files_outside, cost_usd AS cost_introspect
        FROM session_stats
        WHERE session_id IN ({_ids})
    """)
    stats["duration_s"] = pd.to_timedelta(stats["duration"]).dt.total_seconds()
    enriched = res.merge(stats, on="session_id", how="left")
    enriched["cost_delta"] = enriched["cost_usd"] - enriched["cost_introspect"]
    mo.vstack([
        mo.md("## Joined with introspect (live SQL API)"),
        mo.md("Wall-clock `duration` comes from introspect; the results JSONL only has "
              "token/cost counts. Note the results-JSONL cost runs **higher** than "
              "introspect's — the harness accounting includes overhead introspect "
              "attributes elsewhere (max delta "
              "$%.2f)." % enriched.cost_delta.abs().max()),
        mo.ui.table(
            enriched.groupby("cond").agg(
                mean_duration_s=("duration_s", "mean"),
                mean_files_edited=("files_edited", "mean"),
                mean_tool_count=("tool_count", "mean"),
                mean_cost_jsonl=("cost_usd", "mean"),
                mean_cost_introspect=("cost_introspect", "mean"),
            ).round(2).reset_index(),
            selection=None,
        ),
    ])
    return (enriched,)


@app.cell
def _(enriched, mo, px):
    # Wall-clock duration, control vs treatment
    _d = enriched.assign(cond_label=enriched.cond.map({"A": "A control", "D": "D treatment"}))
    _figd = px.box(
        _d, x="cond_label", y="duration_s", color="cond_label", points="all",
        hover_data=["task", "rep", "tyf_invocations"],
        labels={"duration_s": "wall-clock (s)", "cond_label": ""},
        title="Session wall-clock duration — A vs D",
        color_discrete_map={"A control": "#6c757d", "D treatment": "#2f81f7"},
    )
    _figd.update_layout(showlegend=False, height=380, margin=dict(t=60, b=30))
    mo.ui.plotly(_figd)
    return


@app.cell
def _(mo, q, res):
    # Drill into the ONLY session that "invoked" tyf (litestar-4866/D/rep1)
    _sid = res.loc[res.tyf_invocations > 0, "session_id"].iloc[0]
    tyf_bash = q(f"""
        SELECT json_extract_string(tool_input, \'$.command\') AS command
        FROM tool_calls
        WHERE session_id = \'{_sid}\' AND tool_name = \'Bash\'
          AND json_extract_string(tool_input, \'$.command\') LIKE \'%tyf%\'
    """)
    mo.vstack([
        mo.md("## The one `tyf` invocation, inspected"),
        mo.md("Pulled live from `tool_calls`. The single counted invocation across all "
              "30 sessions is an **availability probe**, not a genuine run on code:"),
        mo.ui.table(tyf_bash, selection=None),
    ])
    return


@app.cell
def _(mo):
    mo.md("""
    ## Verdict

    - **The `tyf` snippet did not earn its keep this round.** Treatment (D) invoked
      `tyf` in 1/15 sessions, and that lone invocation is just `which tyf && tyf
      --version` — an availability check, not a real use. Effectively **0/15**
      genuine uses.
    - **No measurable effect on outcomes.** Oracle pass 0.93 (A) vs 1.00 (D), and
      cost/turns/edits/reads/duration all within noise. The single oracle failure
      was a **control** session (litestar-4806/A/rep1), unrelated to `tyf`.
    - **Data-quality note.** `tyf_invocations` counts any Bash command containing
      `tyf`; here it over-counts a version probe. Worth tightening the detector to
      require `tyf` as argv[0] with real arguments.
    - **Cost accounting.** Results-JSONL cost > introspect `session_stats.cost_usd`
      (delta up to ~$0.45/session); the two use different attribution — pick one
      consistently for cross-round comparisons.
    """)
    return


if __name__ == "__main__":
    app.run()
