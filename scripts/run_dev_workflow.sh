#!/usr/bin/env bash
#
# Orchestrate the local RexLit ingest → index → API/UI workflow.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DOCS_PATH="${DOCS_PATH:-${REPO_ROOT}/juul_docs}"
MANIFEST_PATH="${MANIFEST_PATH:-${REPO_ROOT}/case-manifest.jsonl}"
REXLIT_BIN="${REXLIT_BIN:-rexlit}"
REXLIT_HOME="${REXLIT_HOME:-$HOME/.local/share/rexlit}"
API_DIR="${API_DIR:-${REPO_ROOT}/api}"
UI_DIR="${UI_DIR:-${REPO_ROOT}/ui}"
API_COMMAND="${API_COMMAND:-bun run index.ts}"
UI_COMMAND="${UI_COMMAND:-bun run dev}"
TMUX_SESSION_NAME="${TMUX_SESSION_NAME:-rexlit-dev}"

log() {
  printf "\n[%s] %s\n" "$(date '+%H:%M:%S')" "$*"
}

cleanup_redaction_plans() {
  if [[ "${CLEAN_REDACTION_PLANS:-1}" != "1" ]]; then
    log "Skipping redaction plan cleanup (CLEAN_REDACTION_PLANS=0)."
    return
  fi

  if [[ ! -d "$DOCS_PATH" ]]; then
    log "Document path '$DOCS_PATH' not found; nothing to clean."
    return
  fi

  mapfile -t plans < <(find "$DOCS_PATH" -type f -name "*.redaction-plan.enc" 2>/dev/null)
  if (( ${#plans[@]} == 0 )); then
    log "No existing redaction plan artifacts detected."
    return
  fi

  log "Removing ${#plans[@]} stale redaction plan file(s)..."
  for plan in "${plans[@]}"; do
    rm -f "$plan"
  done
}

run_ingest() {
  if [[ "${SKIP_INGEST:-0}" == "1" ]]; then
    log "Skipping ingest (SKIP_INGEST=1)."
    return
  fi

  mkdir -p "$(dirname "$MANIFEST_PATH")"
  log "Running ingest for ${DOCS_PATH} → ${MANIFEST_PATH}..."
  EDITOR="${EDITOR:-true}" \
  REXLIT_HOME="$REXLIT_HOME" \
    "$REXLIT_BIN" ingest run "$DOCS_PATH" \
      --manifest "$MANIFEST_PATH" \
      --skip-redaction \
      --skip-plan-validation \
      --skip-pack
}

rebuild_index() {
  if [[ "${SKIP_INDEX_REBUILD:-0}" == "1" ]]; then
    log "Skipping index rebuild (SKIP_INDEX_REBUILD=1)."
    return
  fi

  log "Rebuilding Tantivy index from ${DOCS_PATH}..."
  REXLIT_HOME="$REXLIT_HOME" \
    "$REXLIT_BIN" index build "$DOCS_PATH" --rebuild
}

launch_tmux() {
  if [[ "${START_SERVERS:-1}" != "1" ]]; then
    log "START_SERVERS=0, skipping API/UI launch."
    return
  fi

  if ! command -v tmux >/dev/null 2>&1; then
    log "tmux is not installed; cannot launch multi-terminal session."
    log "Start servers manually:\n  (API) cd ${API_DIR} && ${API_COMMAND}\n  (UI)  cd ${UI_DIR} && ${UI_COMMAND}"
    return
  fi

  if tmux has-session -t "$TMUX_SESSION_NAME" 2>/dev/null; then
    log "tmux session '${TMUX_SESSION_NAME}' already exists. Attach with: tmux attach -t ${TMUX_SESSION_NAME}"
    return
  fi

  log "Starting tmux session '${TMUX_SESSION_NAME}' for API/UI..."
  tmux new-session -d -s "$TMUX_SESSION_NAME" -c "$API_DIR" "$API_COMMAND"
  tmux rename-window -t "$TMUX_SESSION_NAME:0" "api"
  tmux new-window -t "$TMUX_SESSION_NAME:1" -n "ui" -c "$UI_DIR" "$UI_COMMAND"

  log "tmux session ready. Attach with: tmux attach -t ${TMUX_SESSION_NAME}"
}

main() {
  log "REPO_ROOT=${REPO_ROOT}"
  log "REXLIT_HOME=${REXLIT_HOME}"

  cleanup_redaction_plans
  run_ingest
  rebuild_index
  launch_tmux
}

main "$@"
