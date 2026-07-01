#!/usr/bin/env python3
"""Trajectory frames — render each run's tool sequence as a glyph strip.

Reads the tool-call order straight from introspect's materialized DuckDB (same
read-only connection the analysis notebook uses) and emits one "frame" per run:
a left-to-right strip of the tools called, split into locate / implement / verify
phases, with per-run mechanism metrics. This is the view that exposes behavior
the token/byte totals hide (e.g. reflexive grep-after-tyf, re-reading hot files).

Usage:
    python3 harness/trajectory.py                       # all runs under runs/**
    python3 harness/trajectory.py --glob '%runs/dlt-110/%'   # subset by cwd
    python3 harness/trajectory.py --conds A D           # only these conditions
    python3 harness/trajectory.py --svg frames.svg      # + presentable swimlane

Depends only on duckdb + stdlib. See docs/tyf-trajectory-frames.md for the method.
"""
from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path
import duckdb

DB = Path(os.environ.get("INTROSPECT_DB", "~/.introspect/introspect.duckdb")).expanduser()
CWD_RE = re.compile(r"runs/([\w.-]+)/([ABCD])/(rep\d+)")

# act -> (glyph, ansi, svg_color, label). Order of the classify() checks matters.
STYLE = {
    "tyf":   ("T", "96", "#00b4b4", "tyf"),
    "grep":  ("g", "33", "#c8a000", "grep (bash)"),
    "Read":  ("R", "32", "#3fa63f", "Read"),
    "Edit":  ("E", "35", "#b24bd8", "Edit"),
    "Write": ("W", "35", "#8e30b0", "Write"),
    "TEST":  ("v", "34", "#3f6ad6", "pytest"),   # 'v' renders as a check-ish tick
    "repro": ("p", "90", "#888888", "python repro"),
    "git":   (".", "90", "#bbbbbb", "git"),
    "bash":  ("b", "90", "#666666", "other bash"),
}
BASH_PATTERNS = [
    ("tyf",   re.compile(r"(^|[^\w/])tyf ")),
    ("TEST",  re.compile(r"pytest|python -m pytest|uv run pytest")),
    ("grep",  re.compile(r"\bgrep\b|\brg ")),
    ("repro", re.compile(r"python -c|uv run python|/tmp/|cat >|<<")),
    ("git",   re.compile(r"\bgit ")),
]


def classify(tool_name: str, tool_input: str) -> str:
    if tool_name != "Bash":
        return tool_name if tool_name in STYLE else "bash"
    try:
        cmd = json.loads(tool_input).get("command", "") if tool_input else ""
    except (json.JSONDecodeError, AttributeError):
        cmd = tool_input or ""
    for act, pat in BASH_PATTERNS:
        if pat.search(cmd):
            return act
    return "bash"


def read_path(tool_input: str) -> str | None:
    try:
        p = json.loads(tool_input).get("file_path", "")
    except (json.JSONDecodeError, AttributeError):
        return None
    return re.sub(r".*/((?:dlt|tests|src)/.*)", r"\1", p) if p else None


def fetch(con, glob: str, conds: set[str]):
    rows = con.execute(
        """
        SELECT ss.session_id, ss.cwd,
               tc.tool_name, tc.tool_input,
               ROW_NUMBER() OVER (PARTITION BY ss.session_id ORDER BY tc.called_at) AS i
        FROM session_stats ss JOIN tool_calls tc USING (session_id)
        WHERE ss.cwd LIKE ?
        ORDER BY ss.cwd, i
        """, [glob]).fetchall()
    runs: dict[str, dict] = {}
    for sid, cwd, tool_name, tool_input, _ in rows:
        m = CWD_RE.search(cwd or "")
        if not m:
            continue
        task, cond, rep = m.groups()
        if conds and cond not in conds:
            continue
        key = f"{task}/{cond}/{rep}"
        r = runs.setdefault(key, {"task": task, "cond": cond, "rep": rep, "seq": [], "reads": []})
        act = classify(tool_name, tool_input)
        r["seq"].append(act)
        if act == "Read":
            r["reads"].append(read_path(tool_input))
    return dict(sorted(runs.items()))


def metrics(r: dict) -> dict:
    seq = r["seq"]
    first_edit = next((i for i, a in enumerate(seq) if a == "Edit"), len(seq))
    reads = [p for p in r["reads"] if p]
    counts = {p: reads.count(p) for p in set(reads)}
    nav = next((a for a in seq if a in ("tyf", "grep", "Read")), "-")
    return {
        "locate_len": first_edit,
        "first_edit": first_edit,
        "tyf": seq.count("tyf"),
        "grep": seq.count("grep"),
        "distinct_files": len(counts),
        "max_rereads": max(counts.values(), default=0),
        "first_nav": nav,
    }


def render_ansi(runs: dict, color: bool) -> str:
    def c(act):
        g = STYLE[act][0]
        return f"\033[{STYLE[act][1]}m{g}\033[0m" if color else g
    out = ["legend: " + "  ".join(f"{STYLE[a][0]}={STYLE[a][3]}" for a in STYLE),
           "        │ first Edit   ‖ first pytest\n"]
    for key, r in runs.items():
        mk = metrics(r)
        first_test = next((i for i, a in enumerate(r["seq"]) if a == "TEST"), None)
        strip = []
        for i, a in enumerate(r["seq"]):
            if i == mk["first_edit"] and i:
                strip.append("│")
            if first_test is not None and i == first_test:
                strip.append("‖")
            strip.append(c(a))
        head = (f"{key:<16} locate={mk['locate_len']:<2} tyf={mk['tyf']} "
                f"grep={mk['grep']:<2} files={mk['distinct_files']} "
                f"rereads={mk['max_rereads']} nav1={mk['first_nav']}")
        out.append(head)
        out.append("  " + " ".join(strip) + "\n")
    return "\n".join(out)


def render_svg(runs: dict, path: Path):
    cw, rh, pad, lab = 13, 26, 8, 150
    maxn = max((len(r["seq"]) for r in runs.values()), default=1)
    W, H = lab + maxn * cw + pad, pad + len(runs) * rh + 40
    el = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="monospace" font-size="11">']
    el.append(f'<rect width="{W}" height="{H}" fill="#fafafa"/>')
    for row, (key, r) in enumerate(runs.items()):
        y = pad + row * rh
        el.append(f'<text x="4" y="{y+rh//2+4}" fill="#222">{key}</text>')
        for i, a in enumerate(r["seq"]):
            glyph, _, fill, _ = STYLE[a]
            x = lab + i * cw
            el.append(f'<rect x="{x}" y="{y+3}" width="{cw-2}" height="{rh-8}" rx="2" fill="{fill}"/>')
            el.append(f'<text x="{x+(cw-2)/2}" y="{y+rh//2+4}" text-anchor="middle" fill="#fff">{glyph}</text>')
    lx = 4
    for a in STYLE:
        glyph, _, fill, label = STYLE[a]
        el.append(f'<rect x="{lx}" y="{H-24}" width="11" height="11" rx="2" fill="{fill}"/>')
        el.append(f'<text x="{lx+15}" y="{H-15}" fill="#333">{glyph} {label}</text>')
        lx += 22 + len(label) * 6.4
    el.append("</svg>")
    path.write_text("\n".join(el))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--glob", default="%tyftest/runs/%", help="cwd LIKE pattern")
    ap.add_argument("--conds", nargs="*", default=[], help="filter conditions e.g. A D")
    ap.add_argument("--svg", type=Path, help="also write an SVG swimlane here")
    ap.add_argument("--no-color", action="store_true")
    a = ap.parse_args()
    if not DB.exists():
        sys.exit(f"introspect DB not found: {DB} (set INTROSPECT_DB)")
    con = duckdb.connect(str(DB), read_only=True)
    runs = fetch(con, a.glob, set(a.conds))
    if not runs:
        sys.exit("no matching runs")
    print(render_ansi(runs, color=not a.no_color and sys.stdout.isatty()))
    if a.svg:
        render_svg(runs, a.svg)
        print(f"\nwrote {a.svg}  ({len(runs)} runs)")


if __name__ == "__main__":
    main()
