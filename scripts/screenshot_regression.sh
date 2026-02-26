#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${SCREENSHOT_BASE_URL:-http://127.0.0.1:3000}"
OUT_DIR="${SCREENSHOT_OUT_DIR:-output/playwright/regression}"
WAIT_MS="${SCREENSHOT_WAIT_MS:-2200}"

DESKTOP_DIR="$OUT_DIR/desktop"
MOBILE_DIR="$OUT_DIR/mobile"
mkdir -p "$DESKTOP_DIR" "$MOBILE_DIR"

run_shot() {
  local cmd="$1"
  local attempts=0
  local max_attempts=2

  until eval "$cmd"; do
    attempts=$((attempts + 1))
    if (( attempts >= max_attempts )); then
      return 1
    fi
    sleep 1
  done
}

capture_route() {
  local route="$1"
  local slug="$2"

  run_shot "bunx playwright screenshot --wait-for-timeout=$WAIT_MS --full-page '$BASE_URL$route' '$DESKTOP_DIR/$slug.png'"
  run_shot "bunx playwright screenshot --wait-for-timeout=$WAIT_MS --full-page --viewport-size=390,844 '$BASE_URL$route' '$MOBILE_DIR/$slug.png'"

  if [[ ! -s "$DESKTOP_DIR/$slug.png" || ! -s "$MOBILE_DIR/$slug.png" ]]; then
    echo "Screenshot capture failed for route: $route"
    exit 1
  fi
}

capture_route "/" "home"
capture_route "/articles" "articles"
capture_route "/analytics" "analytics"
capture_route "/admin/crawler" "admin-crawler"
capture_route "/saved" "saved"
capture_route "/settings" "settings"

printf '%s\n' \
  "$DESKTOP_DIR/home.png" \
  "$DESKTOP_DIR/articles.png" \
  "$DESKTOP_DIR/analytics.png" \
  "$DESKTOP_DIR/admin-crawler.png" \
  "$DESKTOP_DIR/saved.png" \
  "$DESKTOP_DIR/settings.png" \
  "$MOBILE_DIR/home.png" \
  "$MOBILE_DIR/articles.png" \
  "$MOBILE_DIR/analytics.png" \
  "$MOBILE_DIR/admin-crawler.png" \
  "$MOBILE_DIR/saved.png" \
  "$MOBILE_DIR/settings.png" > "$OUT_DIR/screenshots.txt"

echo "Screenshot regression completed: $OUT_DIR"
