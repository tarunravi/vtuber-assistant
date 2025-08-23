#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
# Use absolute paths that work in Docker containers
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

log() { printf "[start] %s\n" "$*"; }

start_backend() {
  log "Starting backend..."
  cd "$BACKEND_DIR"
  if [ ! -d .venv ]; then
    log "Creating Python venv"
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip >/dev/null 2>&1 || true
  python -m pip install -r requirements.txt
  python server.py
}

start_frontend() {
  log "Starting frontend dev server..."
  
  # Prepare and install dependencies first
  cd "$FRONTEND_DIR"
  # Clean up node_modules to handle architecture issues in Docker
  if [ -d node_modules ]; then
    log "Cleaning up node_modules for Docker compatibility"
    rm -rf node_modules package-lock.json
  fi
  
  log "Installing npm dependencies"
  npm install --no-fund --no-audit
  
  # Sync assets after dependencies are available
  log "Syncing model assets..."
  cd "$SCRIPT_DIR"
  node frontend/scripts/sync-assets.mjs
  
  # Start the dev server
  cd "$FRONTEND_DIR"
  npm run dev
}

cleanup() {
  log "Shutting down..."
  # Kill all children
  pkill -P $$ 2>/dev/null || true
}

trap cleanup INT TERM EXIT

start_backend &
BACK_PID=$!

# slight stagger helps with logs
sleep 1

start_frontend &
FRONT_PID=$!

wait $BACK_PID
wait $FRONT_PID
