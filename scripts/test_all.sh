#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT_DIR/venv/bin/python"

cd "$ROOT_DIR"

echo "==> Running unit tests"
"$PY" manage.py test --exclude-tag=e2e

echo "==> Running E2E tests (Playwright)"
"$PY" manage.py test --tag=e2e

echo "All tests passed."
