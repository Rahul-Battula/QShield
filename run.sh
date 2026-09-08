#!/usr/bin/env sh
# QShield -- one-command launcher.
# Starts the backend (which serves the frontend) and opens the dashboard.
set -e
cd "$(dirname "$0")"

PY="${QSHIELD_PYTHON:-}"
if [ -z "$PY" ]; then
    if command -v py >/dev/null 2>&1 && py -3.11 -c "pass" >/dev/null 2>&1; then
        PY="py -3.11"
    elif command -v python3.11 >/dev/null 2>&1; then
        PY="python3.11"
    elif command -v python3 >/dev/null 2>&1; then
        PY="python3"
    else
        PY="python"
    fi
fi

if ! $PY -c "import app" >/dev/null 2>&1; then
    echo "First run: installing Python dependencies with $PY ..."
    $PY -m pip install -r requirements.txt
fi

# Build the Vite dashboard once if Node is available; otherwise the backend
# falls back to the vendored frontend-legacy/.
if [ ! -f frontend/dist/index.html ] && command -v npm >/dev/null 2>&1; then
    echo "Building the dashboard (one-time) ..."
    (cd frontend && npm install --no-audit --no-fund && npm run build)
fi

echo
echo "  QShield  ->  http://127.0.0.1:8000/"
echo
exec $PY -m app.api
