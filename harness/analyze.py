#!/usr/bin/env python3
"""Pilot read-out from results/results.jsonl (docs/tyf-experiment-protocol.md §8).
Median + IQR per cell, C-vs-A / C-vs-B paired by task, gate/convergence/ty split.
Directional only — pilot N is for debugging + variance, NOT tight CIs.

Usage: analyze.py [results.jsonl ...]
Multiple files are concatenated — per-invocation result files (each round-script
start writes its own timestamped jsonl) merge by just listing them / globbing.
"""
import json
import statistics as st
import sys
from collections import defaultdict

PATHS = sys.argv[1:] or ["results/results.jsonl"]
rows = [json.loads(l) for p in PATHS for l in open(p) if l.strip()]


def med_iqr(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return (None, None, None)
    n = len(xs)
    q1 = xs[n // 4] if n >= 4 else xs[0]
    q3 = xs[(3 * n) // 4] if n >= 4 else xs[-1]
    return (st.median(xs), q1, q3)


def cell_key(r):
    return (r["task"], r["cond"])


# only count converged, oracle-applied runs for token/quality medians; cap-hits
# (failure-to-converge) reported separately, never folded into the median.
cells = defaultdict(list)
for r in rows:
    cells[cell_key(r)].append(r)

print(f"# Pilot read-out — {len(rows)} runs from {', '.join(PATHS)}")
print(f"# model(s): {sorted({r.get('model') or '?' for r in rows})}")
print()
print("## Per-cell (task × cond): pass@1, input_tokens med[IQR], tool_calls, tyf, $")
hdr = f"{'task':9} {'c':1} {'n':>2} {'pass@1':>6} {'in_tok med[Q1-Q3]':>22} {'tools':>5} {'tyf':>4} {'turns':>5} {'$med':>6} {'conv':>4}"
print(hdr); print("-" * len(hdr))
for (task, cond) in sorted(cells):
    rs = cells[(task, cond)]
    conv = [r for r in rs if r.get("converged")]
    npass = sum(1 for r in rs if r.get("oracle_pass"))
    m, q1, q3 = med_iqr([r.get("input_tokens") for r in conv])
    tm, *_ = med_iqr([r.get("tool_calls_total") for r in conv])
    tyf, *_ = med_iqr([r.get("tyf_invocations") for r in conv])
    turns, *_ = med_iqr([r.get("turns") for r in conv])
    cost, *_ = med_iqr([r.get("cost_usd") for r in conv])
    fmt_tok = f"{m:.0f} [{q1:.0f}-{q3:.0f}]" if m else "-"
    print(f"{task:9} {cond:1} {len(rs):>2} {npass:>3}/{len(rs):<2} {fmt_tok:>22} "
          f"{(tm or 0):>5.0f} {(tyf or 0):>4.0f} {(turns or 0):>5.0f} "
          f"{(cost or 0):>6.3f} {len(conv):>3}/{len(rs)}")

print()
conds_present = [c for c in ("A", "B", "C", "D") if any(r["cond"] == c for r in rows)]
print(f"## Per-cond comparison (conds present: {' '.join(conds_present)}) — paired by task")
print("   pass@1 and median input_tokens per cond; token deltas vs A (negative = cheaper)")
cols = "".join(f" {c+' pass':>6} {c+' tok':>9} |" for c in conds_present)
deltas = "".join(f" {'Δ'+c+'-A':>8}" for c in conds_present if c != "A")
hdr2 = f"{'task':9} |{cols}{deltas}"
print(hdr2); print("-" * len(hdr2))
def tok(x): return x[2] if x and x[2] else None
for task in sorted({r["task"] for r in rows}):
    out = {}
    for cond in conds_present:
        rs = [r for r in rows if r["task"] == task and r["cond"] == cond]
        conv = [r for r in rs if r.get("converged")]
        p = sum(1 for r in rs if r.get("oracle_pass"))
        m, *_ = med_iqr([r.get("input_tokens") for r in conv])
        out[cond] = (p, len(rs), m)
    line = f"{task:9} |"
    for c in conds_present:
        x = out.get(c)
        line += f" {(f'{x[0]}/{x[1]}' if x else '-'):>6} {(f'{tok(x):.0f}' if tok(x) else '-'):>9} |"
    a = out.get("A")
    for c in conds_present:
        if c == "A":
            continue
        d = (tok(out.get(c)) - tok(a)) if tok(out.get(c)) and tok(a) else None
        line += f" {(f'{d:+.0f}' if d is not None else '-'):>8}"
    print(line)

print()
print("## Integrity / diagnostics")
gate_bad = [r for r in rows if r.get("gate") not in (None, "ok")]
caps = [r for r in rows if not r.get("converged")]
tamper = [r for r in rows if r.get("test_tampered")]
degraded = [r for r in rows if r.get("ty_status") == "degraded"]
print(f"  gate warnings (B/C no-tyf or A-has-tyf): {len(gate_bad)}"
      + (f"  -> {[(r['task'],r['cond'],r['rep'],r['gate']) for r in gate_bad]}" if gate_bad else ""))
print(f"  non-converged (cap/timeout, excluded from medians): {len(caps)}")
print(f"  test-tampered (flag only; tests restored at scoring): {len(tamper)}")
print(f"  ty_status=degraded runs: {len(degraded)}")
print(f"  regression failures (pass_to_pass not green): "
      f"{sum(1 for r in rows if not r.get('regression_ok'))}")
# floored = no arm passed on the whole task -> non-discriminating. A thin n
# (fewer reps than the matrix) means FLOOR_ABORT skipped the rest of that task.
floored = []
for task in sorted({r["task"] for r in rows}):
    trs = [r for r in rows if r["task"] == task]
    if trs and not any(r.get("oracle_pass") for r in trs):
        floored.append((task, len(trs), "".join(sorted({r["cond"] for r in trs}))))
print(f"  floored tasks (no arm passed; thin n = pilot-aborted): {len(floored)}"
      + (f"  -> {floored}" if floored else ""))
