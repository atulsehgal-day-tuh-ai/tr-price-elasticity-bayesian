#!/usr/bin/env bash
set -euo pipefail

echo "==> Creating Python 3.12 venv (Linux)"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV_DIR="${REPO_ROOT}/venv312"

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "ERROR: python3.12 not found. On Ubuntu you can usually run:"
  echo "  sudo apt-get update && sudo apt-get install -y python3.12 python3.12-venv python3.12-dev build-essential g++"
  exit 1
fi

rm -rf "$VENV_DIR"
python3.12 -m venv "$VENV_DIR"

"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

echo "==> Done"
echo "To activate: source ./venv312/bin/activate"

