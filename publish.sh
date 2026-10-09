#!/usr/bin/env bash
# Usage: ./publish.sh YYYY-MM-DD /path/to/brief.md
# Copies the brief into briefs/, rebuilds the site, commits "news: <date>", pushes to main.
# Idempotent: re-running for the same date replaces that day's brief.
set -euo pipefail
if [ $# -ne 2 ]; then echo "usage: $0 YYYY-MM-DD path/to/brief.md" >&2; exit 2; fi
DATE="$1"; SRC="$2"
[[ "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { echo "bad date: $DATE (want YYYY-MM-DD)" >&2; exit 2; }
date -d "$DATE" >/dev/null 2>&1 || { echo "invalid date: $DATE" >&2; exit 2; }
[ -s "$SRC" ] || { echo "missing or empty markdown: $SRC" >&2; exit 2; }
SRC="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")"
cd "$(dirname "$0")"
git pull --ff-only --quiet origin main || true
mkdir -p briefs
DEST="briefs/$DATE.md"
[ "$SRC" -ef "$DEST" ] || cp "$SRC" "$DEST"
python3 build.py
git add -A briefs index.html archive robots.txt .nojekyll [0-9][0-9][0-9][0-9] 2>/dev/null || git add -A
if git diff --cached --quiet; then
  echo "no changes for $DATE; nothing to commit"
else
  git commit --quiet -m "news: $DATE"
fi
git push --quiet origin HEAD:main
echo "published: https://vnqqsmhyvm-a11y.github.io/daily-news/$(echo "$DATE" | tr - /)/"
