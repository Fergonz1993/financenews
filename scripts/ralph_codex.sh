#!/usr/bin/env bash
set -euo pipefail

AUTO_STASH="${AUTO_STASH:-0}"
ALLOW_DIRTY="${ALLOW_DIRTY:-1}"
MAX_ITERS="${MAX_ITERS:-${MAX_ITERATIONS:-3}}"
VERIFY_CMD="${VERIFY_CMD:-bun run typecheck}"
MODEL="${MODEL:-gpt-5.2-codex}"
SKIP_CODEX="${SKIP_CODEX:-0}"
TASK_FILE="${TASK_FILE:-TASK.md}"
FEEDBACK_FILE="${FEEDBACK_FILE:-RALPH_FEEDBACK.md}"
LOG_DIR="${LOG_DIR:-.ralph}"
COMPOUND_SCRIPT="${COMPOUND_SCRIPT:-$HOME/.codex/scripts/compound-notes.sh}"
PROJECT_LABEL="${PROJECT_LABEL:-financenews}"
FOCUS_LABEL="${FOCUS_LABEL:-ralph-loop reliability acceleration}"

if ! [[ "$MAX_ITERS" =~ ^[1-9][0-9]*$ ]]; then
  echo "MAX_ITERS must be a positive integer. Received: $MAX_ITERS"
  exit 1
fi

mkdir -p "$LOG_DIR"
META_LOG="$LOG_DIR/meta_lessons.md"
echo "# Ralph Meta Lessons" >"$META_LOG"
echo "- started_at: $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >>"$META_LOG"

EXIT_OUTCOME="ralph-loop interrupted"
STASH_REF=""

log_compound() {
  if [ -x "$COMPOUND_SCRIPT" ]; then
    "$COMPOUND_SCRIPT" "$@" >/dev/null 2>&1 || true
  fi
}

append_meta_lesson() {
  local iteration="$1"
  local phase="$2"
  local lesson="$3"
  local entry="iteration ${iteration}/${MAX_ITERS} [${phase}] ${lesson}"
  echo "- ${entry}" >>"$META_LOG"
  log_compound log "Ralph meta-lesson: ${entry}"
  log_compound promote "ralph-loop-meta-lessons" "$lesson"
}

classify_failure_lesson() {
  local verify_file="$1"
  if grep -Eqi "command not found|No such file or directory|ModuleNotFoundError|ImportError" "$verify_file"; then
    echo "Reliability starts with explicit runtime contracts; pin commands to project-owned toolchains and paths."
    return
  fi
  if grep -Eqi "mypy|ruff|eslint|lint|typecheck|tsc" "$verify_file"; then
    echo "Static checks are design feedback, not ceremony; tightening interfaces early reduces operational failures."
    return
  fi
  if grep -Eqi "FAILED|AssertionError|Traceback| E " "$verify_file"; then
    echo "A failing check is a missing specification; codify it into deterministic tests to prevent recurrence."
    return
  fi
  echo "Fast, measurable verify loops compound reliability faster than intuition-driven iteration."
}

cleanup() {
  if [ -n "${STASH_REF:-}" ]; then
    echo
    echo "Ralph auto-stashed this tree as: ${STASH_REF}"
    echo "Restore with: git stash apply ${STASH_REF}"
  fi
  log_compound close-auto "$EXIT_OUTCOME"
}
trap cleanup EXIT

ensure_file() {
  local file="$1"
  if [ ! -f "$file" ]; then
    echo "Required file missing: $file"
    exit 1
  fi
}

tracked_or_warn() {
  local file="$1"
  if ! git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
    echo "warning: $file is not tracked yet; AUTO_STASH=1 may hide it."
    return 1
  fi
  return 0
}

maybe_stash_dirty_tree() {
  if [ -z "$(git status --porcelain)" ]; then
    return
  fi

  if [ "$AUTO_STASH" != "1" ]; then
    if [ "$ALLOW_DIRTY" = "1" ]; then
      echo "Working tree is dirty; continuing with ALLOW_DIRTY=1 (no auto-stash)."
      return
    fi
    echo "Working tree is dirty. Re-run with AUTO_STASH=1, set ALLOW_DIRTY=1, or clean/stash manually."
    exit 1
  fi

  tracked_or_warn "$TASK_FILE" || {
    echo "Cannot AUTO_STASH safely while $TASK_FILE is untracked."
    exit 1
  }
  tracked_or_warn "scripts/ralph_codex.sh" || {
    echo "Cannot AUTO_STASH safely while scripts/ralph_codex.sh is untracked."
    exit 1
  }
  tracked_or_warn ".gitignore" || {
    echo "Cannot AUTO_STASH safely while .gitignore is untracked."
    exit 1
  }

  local name="ralph-preflight-$(date -u +%Y%m%dT%H%M%SZ)"
  git stash push -u -m "$name" >/dev/null
  STASH_REF="$(git stash list | head -n 1 | cut -d: -f1)"
  echo "$STASH_REF" >"$LOG_DIR/preflight_stash_ref.txt"
  echo "Auto-stashed dirty tree as ${STASH_REF}"
}

run_verify() {
  set +e
  bash -lc "$VERIFY_CMD" >"$LOG_DIR/verify.out" 2>&1
  code=$?
  set -e
  return $code
}

snapshot_repo_state() {
  local prefix="$1"
  git diff --binary >"$LOG_DIR/${prefix}_worktree.patch" || true
  git diff --cached --binary >"$LOG_DIR/${prefix}_index.patch" || true
  git ls-files --others --exclude-standard | sort >"$LOG_DIR/${prefix}_untracked.txt" || true
}

iteration_produced_changes() {
  local before="$1"
  local after="$2"
  if ! cmp -s "$LOG_DIR/${before}_worktree.patch" "$LOG_DIR/${after}_worktree.patch"; then
    return 0
  fi
  if ! cmp -s "$LOG_DIR/${before}_index.patch" "$LOG_DIR/${after}_index.patch"; then
    return 0
  fi
  if ! cmp -s "$LOG_DIR/${before}_untracked.txt" "$LOG_DIR/${after}_untracked.txt"; then
    return 0
  fi
  return 1
}

if [ "$SKIP_CODEX" != "1" ] && ! command -v codex >/dev/null 2>&1; then
  echo "codex not found in PATH"
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Ralph loop requires a Git repository"
  exit 1
fi

ensure_file "$TASK_FILE"
ensure_file "scripts/ralph_codex.sh"
ensure_file ".gitignore"
tracked_or_warn "$TASK_FILE" || true
tracked_or_warn "scripts/ralph_codex.sh" || true

log_compound start-auto "$PROJECT_LABEL" "$FOCUS_LABEL" "$(pwd)"
log_compound ingest-history
append_meta_lesson "0" "preflight" "Every iteration starts by making constraints explicit: objective, verify command, and rollback-safe context."

maybe_stash_dirty_tree

echo "# Ralph Feedback" >"$FEEDBACK_FILE"
echo "- Start: $(date -u +'%Y-%m-%dT%H:%M:%SZ')" >>"$FEEDBACK_FILE"
echo "- VERIFY_CMD: $VERIFY_CMD" >>"$FEEDBACK_FILE"

for i in $(seq 1 "$MAX_ITERS"); do
  echo
  echo "=== Ralph iteration $i/$MAX_ITERS ==="
  append_meta_lesson "$i" "start" "Scope one change batch at a time, then verify before expanding blast radius."

  snapshot_repo_state "before_$i"

  {
    echo "# Ralph Feedback (iteration $i)"
    echo
    echo "## What to do"
    echo "- Read $TASK_FILE and follow it."
    echo "- Read this file ($FEEDBACK_FILE) for latest failures."
    echo "- Make the smallest change that makes verification pass."
    echo "- Run verification before stopping: $VERIFY_CMD"
    echo
    echo "## Current repo status"
    echo '```'
    git status -sb
    echo '```'
    echo
    echo "## Last verify output (if any)"
    if [ -f "$LOG_DIR/verify.out" ]; then
      echo '```'
      tail -n 200 "$LOG_DIR/verify.out"
      echo '```'
    fi
  } >"$FEEDBACK_FILE"

  if [ "$SKIP_CODEX" = "1" ]; then
    echo "SKIP_CODEX=1 set; skipping codex exec for iteration $i." >"$LOG_DIR/codex_progress_$i.log"
    echo "SKIP_CODEX=1" >"$LOG_DIR/codex_last_message_$i.txt"
  else
    codex exec --full-auto --sandbox workspace-write -m "$MODEL" \
      "Fix the repo to satisfy $TASK_FILE. Read $TASK_FILE and $FEEDBACK_FILE. \
Run '$VERIFY_CMD' and iterate until it passes. Stop when done." \
      1>"$LOG_DIR/codex_last_message_$i.txt" \
      2>"$LOG_DIR/codex_progress_$i.log" || true
  fi

  if run_verify; then
    append_meta_lesson "$i" "pass" "Done is evidence-based: passing verification is the only valid completion signal."
    EXIT_OUTCOME="ralph-loop success on iteration $i"
    echo "VERIFY PASSED on iteration $i"
    git status -sb
    exit 0
  fi

  echo "VERIFY FAILED on iteration $i"
  echo "Last verify output: $LOG_DIR/verify.out"
  append_meta_lesson "$i" "fail" "$(classify_failure_lesson "$LOG_DIR/verify.out")"

  snapshot_repo_state "after_$i"
  if ! iteration_produced_changes "before_$i" "after_$i"; then
    append_meta_lesson "$i" "stall" "When an iteration produces no diff and verification still fails, change the hypothesis before repeating."
    EXIT_OUTCOME="ralph-loop stalled on iteration $i"
    echo "No repo-state changes detected during this iteration; stopping to avoid a non-productive loop."
    exit 2
  fi
done

append_meta_lesson "$MAX_ITERS" "limit" "Iteration caps protect system stability; unresolved work must be re-scoped with new evidence."
EXIT_OUTCOME="ralph-loop reached MAX_ITERS=$MAX_ITERS without passing verify"
echo "Reached MAX_ITERS=$MAX_ITERS without passing VERIFY_CMD."
exit 3
