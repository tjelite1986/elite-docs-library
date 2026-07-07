#!/bin/bash
# docker-cleanup.sh — weekly disk hygiene for a Docker host.
#
# Docker hosts rot: dangling images from every rebuild, build cache that
# grows by gigabytes, logs that never rotate. On a small machine (Raspberry
# Pi with an SD card or small SSD) this eventually fills the disk and takes
# every container down with it.
#
# This script only removes things that are safe to lose:
#   - dangling images (untagged layers superseded by a rebuild)
#   - build cache older than the threshold
#   - stopped containers older than the threshold
#   - unused networks
# It deliberately does NOT touch volumes (that's your data) and does NOT
# remove unused tagged images (you may want the rollback).
#
# Run weekly from cron:
#   0 4 * * 0 /path/to/docker-cleanup.sh >> /var/log/docker-cleanup.log 2>&1

set -euo pipefail

AGE="168h"   # only clean things older than 7 days

echo "=== docker-cleanup $(date +'%F %T') ==="
df -h / | tail -1

# Stopped containers older than AGE (running ones are never touched)
docker container prune -f --filter "until=$AGE"

# Dangling images only (NOT -a: keeps tagged images for rollbacks)
docker image prune -f

# Build cache — the usual biggest win; rebuilds recreate it as needed
docker builder prune -f --filter "until=$AGE"

# Networks no container uses
docker network prune -f --filter "until=$AGE"

echo "--- after ---"
df -h / | tail -1
docker system df
