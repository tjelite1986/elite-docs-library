#!/bin/bash
# deploy-verify.sh — push-triggered deploy that can't lie to you.
#
# For the GitHub Actions → registry → docker compose flow (see the
# auto-deploy guide in this repo). Instead of "push, pull, hope", it:
#
#   1. finds the CI run for YOUR exact commit (not just the latest run),
#   2. waits for it to finish and aborts if it failed,
#   3. pulls + recreates the container,
#   4. PROVES the deploy happened by comparing image IDs.
#
# Why: pulling too early silently deploys the OLD image — the pull finds "no
# change", `up -d` recreates nothing, and everything looks fine. This script
# makes that impossible.
#
# Requirements: gh (GitHub CLI, authenticated), docker compose v2, run it
# from the repo you just pushed. Edit the three variables below.

set -euo pipefail

COMPOSE_DIR="/path/to/compose/dir"                 # where docker-compose.yml lives
CONTAINER="PUT_YOUR_CONTAINER_NAME_HERE"           # container_name in the compose file
IMAGE="ghcr.io/PUT_YOUR_USER_HERE/PUT_YOUR_REPO_HERE:latest"

SHA=$(git rev-parse HEAD)
echo "==> Waiting for CI on commit ${SHA:0:7} ..."

# Find the workflow run for this exact commit (retry while GitHub registers it)
RUN_ID=""
for _ in $(seq 1 12); do
    RUN_ID=$(gh run list --commit "$SHA" --json databaseId -q '.[0].databaseId' 2>/dev/null || true)
    [ -n "$RUN_ID" ] && break
    sleep 5
done
[ -z "$RUN_ID" ] && { echo "ERROR: no CI run found for $SHA — did you push?"; exit 1; }

# Wait for it; --exit-status makes this command fail if the run failed
gh run watch "$RUN_ID" --exit-status
echo "==> CI green."

cd "$COMPOSE_DIR"

BEFORE=$(docker inspect "$CONTAINER" --format '{{.Image}}' 2>/dev/null || echo "none")

docker compose pull
docker compose up -d

AFTER=$(docker inspect "$CONTAINER" --format '{{.Image}}')
PULLED=$(docker image inspect "$IMAGE" --format '{{.Id}}')

echo "==> image before : $BEFORE"
echo "==> image after  : $AFTER"

# The container must run the image we just pulled, and it must be a new one
if [ "$AFTER" != "$PULLED" ]; then
    echo "ERROR: container is NOT running the pulled image — deploy did not take."
    exit 1
fi
if [ "$AFTER" = "$BEFORE" ]; then
    echo "WARNING: image unchanged. Either the commit didn't change the image,"
    echo "         or you're about to debug something that never deployed."
    exit 1
fi

echo "==> Deploy verified: $CONTAINER runs the new image."
