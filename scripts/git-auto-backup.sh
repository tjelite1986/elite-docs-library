#!/bin/bash
# git-auto-backup.sh — auto-commit + push a directory to its git remote.
#
# Run it from cron (e.g. every 10 minutes) against any directory that is a
# git repo with a remote: an Obsidian vault, a config directory, a notes
# folder. Silent when there is nothing to commit; logs one line per backup.
#
# Setup:
#   1. cd /path/to/dir && git init -b main
#   2. git remote add origin git@github.com:PUT_YOUR_USER_HERE/PUT_YOUR_REPO_HERE.git
#      (use a PRIVATE repo for anything personal)
#   3. crontab -e   →   */10 * * * * /path/to/git-auto-backup.sh
#
# Edit the two variables below.

set -euo pipefail

DIR="/path/to/directory"          # the directory to back up
LOG="$HOME/git-auto-backup.log"   # one-line log per push / failure

cd "$DIR"

# Nothing changed → exit silently (keeps cron mail quiet)
[ -z "$(git status --porcelain)" ] && exit 0

DATE=$(date +"%Y-%m-%d %H:%M:%S")

git add --all

# Put a short summary of what changed in the commit body
CHANGED=$(git diff --cached --name-status | head -20)
git commit -q -m "Auto-backup $DATE" -m "$CHANGED"

# Push; log errors but let the next cron run retry instead of crashing
if ! git push -q origin main >>"$LOG" 2>&1; then
    echo "[$DATE] push failed (will retry next run)" >>"$LOG"
    exit 1
fi

echo "[$DATE] backup ok" >>"$LOG"
