#!/usr/bin/env bash
# One experiment cell: fresh-copy a fixture, run Claude Code headless, capture
# the transcript. Does NOT score (see score.sh).
#   run.sh <task> <cond> <rep>
# Env: DRY=1 -> no claude call; simulate a perfect agent (apply solution.patch)
#               and emit a canned transcript, for $0 plumbing tests.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

TASK="${1:?task}"; COND="${2:?cond A|B|C}"; REP="${3:?rep}"
FIX="$ROOT/fixtures/$TASK/$COND"
RUN="$ROOT/runs/$TASK/$COND/rep$REP"
HOLD="$ROOT/holdout/$TASK"
[ -d "$FIX" ] || { echo "no fixture: $FIX" >&2; exit 2; }

# --- fresh, byte-identical working copy every run (§6) ---
rm -rf "$RUN"; mkdir -p "$(dirname "$RUN")"
cp -a "$FIX" "$RUN"

# --- environment: out-of-tree venv on PATH for ALL conditions (python/pytest/ty);
#     tyf binary on PATH for B/C ONLY (the present/absent lever) ---
RUN_PATH="$VENV/bin:$PATH"
[ "$COND" != "A" ] && RUN_PATH="$ROOT/bin:$RUN_PATH"
export VIRTUAL_ENV="$VENV"

PROMPT="$(cat "$HOLD/prompt.txt")"
mkdir -p "$RUN"

if [ "${DRY:-0}" = "1" ]; then
    log "[DRY] $TASK/$COND/rep$REP — simulating perfect agent"
    # apply the held-out solution to mimic a correct fix (DRY only — never in real runs)
    git -C "$RUN" apply "$HOLD/solution.patch" 2>/dev/null \
        || patch -p1 -d "$RUN" < "$HOLD/solution.patch" 2>/dev/null || true
    TYF_LINE=""
    if [ "$COND" != "A" ]; then
        TYF_LINE='{"type":"assistant","message":{"content":[{"type":"tool_use","id":"t1","name":"Bash","input":{"command":"tyf show some_symbol"}}],"usage":{}}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"# Definition\\nfoo.py:1:1"}]}}'
    fi
    {
      echo '{"type":"system","subtype":"init"}'
      [ -n "$TYF_LINE" ] && echo "$TYF_LINE"
      echo '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"r1","name":"Read","input":{"file_path":"x.py"}}],"usage":{}}}'
      echo '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"r1","content":"def x(): pass"}]}}'
      echo '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"e1","name":"Edit","input":{}}],"usage":{}}}'
      echo '{"type":"result","subtype":"success","is_error":false,"terminal_reason":"completed","stop_reason":"end_turn","num_turns":3,"total_cost_usd":0.0,"usage":{"input_tokens":100,"cache_read_input_tokens":2000,"cache_creation_input_tokens":500,"output_tokens":200},"modelUsage":{"DRY-canned":{}},"permission_denials":[],"result":"Applied the fix (DRY)."}'
    } > "$RUN/transcript.jsonl"
    echo "0" > "$RUN/exit_code"
    exit 0
fi

# --- B/C: warm the daemon once (constant policy across all timed runs) ---
if [ "$COND" != "A" ]; then
    PATH="$RUN_PATH" "$TYF_BIN" daemon restart --workspace "$RUN" >/dev/null 2>&1 || true
    PATH="$RUN_PATH" "$TYF_BIN" list --workspace "$RUN" "$(basename "$(find "$RUN" -name '*.py' | head -1)")" >/dev/null 2>&1 || true
fi

# --- headless run, fresh session, no --resume; cwd=RUN so RUN/CLAUDE.md loads ---
log "$TASK/$COND/rep$REP — model=$MODEL wall=${WALL}s tyf=$([ "$COND" = A ] && echo absent || echo present)"
set +e
( cd "$RUN" && timeout "$WALL" env PATH="$RUN_PATH" \
    claude -p "$PROMPT" --model "$MODEL" "${CLAUDE_COMMON[@]}" \
    > "$RUN/transcript.jsonl" 2> "$RUN/claude.err" )
EC=$?
set -e
echo "$EC" > "$RUN/exit_code"
[ "$EC" -eq 124 ] && log "WALL TIMEOUT (failure-to-converge)"
log "done exit=$EC  transcript=$(wc -l < "$RUN/transcript.jsonl") lines"
