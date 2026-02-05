#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <filename.md>"
  echo "Example: $0 Sparkling_Ice_Analytics_Plan_Business_Guide.md"
  exit 1
fi

INPUT_MD="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELP_DIR="${REPO_ROOT}/help_documents"
OUT_DIR="${REPO_ROOT}/html"

if [[ ! -d "$HELP_DIR" ]]; then
  echo "ERROR: help_documents not found at: $HELP_DIR"
  exit 1
fi

IN_PATH="${HELP_DIR}/${INPUT_MD}"
if [[ ! -f "$IN_PATH" ]]; then
  echo "ERROR: Markdown file not found: $IN_PATH"
  exit 1
fi

mkdir -p "$OUT_DIR"
STEM="$(basename "$IN_PATH" .md)"
OUT_PATH="${OUT_DIR}/${STEM}.html"

PYTHON="${REPO_ROOT}/venv312/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python"
fi

CSS_HREF="https://cdn.jsdelivr.net/npm/github-markdown-css@5/github-markdown.min.css"

"$PYTHON" "${REPO_ROOT}/scripts/md_to_html.py" --input "$IN_PATH" --output "$OUT_PATH" --css "$CSS_HREF"

echo "Wrote: $OUT_PATH"

