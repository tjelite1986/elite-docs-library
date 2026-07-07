# Guides

Step-by-step setup and how-to guides. Each guide is self-contained and written
for a reader starting from scratch — prerequisites, cost overview, glossary,
and troubleshooting included.

## Index

| Guide | Description |
|-------|-------------|
| [TorBox + TiviMate — Beginner guide](torbox-tivimate-beginner.md) | Build a personal streaming setup with TorBox cloud storage, the *arr stack (Prowlarr/Radarr/Sonarr), Decypharr, and TiviMate as the player. Written for complete beginners. |
| [Traefik + Cloudflare wildcard HTTPS](traefik-cloudflare-docker.md) | One reverse proxy for all your self-hosted apps, each on its own subdomain with a real auto-renewing certificate — no ports opened to the internet (DNS-01 challenge). |
| [Next.js in Docker with native modules](nextjs-docker-native-modules.md) | Multi-stage Docker builds for Next.js, when to bind-mount standalone output instead, and the traps: `ERR_DLOPEN_FAILED`, `chown -R` layer bloat, dev deps in production, ARM lockfiles. |
| [Auto-deploy: GitHub Actions → GHCR → Watchtower](github-actions-watchtower-autodeploy.md) | Push to `main` and your server updates itself: CI builds a multi-arch image, Watchtower pulls it. Includes the deploy-verification gotchas that bite in practice. |
| [Samba + SFTP NAS in Docker](samba-sftp-docker-nas.md) | Turn an always-on Linux box into a network drive for Windows/macOS/Android (SMB) and scripts/Linux (SFTP), including systemd sshfs auto-mounts. |
| [Self-hosted Obsidian sync (LiveSync + CouchDB)](obsidian-selfhosted-livesync.md) | Real-time vault sync across phone/tablet/computer through your own CouchDB with end-to-end encryption, plus a cron-driven git backup as a second safety net. |
