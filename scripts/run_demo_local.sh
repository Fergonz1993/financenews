#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
DEMO_ONCE="${DEMO_ONCE:-0}"

source_if_exists() {
  if [[ -f "$1" ]]; then
    while IFS= read -r line; do
      line="${line//$'\r'/}"
      if [[ -z "$line" || "$line" == "#"* ]]; then
        continue
      fi
      if [[ "$line" == *"="* ]]; then
        # shellcheck disable=SC2163
        export "${line%%=*}=${line#*=}"
      fi
    done < "$1"
  fi
}

cleanup() {
  set +e
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  pkill -f "uvicorn financial_news.api.main:app" 2>/dev/null || true
  pkill -f "next dev" 2>/dev/null || true
}

source_if_exists "$PROJECT_ROOT/.env"

BACKEND_LOG_DIR="$PROJECT_ROOT/.tmp/demo"
mkdir -p "$BACKEND_LOG_DIR"
BACKEND_LOG="$BACKEND_LOG_DIR/backend.log"
FRONTEND_LOG="$BACKEND_LOG_DIR/frontend.log"

PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "❌ Python not found. Activate a venv or install Python 3."
  exit 1
fi

if ! command -v bun >/dev/null 2>&1; then
  echo "❌ Bun not found. Install Bun before running this demo."
  exit 1
fi

trap cleanup EXIT INT TERM

cd "$PROJECT_ROOT/src"
"$PYTHON_BIN" -m uvicorn financial_news.api.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

cd "$PROJECT_ROOT"
bun run dev -- --hostname 127.0.0.1 --port "$FRONTEND_PORT" >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

wait_until_ready() {
  local url="$1"
  local max_attempts=60
  local i=1
  while (( i <= max_attempts )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    ((i += 1))
  done
  return 1
}

if ! wait_until_ready "http://127.0.0.1:$BACKEND_PORT/health"; then
  echo "❌ Backend did not start in time. Check: $BACKEND_LOG"
  exit 1
fi

if ! wait_until_ready "http://127.0.0.1:$FRONTEND_PORT"; then
  echo "⚠️  Frontend did not answer quickly. Check: $FRONTEND_LOG"
fi

DEFAULT_FEEDS="${NEWS_INGEST_FEEDS:-https://www.reuters.com/tools/rss,https://www.cnbc.com/id/100003114/device/rss/rss.html,https://feeds.bbci.co.uk/news/business/rss.xml,https://news.google.com/rss/search?q=financial+news&hl=en-US&gl=US&ceid=US:en,https://news.google.com/rss/search?q=capital+markets&hl=en-US&gl=US&ceid=US:en,https://news.google.com/rss/search?q=artificial+intelligence+finance+markets&hl=en-US&gl=US&ceid=US:en}"
if [[ -n "${SEC_PRESS_RELEASE_FEEDS:-}" ]]; then
  DEFAULT_FEEDS="$SEC_PRESS_RELEASE_FEEDS,$DEFAULT_FEEDS"
fi

echo "🚀 Backend running on http://127.0.0.1:$BACKEND_PORT"
echo "🖥️  Frontend running on http://127.0.0.1:$FRONTEND_PORT"
echo "📓 Logs: $BACKEND_LOG  |  $FRONTEND_LOG"
echo
echo "🔎 Running demo ingest + search against your configured feeds..."

INGEST_RESPONSE=$(curl -sS -X POST -G --data-urlencode "source_urls=$DEFAULT_FEEDS" "http://127.0.0.1:$BACKEND_PORT/api/ingest")
echo "INGEST_RESPONSE: $INGEST_RESPONSE"

echo
echo "Sources:"
curl -sS "http://127.0.0.1:$BACKEND_PORT/api/sources"
echo
echo
echo "Topics:"
curl -sS "http://127.0.0.1:$BACKEND_PORT/api/topics"
echo
echo
echo "Search demo (SEC + Fed):"
curl -sS "http://127.0.0.1:$BACKEND_PORT/api/articles?search=SEC&limit=5"
echo

if [[ "$DEMO_ONCE" == "1" ]]; then
  echo "✅ Demo complete (DEMO_ONCE=1). Stopping now."
  exit 0
fi

echo "✅ Demo is ready. Keep this process open and open http://127.0.0.1:$FRONTEND_PORT in your browser."
echo "Press Ctrl+C to stop backend + frontend."
wait "$BACKEND_PID" "$FRONTEND_PID"
