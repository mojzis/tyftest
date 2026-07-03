import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import json
    import urllib.request
    from pathlib import Path

    import marimo as mo
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    return Path, json, mo, pd, px, urllib


@app.cell(hide_code=True)
def _():
    API_BASE = "http://127.0.0.1:8347"  # introspect SQL API (bd#93)
    return (API_BASE,)


@app.cell(hide_code=True)
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


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### What this is

    `tyf` is a code-navigation CLI (symbol lookup — `find`, `show`, `refs`) being
    evaluated for a permanent spot in Claude Code’s `CLAUDE.md`. To test whether it
    earns that standing context cost, we run the **same coding task** under two setups,
    **5 repetitions each**, on Claude Opus in headless mode:

    - **A (control)** — no `tyf` binary, no snippet.
    - **D (treatment)** — `tyf` on PATH **plus** a `CLAUDE.md` snippet telling the agent to use it.

    The task (`dlt-131`) is a real reverted bug-fix from the `dlt` library (PR #3431) —
    the agent sees the pre-fix code and a failing-test description but **never** the
    held-out oracle tests that grade it (SWE-bench style). It’s a ~100-step job
    spanning 8 files. Below we compare not just pass/fail but **how** the agent worked,
    using step-level data pulled live from the introspect log DB.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # `dlt-131` (round 4) — how the `tyf` snippet changes agent behavior

    **Design.** dlt task `dlt-131`, 5 reps × 2 conditions, opus-4.8.
    - **A** = control (no `tyf` snippet in CLAUDE.md)
    - **D** = treatment (`tyf` snippet present)

    This is the round where treatment actually **used `tyf`** (avg 4.6 calls/session).
    The interesting result isn’t pass/fail (0.6 vs 0.4 on n=5 is noise) — it’s a
    clear **behavioral shift**: with `tyf` the agent reads less, edits less, burns
    far less context, and finishes in fewer turns. Outcome rows come from the
    results JSONL; the step-level data is pulled live from the **introspect SQL API**
    (bd#93), joined on `session_id`.
    """)
    return


@app.cell(hide_code=True)
def _(Path, json, mo, pd):
    D131_PATH = Path("/home/matous/git/tyftest/results/round4-dlt131-opus.jsonl")
    d131 = pd.DataFrame(
        json.loads(l) for l in D131_PATH.read_text().splitlines() if l.strip()
    )
    d131["reads"] = d131.tool_counts.apply(lambda d: d.get("Read", 0))
    d131["edits"] = d131.tool_counts.apply(lambda d: d.get("Edit", 0))
    d131["bash"] = d131.tool_counts.apply(lambda d: d.get("Bash", 0))
    d131["tyf"] = d131.tyf_invocations
    # kept for the bar chart downstream
    behavior = (
        d131.groupby("cond")
        .agg(n=("cond", "size"), mean_tyf=("tyf", "mean"), reads=("reads", "mean"),
             edits=("edits", "mean"), bash=("bash", "mean"), turns=("turns", "mean"),
             cost=("cost_usd", "mean"))
        .round(1)
        .reset_index()
    )

    _metrics = [
        ("tyf", "tyf calls / session", "{:.1f}"),
        ("reads", "Read calls / session", "{:.1f}"),
        ("edits", "Edit calls / session", "{:.1f}"),
        ("bash", "Bash calls / session", "{:.1f}"),
        ("turns", "Turns / session", "{:.1f}"),
        ("cost", "Cost (USD) / session", "{:.2f}"),
    ]
    d131["cost"] = d131.cost_usd
    _A, _D = d131[d131.cond == "A"], d131[d131.cond == "D"]
    _rows = [{"metric": "Sessions (n)", "A  (control)": "5",
              "D  (treatment)": "5", "D / A": "\u2014"}]
    for _col, _label, _f in _metrics:
        _a, _d = _A[_col], _D[_col]
        _cell = lambda s: f"{_f.format(s.mean())} \u00b1 {_f.format(s.std())}"
        _ratio = f"{_d.mean() / _a.mean():.2f}" if _a.mean() else "\u2014"
        _rows.append({"metric": _label, "A  (control)": _cell(_a),
                      "D  (treatment)": _cell(_d), "D / A": _ratio})
    _disp = pd.DataFrame(_rows)
    mo.vstack([
        mo.md("### The behavioral difference (mean \u00b1 sd per session)"),
        mo.md("With `tyf` (D) the agent **reads 27% less, edits 35% less, and finishes "
              "in ~20% fewer turns** \u2014 it orients by symbol lookup instead of scanning "
              "files. The **D / A** column is the ratio (< 1 = treatment does less); "
              "spreads are \u00b11 sd across the 5 reps. Note D isn\u2019t just lower, it\u2019s "
              "**more consistent**: Edit spread collapses \u00b17.7\u2192\u00b11.1 and Turns "
              "\u00b142\u2192\u00b117 \u2014 the same variance-narrowing the locate phase shows "
              "(tyf gives a steadier \u201clook it up, then edit\u201d rhythm). Oracle pass 0.6 "
              "vs 0.4 is n=5 noise; the behavior is the signal."),
        mo.ui.table(_disp, selection=None),
    ])
    return behavior, d131


@app.cell(hide_code=True)
def _(d131, mo, q):
    # Per-session step metrics pulled live from introspect, joined on session_id
    _ids = ",".join(f"\'{s}\'" for s in d131.session_id.dropna())
    _comp = q(f"""
        SELECT session_id, tool_name, count(*) n FROM tool_calls
        WHERE session_id IN ({_ids}) GROUP BY 1, 2
    """, limit=500).pivot_table(index="session_id", columns="tool_name",
                                values="n", fill_value=0).reset_index()
    _churn = q(f"""
        SELECT session_id,
               sum(input_tokens + cache_read_tokens + cache_creation_tokens) AS context_tokens,
               sum(output_tokens) AS output_tokens,
               count(*) AS assistant_msgs
        FROM assistant_message_costs WHERE session_id IN ({_ids}) GROUP BY 1
    """)
    _start = q(f"""
        WITH firsts AS (
            SELECT session_id, min(timestamp) t0 FROM assistant_message_costs
            WHERE session_id IN ({_ids}) GROUP BY session_id)
        SELECT a.session_id,
               (a.input_tokens + a.cache_read_tokens + a.cache_creation_tokens) AS start_context
        FROM assistant_message_costs a
        JOIN firsts f ON a.session_id = f.session_id AND a.timestamp = f.t0
    """)
    _pre = q(f"""
        WITH fe AS (
            SELECT session_id, min(called_at) fe FROM tool_calls
            WHERE session_id IN ({_ids}) AND tool_name IN (\'Edit\', \'Write\')
            GROUP BY session_id)
        SELECT t.session_id,
               count(*) FILTER (WHERE t.called_at < fe.fe) AS calls_before_edit,
               count(*) FILTER (WHERE t.called_at < fe.fe AND t.tool_name = \'Read\') AS reads_before_edit
        FROM tool_calls t JOIN fe ON t.session_id = fe.session_id
        GROUP BY t.session_id
    """)
    steps = d131[["session_id", "cond", "rep", "turns", "cost_usd", "tyf_invocations"]].copy()
    for _df in (_comp, _churn, _start, _pre):
        steps = steps.merge(_df, on="session_id", how="left")
    mo.md(f"Built `steps` \u2014 **{len(steps)} sessions \u00d7 {steps.shape[1]} metrics** from introspect.")
    return (steps,)


@app.cell(hide_code=True)
def _(behavior, mo, px):
    # Fewer reads/edits/bash under treatment
    _b = behavior.melt(id_vars="cond", value_vars=["reads", "edits", "bash"],
                       var_name="tool", value_name="mean_calls")
    _b["cond_label"] = _b.cond.map({"A": "A control", "D": "D treatment"})
    _fig = px.bar(
        _b, x="tool", y="mean_calls", color="cond_label", barmode="group",
        text_auto=".1f",
        title="Tool calls per session \u2014 treatment does less of everything",
        labels={"tool": "", "mean_calls": "mean calls / session", "cond_label": ""},
        color_discrete_map={"A control": "#6c757d", "D treatment": "#2f81f7"},
    )
    _fig.update_layout(height=380, margin=dict(t=60, b=30))
    mo.ui.plotly(_fig)
    return


@app.cell(hide_code=True)
def _(mo, px, steps):
    # Total context processed per session
    _c = steps.assign(context_M=steps.context_tokens / 1e6,
                      cond_label=steps.cond.map({"A": "A control", "D": "D treatment"}))
    _figc = px.violin(
        _c, x="cond_label", y="context_M", color="cond_label", box=True, points="all",
        hover_data=["rep", "turns"],
        title="Context churned per session \u2014 ~31% less with tyf",
        labels={"context_M": "total context tokens (millions)", "cond_label": ""},
        color_discrete_map={"A control": "#6c757d", "D treatment": "#2f81f7"},
    )
    _figc.update_traces(meanline_visible=True, points="all", jitter=0.15, pointpos=0)
    _figc.update_layout(showlegend=False, height=380, margin=dict(t=60, b=30))
    mo.ui.plotly(_figc)
    return


@app.cell(hide_code=True)
def _(mo, steps):
    # Startup context size + exploration before the first edit
    _su = steps.groupby("cond").agg(
        start_context_tokens=("start_context", "mean"),
        calls_before_first_edit=("calls_before_edit", "mean"),
        reads_before_first_edit=("reads_before_edit", "mean"),
        total_turns=("turns", "mean"),
    ).round(1)
    _labels = {
        "start_context_tokens": "Startup context (tokens loaded)",
        "calls_before_first_edit": "Tool calls before first edit",
        "reads_before_first_edit": "Read calls before first edit",
        "total_turns": "Total turns / session",
    }
    _disp = _su.T
    _disp.columns = _disp.columns.map({"A": "A  (control)", "D": "D  (treatment)"})
    _disp = _disp.rename(index=_labels).reset_index().rename(columns={"index": "metric"})
    mo.vstack([
        mo.md("### Startup cost vs. what it saves"),
        mo.md("The `tyf` snippet adds only **~650 tokens** of startup context (D loads "
              "slightly more than A) \u2014 a rounding error against the **~3M tokens** of "
              "churn it removes over the session. Exploration *before* the first edit is "
              "similar; the savings compound *after*, across the whole run."),
        mo.ui.table(_disp, selection=None),
    ])
    return


@app.cell(hide_code=True)
def _(d131, mo, q):
    # Genuine tyf sub-commands in dlt-131 treatment, pulled live from introspect
    _sids = ",".join(f"\'{s}\'" for s in d131.session_id.dropna())
    tyf_calls = q(f"""
        SELECT session_id,
               json_extract_string(tool_input, \'$.command\') AS command
        FROM tool_calls
        WHERE session_id IN ({_sids}) AND tool_name = \'Bash\'
          AND regexp_matches(
              json_extract_string(tool_input, \'$.command\'),
              \'\\btyf (find|show|list|tree|callers|callees|refs)\\b\')
        ORDER BY session_id, command
    """, limit=200)
    tyf_calls["subcmd"] = tyf_calls["command"].str.extract(
        r"(tyf (?:find|show|list|tree|callers|callees|refs))")
    mix = tyf_calls["subcmd"].value_counts().rename_axis("subcmd").reset_index(name="n")
    mo.vstack([
        mo.md("### The `tyf` calls that actually ran (introspect `tool_calls`)"),
        mo.md(f"**{len(tyf_calls)} real symbol-navigation calls** across the 5 treatment "
              "sessions \u2014 `show` (definitions), `find` (locate), `refs` (usages):"),
        mo.ui.table(mix, selection=None),
        mo.md("Sample commands:"),
        mo.ui.table(tyf_calls[["session_id", "command"]].head(12), selection=None),
    ])
    return


@app.cell(hide_code=True)
def _(d131, mo, px, q):
    # Where the tyf calls land within a session
    _ids = ",".join(f"'{s}'" for s in d131.session_id.dropna())
    tyf_pos = q(f"""
        WITH ord AS (
            SELECT session_id, tool_name, tool_input,
                   row_number() OVER (PARTITION BY session_id ORDER BY called_at) rn,
                   count(*) OVER (PARTITION BY session_id) tot
            FROM tool_calls WHERE session_id IN ({_ids}))
        SELECT session_id, rn * 1.0 / tot AS frac
        FROM ord
        WHERE tool_name = 'Bash'
          AND regexp_matches(json_extract_string(tool_input, '$.command'),
                             '\\btyf (find|show|list|tree|callers|callees|refs)\\b')
    """, limit=200)
    _figp = px.histogram(
        tyf_pos, x="frac", nbins=10, range_x=[0, 1],
        title="When tyf gets called (position through the session)",
        labels={"frac": "position in session  (0 = start, 1 = end)"},
        color_discrete_sequence=["#2f81f7"],
    )
    _figp.update_layout(height=340, margin=dict(t=60, b=30), bargap=0.05,
                        yaxis_title="tyf calls")
    mo.vstack([
        mo.md("### `tyf` front-loads orientation"),
        mo.md(f"All **{len(tyf_pos)}** `tyf` calls land in the **first quarter** of their "
              "session (median ~13% in). The agent maps the code by symbol early, then "
              "spends the rest of the run searching less \\u2014 which is where the read/turn/"
              "context savings come from."),
        mo.ui.plotly(_figp),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ---
    ## Trajectory frames — the shape of each run

    Method & tool: `harness/trajectory.py` + `docs/learnings/tyf-trajectory-frames.md`.
    Every tool call is classified into one act (`tyf`, `grep`, `Read`, `Edit`,
    `pytest`, ...) and laid out in call order. The swimlane shows each run as a strip;
    the **mechanism metrics** below are the numbers that *move when tyf changes
    behavior* (totals don’t) — the opening navigation tool, calls-to-first-edit,
    and grep vs tyf counts.
    """)
    return


@app.cell(hide_code=True)
def _(d131, json, mo, q):
    # Classify every tool call in order (classifier ported from harness/trajectory.py)
    import re as _re

    _BASH_PATTERNS = [
        ("tyf",   _re.compile(r"(^|[^\w/])tyf ")),
        ("TEST",  _re.compile(r"pytest|python -m pytest|uv run pytest")),
        ("grep",  _re.compile(r"\bgrep\b|\brg ")),
        ("repro", _re.compile(r"python -c|uv run python|/tmp/|cat >|<<")),
        ("git",   _re.compile(r"\bgit ")),
    ]
    def _classify(tool_name, tool_input):
        if tool_name != "Bash":
            return tool_name if tool_name in ("Read", "Edit", "Write") else "bash"
        try:
            cmd = json.loads(tool_input).get("command", "") if tool_input else ""
        except Exception:
            cmd = tool_input or ""
        for act, pat in _BASH_PATTERNS:
            if pat.search(cmd):
                return act
        return "bash"

    ACT_COLORS = {"tyf": "#00b4b4", "grep": "#c8a000", "Read": "#3fa63f", "Edit": "#b24bd8",
                  "Write": "#8e30b0", "TEST": "#3f6ad6", "repro": "#888888",
                  "git": "#bbbbbb", "bash": "#666666"}
    ACT_ORDER = list(ACT_COLORS)

    _ids = ",".join(f"'{s}'" for s in d131.session_id.dropna())
    _tc = q(f"""
        SELECT session_id, tool_name, tool_input,
               row_number() OVER (PARTITION BY session_id ORDER BY called_at) AS i,
               count(*) OVER (PARTITION BY session_id) AS tot
        FROM tool_calls WHERE session_id IN ({_ids})
        ORDER BY session_id, called_at
    """, limit=5000)
    _tc["act"] = [_classify(n, ti) for n, ti in zip(_tc.tool_name, _tc.tool_input)]
    _tc["frac"] = _tc.i / _tc.tot
    traj = _tc.merge(d131[["session_id", "cond", "rep"]], on="session_id")
    traj["run"] = traj.cond + " rep" + traj.rep.astype(str)
    mo.md(f"Classified **{len(traj)} tool calls** across {traj.session_id.nunique()} "
          f"runs into {len(ACT_ORDER)} act types.")
    return ACT_COLORS, ACT_ORDER, traj


@app.cell(hide_code=True)
def _(ACT_COLORS, ACT_ORDER, d131, mo, px, traj):
    # Swimlane — each run's tool sequence on an explicit numeric y-axis so the
    # failure bands align deterministically (categorical-axis hrect does not).
    _sw = traj.merge(d131[["cond", "rep", "fail_to_pass"]], on=["cond", "rep"])
    _runs = (
        _sw.drop_duplicates(["cond", "rep"])[["cond", "rep", "fail_to_pass"]]
        .sort_values(["cond", "rep"]).reset_index(drop=True)
    )
    _runs["y"] = _runs.index
    _runs["label"] = (_runs.cond + " rep" + _runs.rep.astype(str) + " "
                      + _runs.fail_to_pass.map({"PASS": "\u2713", "FAIL": "\u2717"}))
    _sw = _sw.merge(_runs[["cond", "rep", "y"]], on=["cond", "rep"])
    _fig = px.scatter(
        _sw, x="i", y="y", color="act",
        category_orders={"act": ACT_ORDER}, color_discrete_map=ACT_COLORS,
        hover_data={"i": True, "frac": ":.2f", "y": False},
        title="Trajectory frames \u2014 tool-call sequence per run  (\u2717 = failed the oracle, shaded)",
        labels={"i": "call index"},
    )
    _fig.update_traces(marker=dict(symbol="square", size=7))
    _fig.update_yaxes(tickmode="array", tickvals=_runs.y.tolist(),
                      ticktext=_runs.label.tolist(), title="",
                      range=[-0.5, len(_runs) - 0.5])
    for _y in _runs.loc[_runs.fail_to_pass == "FAIL", "y"]:
        _fig.add_hrect(y0=_y - 0.5, y1=_y + 0.5, fillcolor="#c8503f",
                       opacity=0.15, line_width=0, layer="below")
    _fig.update_layout(height=460, margin=dict(t=60, b=30), legend_title_text="act")
    mo.ui.plotly(_fig)
    return


@app.cell(hide_code=True)
def _(d131, mo, pd, traj):
    # Per-run mechanism metrics (the trajectory-frame headers from harness/trajectory.py)
    def _frame(g):
        seq = g.sort_values("i").act.tolist()
        fe = next((i for i, a in enumerate(seq) if a == "Edit"), len(seq))
        nav1 = next((a for a in seq if a in ("tyf", "grep", "Read")), "-")
        return pd.Series({"locate_len": fe, "grep": seq.count("grep"),
                          "tyf": seq.count("tyf"), "nav1": nav1})

    frames = (
        traj.groupby(["cond", "rep"]).apply(_frame, include_groups=False).reset_index()
        .merge(d131[["cond", "rep", "fail_to_pass"]], on=["cond", "rep"])
    )
    frames["run"] = frames.cond + " rep" + frames.rep.astype(str)
    _disp = (
        frames.sort_values(["cond", "rep"])[
            ["run", "nav1", "locate_len", "grep", "tyf", "fail_to_pass"]
        ].rename(columns={"nav1": "first nav", "locate_len": "calls \u2192 1st edit",
                          "grep": "grep calls", "tyf": "tyf calls",
                          "fail_to_pass": "solved"})
    )
    mo.vstack([
        mo.md("### Mechanism metrics per run"),
        mo.md("Two things jump out: **`first nav` flips grep\u2192tyf perfectly** (5/5 in "
              "each arm), and **A\u2019s `calls \u2192 1st edit` swings 11\u201348** while D stays a "
              "tight 16\u201329 \u2014 tyf gives a consistent \u201clook it up, then edit\u201d rhythm."),
        mo.ui.table(_disp, selection=None),
    ])
    return (frames,)


@app.cell(hide_code=True)
def _(frames, mo, px):
    # First navigation reflex — grep vs tyf, per condition
    _n = frames.assign(cond_label=frames.cond.map({"A": "A control", "D": "D treatment"}))
    _c = _n.groupby(["cond_label", "nav1"]).size().reset_index(name="runs")
    _fig = px.bar(
        _c, x="cond_label", y="runs", color="nav1", text="runs",
        color_discrete_map={"tyf": "#00b4b4", "grep": "#c8a000"},
        category_orders={"nav1": ["grep", "tyf"]},
        title="First navigation tool \u2014 tyf deterministically flips the opening reflex (5/5)",
        labels={"cond_label": "", "runs": "runs (of 5)", "nav1": "first nav"},
    )
    _fig.update_layout(height=360, margin=dict(t=60, b=30))
    mo.ui.plotly(_fig)
    return


@app.cell(hide_code=True)
def _(frames, mo, px):
    # Does tyf dose track success?
    _d = frames.assign(
        cond_label=frames.cond.map({"A": "A control", "D": "D treatment"}),
        solved=frames.fail_to_pass.map({"PASS": "solved", "FAIL": "failed"}),
    )
    _fig = px.strip(
        _d, x="tyf", y="cond_label", color="solved",
        color_discrete_map={"solved": "#3fa63f", "failed": "#c8503f"},
        stripmode="overlay", hover_data=["run", "grep", "locate_len"],
        title="tyf dose vs. outcome \u2014 D runs with \u22654 tyf calls all solved; \u22642 all failed",
        labels={"tyf": "tyf calls in the run", "cond_label": "", "solved": ""},
    )
    _fig.update_traces(marker=dict(size=14, opacity=0.85), jitter=0.25)
    _fig.add_vline(x=3.5, line_dash="dash", line_color="#888",
                   annotation_text="dose threshold", annotation_position="top")
    _fig.update_layout(height=340, margin=dict(t=60, b=30))
    mo.vstack([
        mo.ui.plotly(_fig),
        mo.md("*Caveat \u2014 n=5: this is a suggestive lead, not a result. The `first nav` "
              "grep\u2192tyf flip is deterministic (5/5, robust), but the dose\u2192solve split "
              "rests on one or two runs per side; solve-rate p=1.00 at this N. Powering "
              "the effect needs ~13 reps/arm (see `docs/learnings/tyf-significance-test.md`).*"),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ---
    ## Wait — 5/10 failed. What happened?

    That looks alarming; it mostly isn’t. `dlt-131` is a **deliberately hard**,
    SWE-bench-style task: a real reverted bug-fix (dlt PR #3431), ~100 steps across 8
    files, graded by **held-out oracle tests the agent never sees**. Near-ceiling pass
    rates would mean the task is too easy to measure navigation at all. Every run in
    *both* arms correctly **diagnosed** the bug (accumulate-vs-replace, the two leak
    layers); failures came down to whether the fix reached the destination-schema layer
    the oracle checks — and how much thrash it took to get there.

    - **A rep2 — not a real failure (grading artifact).** Hit a `_storage` file-lock;
      pytest then errored on *every* test in the locked run dir, which is exactly where
      scoring runs — the only run with `pass_to_pass=FAIL` / `regression_ok=false`.
      Patch quality unknown. Excluding it, control solves **2/4**.
    - **A rep4 — over-engineering rabbit-hole.** Dove in early (first edit at call ~11),
      built a 3-part fix and even rewrote the oracle test’s own assertions, landing on the
      wrong layer. No regression (`p2p=PASS`) but wrong behavior (`f2p=FAIL`). Also the
      priciest run ($13) and the one that tripped the usage-limit backstop.
    - **A rep5 — genuine incomplete fix**, second-highest edit churn.
    - **D rep2 & D rep3 — the low-dose tyf runs.** Both fired tyf only **2×** and stopped
      short of the destination-schema layer — fast, cheap, incomplete. These are exactly
      the runs where treatment barely adopted the tool; behaviorally they look like baseline
      A. **Every D run that used tyf ≥4× passed.**

    **Takeaway.** Solve-rate at n=5 is noise (p=1.00), one control “fail” is a harness bug,
    and both treatment fails are *low-adoption* runs rather than tyf-assisted-and-still-wrong.
    The durable signal is behavioral — the grep→tyf flip, fewer greps, tighter spreads —
    not the pass count. Corrected solve rate: **A 2/4, D 3/5**. To firm it up: fix the
    storage-lock scorer and re-grade A rep2, then add reps (~13/arm).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ---
    > **A note on pace.** Running these experiments takes a lot of time, patience,
    > and tokens/money — each cell is a full ~100-step headless Opus session, run
    > many times over. More results are coming, but they accrue slowly. The above is
    > one task’s worth of the picture, not the final word.
    """)
    return


if __name__ == "__main__":
    app.run()
