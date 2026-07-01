# Trajectory frames — method & tooling

A **trajectory frame** renders one run's tool-call sequence as a left-to-right glyph
strip, split into locate / implement / verify phases, with per-run mechanism metrics.
It's the view that exposes *behavior* the token/byte totals hide — reflexive
grep-after-tyf, re-reading hot files, grep-thrash outliers. Built for the tyf
experiment but reusable for any `runs/**` transcript tree.

Emitter: `harness/trajectory.py`. Depends only on `duckdb` + stdlib.

---

## Why frames (not totals)

Aggregate metrics (`input_tokens`, `bytes_read`) are dominated by trajectory *shape*,
not condition — see `tyf-experiment-lessons.md` §2. Two runs with the same byte total
can have opposite strategies. The frame makes the strategy legible: you can *see*
whether a run opened with tyf or grep, whether the locate phase was tight or thrashed,
and whether tyf actually displaced grep (it didn't — every tyf run still greps).

---

## Reading a frame

```
dlt-110/D/rep3   locate=8  tyf=4 grep=7  files=5 rereads=3 nav1=tyf
  T T g g g R R T │ E R R g R R R E g E ‖ v p p T . R g E E E E R E v v v v g R v v v .
```

- **Glyphs** (one per tool call, in order):
  `T` tyf · `g` grep(bash) · `R` Read · `E` Edit · `W` Write · `v` pytest ·
  `p` python repro · `.` git · `b` other bash.
- **`│`** marks the first Edit (end of *locate* phase); **`‖`** the first pytest (end of
  *implement* phase). So: `locate … │ implement … ‖ verify …`.
- **Metrics** (the header — these move iff tyf changes behavior; totals don't):
  - `locate_len` — calls before first Edit. Should *shrink* if tyf speeds navigation.
  - `tyf`, `grep` — adoption vs the reflexive grep it's meant to replace.
  - `distinct_files`, `max_rereads` — "read once precisely" vs re-reading hot files.
  - `nav1` — the first navigation tool (tyf or grep): did the run *start* with tyf?

**What round 2 showed at a glance:** D frames open `T … T … g … R` — tyf, then grep
*anyway* — and `locate_len` is *larger* in D (8–9) than A (4–7). tyf was layered on,
not substituted in.

## Classification note

Each tool call gets **one primary label** (first pattern match wins), so a Bash command
that both greps and runs pytest counts as `pytest`. This makes `grep`/`tyf` counts
"calls whose primary purpose was X" — slightly lower than a substring count, and more
faithful to intent. Order of checks lives in `BASH_PATTERNS` in the script.

---

## Usage

```bash
# terminal (ANSI color auto-on when stdout is a tty)
python3 harness/trajectory.py                        # all runs under runs/**
python3 harness/trajectory.py --glob '%runs/dlt-110/%' --conds A D
python3 harness/trajectory.py --svg frames.svg       # + presentable swimlane

# no duckdb in system python? run through uv:
uv run --with duckdb python3 harness/trajectory.py --conds A D
```

Reads introspect's materialized DuckDB read-only (`~/.introspect/introspect.duckdb`,
override with `INTROSPECT_DB`). Runs are discovered by parsing `task/cond/rep` out of
each session's `cwd` (`runs/<task>/<cond>/rep<N>`), so no bridge file is needed — the
directory layout *is* the manifest. If the run layout changes, update `CWD_RE`.

---

## Making them presentable (roadmap)

The ANSI strip is for us; these are the upgrades to show other people. Ranked by
payoff-to-effort. The SVG swimlane (`--svg`) is the first rung and already built.

1. **SVG swimlane** *(done)* — one colored row per run, aligned columns so you can read
   *down* a position across runs. Exports clean to PNG for slides. Colors match the
   glyph legend.
2. **Phase bands** — shade the locate/implement/verify segments as background blocks
   instead of single `│`/`‖` marks. Makes "D's locate phase is longer" a visual area,
   not a counted marker. (Segment boundaries already computed in `metrics()`.)
3. **The money shot — normalized aggregate view.** Per condition, bin every run's steps
   into normalized time (0–1) and stack tool-type density. Put A and D side by side:
   the reflexive grep-after-tyf shows up as a *population* pattern (grep mass right
   after the tyf spike at t≈0), not an anecdote. This is the one chart that makes the
   finding undeniable to an audience — build it once N is large enough to average.
4. **Hover-to-command HTML** — same swimlane as inline SVG in a single self-contained
   HTML file; hovering a tile shows the actual command. Good for reviewers who want to
   drill in without reading raw JSONL. Keep it dependency-light (inline `<title>` tags
   already give native tooltips — nearly free).
5. **Summary sidebar** — the mechanism metrics as a small aligned table beside the
   lanes, sorted so the thrash outliers (high grep / high rereads) sort to the bottom
   and are visually obvious.

Guardrail: keep the terminal strip as the canonical, dependency-light view. The pretty
renderers read the *same* `fetch()` + `metrics()` output — don't fork the data layer.
