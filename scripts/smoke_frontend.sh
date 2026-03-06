#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3100}"
SMOKE_WAIT_SECONDS="${SMOKE_WAIT_SECONDS:-90}"
SMOKE_LOG_DIR="${SMOKE_LOG_DIR:-$PROJECT_ROOT/.tmp/smoke}"
SMOKE_PORT_SCAN_LIMIT="${SMOKE_PORT_SCAN_LIMIT:-20}"

mkdir -p "$SMOKE_LOG_DIR"

BUILD_LOG="$SMOKE_LOG_DIR/build.log"
FRONTEND_LOG="$SMOKE_LOG_DIR/frontend.log"

cleanup() {
  set +e
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

wait_until_ready() {
  local url="$1"
  local label="$2"
  local max_attempts="$3"

  local attempt=1
  while (( attempt <= max_attempts )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    ((attempt += 1))
  done

  echo "ERROR: ${label} not ready at ${url} after ${max_attempts}s"
  return 1
}

port_in_use() {
  local host="$1"
  local port="$2"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -n -P >/dev/null 2>&1
    return $?
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z "$host" "$port" >/dev/null 2>&1
    return $?
  fi
  return 1
}

resolve_frontend_port() {
  local host="$1"
  local preferred_port="$2"
  local scan_limit="$3"

  local selected_port="$preferred_port"
  local attempt=0
  while (( attempt <= scan_limit )); do
    if ! port_in_use "$host" "$selected_port"; then
      echo "$selected_port"
      return 0
    fi
    selected_port=$((selected_port + 1))
    attempt=$((attempt + 1))
  done

  echo "ERROR: no free frontend port found from ${preferred_port} to $((preferred_port + scan_limit))."
  return 1
}

cd "$PROJECT_ROOT"

echo "Building frontend..."
bun run build >"$BUILD_LOG" 2>&1

RESOLVED_FRONTEND_PORT="$(resolve_frontend_port "$FRONTEND_HOST" "$FRONTEND_PORT" "$SMOKE_PORT_SCAN_LIMIT")"
if [[ "$RESOLVED_FRONTEND_PORT" != "$FRONTEND_PORT" ]]; then
  echo "Port ${FRONTEND_PORT} is in use; using ${RESOLVED_FRONTEND_PORT} for smoke run."
fi
FRONTEND_PORT="$RESOLVED_FRONTEND_PORT"

echo "Starting frontend on ${FRONTEND_HOST}:${FRONTEND_PORT}..."
bun run start -- --hostname "$FRONTEND_HOST" --port "$FRONTEND_PORT" >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

sleep 1
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
  echo "ERROR: next start exited before readiness check."
  cat "$FRONTEND_LOG" || true
  exit 1
fi

wait_until_ready \
  "http://${FRONTEND_HOST}:${FRONTEND_PORT}" \
  "frontend" \
  "$SMOKE_WAIT_SECONDS"

SMOKE_FRONTEND_BASE_URL="http://${FRONTEND_HOST}:${FRONTEND_PORT}" \
SMOKE_METRICS_PATH="$SMOKE_LOG_DIR/smoke-metrics.json" \
  bun scripts/smoke/check-routes-and-api.ts

echo "Ensuring Playwright Chromium is installed..."
bunx playwright install chromium >/dev/null

if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
  echo "ERROR: frontend process exited before screenshot capture."
  cat "$FRONTEND_LOG" || true
  exit 1
fi

SCREENSHOT_BASE_URL="http://${FRONTEND_HOST}:${FRONTEND_PORT}" \
SCREENSHOT_OUT_DIR="output/playwright/smoke" \
  ./scripts/screenshot_regression.sh

echo "Frontend smoke suite passed."
echo "Logs: $SMOKE_LOG_DIR"
echo "Screenshots: output/playwright/smoke"
