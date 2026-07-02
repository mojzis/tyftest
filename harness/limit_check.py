#!/usr/bin/env python3
"""Detect whether a headless `claude -p` run ended because the Claude usage
limit was hit, and if so extract the reset time (epoch seconds).

Reads a transcript.jsonl (and, if present, the sibling claude.err). Prints one
JSON object to stdout:
  {"limited": bool, "resets_at": <epoch|null>, "source": "...", "message": "..."}
Exit code 0 if limited, 1 if not — so callers can branch on the exit status.

Signals (any one triggers limited=True):
  * a `result` event whose `result` text (the final_answer) matches a known
    limit message:
      - "usage limit reached", optionally suffixed "|<epoch>"       (old CLI)
      - "You've hit your session limit · resets 4:40pm (Europe/Prague)"
        (current CLI; observed in round-3 dlt-120 run1 — resets time is
        local wall-clock in the parenthesized IANA zone)
  * a `rate_limit_event` with rate_limit_info.status == "rejected"
  * the same limit text anywhere in claude.err

Reset epoch priority: explicit "|<epoch>" > rejected rate_limit_event's
resetsAt > wall-clock parse of "resets H[:MM]am/pm (Zone)" (next occurrence
of that time in that zone). null if none parse — the caller should fall back
to a fixed wait.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:          # py<3.9 — fall back to local time
    ZoneInfo = None

# "Claude AI usage limit reached|1782859800"  (epoch optional)
OLD_LIMIT_RE = re.compile(r"usage limit reached(?:\s*\|\s*(\d+))?", re.IGNORECASE)
# "You've hit your session limit · resets 4:40pm (Europe/Prague)"
NEW_LIMIT_RE = re.compile(r"hit your [\w -]{0,20}limit", re.IGNORECASE)
# "resets 4:40pm (Europe/Prague)" — minutes, am/pm and zone all optional
RESET_RE = re.compile(
    r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)?(?:\s*\(([^)]+)\))?",
    re.IGNORECASE)


def parse_reset_walltime(text):
    """Epoch of the NEXT occurrence of the 'resets H[:MM]am/pm (Zone)' time.
    Returns None if the text has no parseable reset time."""
    m = RESET_RE.search(text)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower()
    if ampm == "pm" and hh != 12:
        hh += 12
    elif ampm == "am" and hh == 12:
        hh = 0
    if hh > 23 or mm > 59:
        return None
    tz = None
    if m.group(4) and ZoneInfo is not None:
        try:
            tz = ZoneInfo(m.group(4).strip())
        except Exception:
            tz = None
    now = datetime.now(tz)          # tz=None -> naive local; timestamp() is local
    cand = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if cand <= now:
        cand += timedelta(days=1)
    return int(cand.timestamp())


def check_text(text):
    """(matched, epoch_or_None, matched_snippet) for one blob of text."""
    m = OLD_LIMIT_RE.search(text)
    if m:
        return True, (int(m.group(1)) if m.group(1) else None), m.group(0)
    m = NEW_LIMIT_RE.search(text)
    if m:
        return True, parse_reset_walltime(text), m.group(0)
    return False, None, ""


def scan(path):
    limited = False
    source = None
    message = ""
    epoch_from_answer = None
    epoch_from_rate = None

    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return None
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
            if t == "rate_limit_event":
                info = ev.get("rate_limit_info", {}) or {}
                if info.get("status") == "rejected":
                    limited = True
                    source = source or "rate_limit_event"
                    ra = info.get("resetsAt")
                    if isinstance(ra, (int, float)):
                        epoch_from_rate = int(ra)
            elif t == "result":
                text = ev.get("result", "") or ""
                hit, epoch, _ = check_text(text)
                if hit:
                    limited = True
                    source = "final_answer"
                    message = text.strip()
                    if epoch is not None:
                        epoch_from_answer = epoch
    return limited, source, message, epoch_from_answer, epoch_from_rate


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: limit_check.py <transcript.jsonl>")
    path = sys.argv[1]
    res = scan(path)
    if res is None:
        json.dump({"limited": False, "resets_at": None,
                   "source": "no_transcript", "message": ""}, sys.stdout)
        print()
        sys.exit(1)
    limited, source, message, epoch_answer, epoch_rate = res

    # also check the sibling claude.err (limit message can land on stderr)
    err = os.path.join(os.path.dirname(path), "claude.err")
    if os.path.exists(err):
        try:
            with open(err, encoding="utf-8", errors="replace") as fh:
                blob = fh.read()
            hit, epoch, snippet = check_text(blob)
            if hit:
                limited = True
                source = source or "claude.err"
                if not message:
                    message = snippet
                if epoch is not None and epoch_answer is None:
                    epoch_answer = epoch
        except OSError:
            pass

    resets_at = epoch_answer if epoch_answer is not None else epoch_rate
    json.dump({"limited": limited, "resets_at": resets_at,
               "source": source, "message": message}, sys.stdout)
    print()
    sys.exit(0 if limited else 1)


if __name__ == "__main__":
    main()
