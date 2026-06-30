#!/usr/bin/env python3
"""Pilot read-out from results/results.jsonl (docs/tyf-experiment-protocol.md §8).
Median + IQR per cell, C-vs-A / C-vs-B paired by task, gate/convergence/ty split.
Directional only — pilot N is for debugging + variance, NOT tight CIs.

Usage: analyze.py [results.jsonl]
"""
import json
import statistics as st
import sys
from collections import defaultdict

PATH = sys.argv[1] if len(sys.argv) > 1 else "results/results.jsonl"
rows = [json.loads(l) for l in open(PATH) if l.strip()]


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

print(f"# Pilot read-out — {len(rows)} runs from {PATH}")
print(f"# model(s): {sorted({r.get('model') for r in rows})}")
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
print("## C vs B (instruction lines) and C vs A (whole package) — paired by task")
print("   pass@1 sum and median input_tokens per cond, per task")
hdr2 = f"{'task':9} | {'A pass':>6} {'A tok':>8} | {'B pass':>6} {'B tok':>8} | {'C pass':>6} {'C tok':>8} | {'C-A tok':>8} {'C-B tok':>8}"
print(hdr2); print("-" * len(hdr2))
for task in sorted({r["task"] for r in rows}):
    out = {}
    for cond in ("A", "B", "C"):
        rs = [r for r in rows if r["task"] == task and r["cond"] == cond]
        conv = [r for r in rs if r.get("converged")]
        p = sum(1 for r in rs if r.get("oracle_pass"))
        m, *_ = med_iqr([r.get("input_tokens") for r in conv])
        out[cond] = (p, len(rs), m)
    a, b, c = out.get("A"), out.get("B"), out.get("C")
    def tok(x): return x[2] if x and x[2] else None
    ca = (tok(c) - tok(a)) if tok(c) and tok(a) else None
    cb = (tok(c) - tok(b)) if tok(c) and tok(b) else None
    def f(x): return f"{x[0]}/{x[1]}" if x else "-"
    def g(x): return f"{tok(x):.0f}" if tok(x) else "-"
    print(f"{task:9} | {f(a):>6} {g(a):>8} | {f(b):>6} {g(b):>8} | {f(c):>6} {g(c):>8} "
          f"| {(f'{ca:+.0f}' if ca is not None else '-'):>8} {(f'{cb:+.0f}' if cb is not None else '-'):>8}")

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
