#!/usr/bin/env python3
"""Detect whether a headless `claude -p` run was disrupted mid-session by a
transient API failure (e.g. 529 Overloaded) — including the case where the CLI
auto-resumed and finished "successfully".

Why it matters for the experiment: a resumed run is not comparable to a clean
one (interrupted trajectory, per-segment stats — see
docs/changes/2026-07-02-round4-data-collection-issues.md issue 1, A-rep4).
Such cells must be discarded and re-run fresh so every scored run had
identical conditions.

Prints {"interrupted": bool, "reason": "...", "result_events": N} to stdout.
Exit 0 if interrupted, 1 if clean. NOTE: run limit_check.py FIRST — a
usage-limit death is handled differently (wait for reset, not quick retry).

Signals (any one triggers interrupted=True):
  * more than one `result` event (or more than one system/init) in the
    transcript — the fingerprint of an in-place auto-resume
  * any `result` event whose text looks like an API error
    ("API Error", "Overloaded", 5xx)
"""
import json
import re
import sys

# anchored: the CLI emits the raw error AS the result text; an agent's real
# final answer merely *mentioning* "API error" must not trigger a discard
API_ERR_RE = re.compile(r"\s*(API Error\b|5\d\d\s+Overloaded\b)",
                        re.IGNORECASE)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: interruption_check.py <transcript.jsonl>")
    results = 0
    inits = 0
    api_err = ""
    try:
        fh = open(sys.argv[1], encoding="utf-8", errors="replace")
    except OSError:
        json.dump({"interrupted": False, "reason": "no_transcript",
                   "result_events": 0}, sys.stdout)
        print()
        sys.exit(1)
    with fh:
        for line in fh:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = ev.get("type")
            if t == "result":
                results += 1
                text = ev.get("result", "") or ""
                if API_ERR_RE.match(text):
                    api_err = text.strip()[:200]
            elif t == "system" and ev.get("subtype") == "init":
                inits += 1

    if results > 1 or inits > 1:
        reason = f"resumed_mid_session ({inits} inits, {results} result events)"
        if api_err:
            reason += f"; api_error: {api_err}"
        out = {"interrupted": True, "reason": reason, "result_events": results}
    elif api_err:
        out = {"interrupted": True, "reason": f"api_error: {api_err}",
               "result_events": results}
    else:
        out = {"interrupted": False, "reason": "", "result_events": results}
    json.dump(out, sys.stdout)
    print()
    sys.exit(0 if out["interrupted"] else 1)


if __name__ == "__main__":
    main()
