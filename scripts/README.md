# Scripts

Small, self-contained shell scripts extracted from a real homelab. Each one
has its configuration at the top as plain variables — edit those, make the
file executable (`chmod +x`), and wire it into cron where noted.

## Index

| Script | Description |
|--------|-------------|
| [git-auto-backup.sh](git-auto-backup.sh) | Cron-driven auto-commit + push of any directory (Obsidian vault, config folder) to a private git repo. Silent when clean, retries failed pushes on the next run. |
| [deploy-verify.sh](deploy-verify.sh) | Deploy that can't lie: waits for the CI run of your exact commit, pulls, and proves the container runs the new image by comparing image IDs. |
| [docker-cleanup.sh](docker-cleanup.sh) | Weekly disk hygiene for a Docker host — prunes dangling images, old build cache, old stopped containers and unused networks. Never touches volumes or tagged images. |

## Conventions

- Configuration lives in UPPERCASE variables at the top of each script, with
  `PUT_YOUR_..._HERE` placeholders where a value is required.
- Scripts are cron-friendly: silent on the happy no-op path, one log line per
  action, non-zero exit on failure so cron mail / monitoring notices.
- `set -euo pipefail` everywhere.
