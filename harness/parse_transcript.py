#!/usr/bin/env python3
"""Parse a `claude -p --output-format stream-json --verbose` transcript into the
metrics from docs/tyf-experiment-protocol.md §4. Emits one JSON object on stdout.

Usage: parse_transcript.py <transcript.jsonl>
Robust to partial/garbled lines (skips non-JSON).
"""
import json
import sys


def load_events(path):
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def is_tyf(cmd):
    if not isinstance(cmd, str):
        return False
    c = cmd.strip()
    # match `tyf ...`, `bin/tyf ...`, or an absolute path ending in /tyf
    first = c.split()[0] if c.split() else ""
    return first == "tyf" or first.endswith("/tyf") or " tyf " in f" {c} "


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: parse_transcript.py <transcript.jsonl>")
    events = load_events(sys.argv[1])

    tool_counts = {"Read": 0, "Grep": 0, "Glob": 0, "Edit": 0, "Write": 0,
                   "Bash": 0, "Bash_tyf": 0, "other": 0}
    tyf_invocations = 0
    id_to_tool = {}        # tool_use_id -> tool name (for matching results)
    id_is_read = {}        # tool_use_id -> bool
    bytes_read = 0

    result = None
    for ev in events:
        t = ev.get("type")
        if t == "assistant":
            for blk in ev.get("message", {}).get("content", []):
                if blk.get("type") != "tool_use":
                    continue
                name = blk.get("name", "other")
                tid = blk.get("id")
                inp = blk.get("input", {}) or {}
                id_to_tool[tid] = name
                if name == "Bash" and is_tyf(inp.get("command", "")):
                    tool_counts["Bash_tyf"] += 1
                    tyf_invocations += 1
                elif name in tool_counts:
                    tool_counts[name] += 1
                else:
                    tool_counts["other"] += 1
                id_is_read[tid] = (name == "Read")
        elif t == "user":
            for blk in ev.get("message", {}).get("content", []):
                if blk.get("type") != "tool_result":
                    continue
                tid = blk.get("tool_use_id")
                if not id_is_read.get(tid):
                    continue
                content = blk.get("content", "")
                if isinstance(content, list):
                    content = "".join(
                        c.get("text", "") for c in content if isinstance(c, dict))
                bytes_read += len(content.encode("utf-8", errors="replace")) \
                    if isinstance(content, str) else 0
        elif t == "result":
            result = ev

    out = {
        "parsed_ok": result is not None,
        "tool_counts": tool_counts,
        "tool_calls_total": sum(tool_counts.values()),
        "tyf_invocations": tyf_invocations,
        "bytes_read": bytes_read,
    }
    if result is not None:
        u = result.get("usage", {}) or {}
        in_tok = (u.get("input_tokens", 0)
                  + u.get("cache_creation_input_tokens", 0)
                  + u.get("cache_read_input_tokens", 0))
        out.update({
            "input_tokens": in_tok,
            "input_tokens_uncached": u.get("input_tokens", 0),
            "output_tokens": u.get("output_tokens", 0),
            "cost_usd": result.get("total_cost_usd"),
            "turns": result.get("num_turns"),
            "subtype": result.get("subtype"),
            "is_error": result.get("is_error"),
            "terminal_reason": result.get("terminal_reason"),
            "stop_reason": result.get("stop_reason"),
            "model": next(iter(result.get("modelUsage", {})), None),
            "permission_denials": len(result.get("permission_denials", []) or []),
            "final_answer": result.get("result", ""),
        })
        # convergence flag: True if the run ended cleanly (not budget/turn capped)
        out["converged"] = (result.get("subtype") == "success"
                            and not result.get("is_error"))
    else:
        out["converged"] = False
    json.dump(out, sys.stdout)
    print()


if __name__ == "__main__":
    main()
