#!/usr/bin/env zsh
# dev.sh — Start the FastAPI backend and the React frontend together.
#
# Usage:
#   ./dev.sh
#
# Press Ctrl+C once to cleanly stop both processes.

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

# ── Colour helpers ────────────────────────────────────────────────────────────
CYAN="\033[1;36m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

echo ""
echo "${CYAN}══════════════════════════════════════════${RESET}"
echo "${CYAN}  Resume Tailor — Dev Server              ${RESET}"
echo "${CYAN}══════════════════════════════════════════${RESET}"
echo ""

# ── Resolve npm BEFORE activating venv (venv activate can clobber PATH) ───────
NPM_BIN="$(command -v npm 2>/dev/null)"
if [[ -z "$NPM_BIN" ]]; then
  for candidate in /opt/homebrew/bin/npm /usr/local/bin/npm; do
    [[ -x "$candidate" ]] && NPM_BIN="$candidate" && break
  done
fi
if [[ -z "$NPM_BIN" ]]; then
  echo "${RED}❌  npm not found. Install Node.js (brew install node) and re-run.${RESET}"
  exit 1
fi
echo "  npm  → $NPM_BIN"

# ── Activate Python venv ──────────────────────────────────────────────────────
if [[ ! -f "$SCRIPT_DIR/.venv/bin/activate" ]]; then
  echo "${RED}❌  No .venv found. Run:${RESET}"
  echo "     python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
source "$SCRIPT_DIR/.venv/bin/activate"
echo "  venv → $VIRTUAL_ENV"
echo ""

# ── Install frontend deps if node_modules is missing ─────────────────────────
if [[ ! -d "$SCRIPT_DIR/frontend/node_modules" ]]; then
  echo "${YELLOW}⚙  Installing frontend dependencies…${RESET}"
  (cd "$SCRIPT_DIR/frontend" && "$NPM_BIN" install --silent)
fi

# ── Trap Ctrl+C — kill both child processes cleanly ──────────────────────────
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "${YELLOW}Shutting down…${RESET}"
  [[ -n "$BACKEND_PID"  ]] && kill "$BACKEND_PID"  2>/dev/null
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null
  # Give processes a moment to exit, then force-kill
  sleep 1
  [[ -n "$BACKEND_PID"  ]] && kill -9 "$BACKEND_PID"  2>/dev/null
  [[ -n "$FRONTEND_PID" ]] && kill -9 "$FRONTEND_PID" 2>/dev/null
  echo "${GREEN}All processes stopped. Bye!${RESET}"
  exit 0
}
trap cleanup INT TERM

# ── Start backend ─────────────────────────────────────────────────────────────
echo "${GREEN}▶  Backend  →  http://localhost:8000${RESET}"
uvicorn api:app --reload --port 8000 &
BACKEND_PID=$!

# Give uvicorn a moment to bind the port before vite starts
sleep 1

# ── Start frontend ────────────────────────────────────────────────────────────
echo "${GREEN}▶  Frontend →  http://localhost:5173${RESET}"
(cd "$SCRIPT_DIR/frontend" && "$NPM_BIN" run dev) &
FRONTEND_PID=$!

echo ""
echo "  Both servers are running."
echo "  Press ${YELLOW}Ctrl+C${RESET} to stop both."
echo ""

# ── Keep the script alive, watching for either process to die unexpectedly ────
while true; do
  sleep 3

  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "${RED}⚠  Backend process exited unexpectedly.${RESET}"
    cleanup
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "${RED}⚠  Frontend process exited unexpectedly.${RESET}"
    cleanup
  fi
done
