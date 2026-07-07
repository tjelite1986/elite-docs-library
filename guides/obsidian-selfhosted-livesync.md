# Self-hosted Obsidian sync — CouchDB + LiveSync behind Traefik, with a git safety net

Sync your Obsidian vault between phone, tablet, and computers **without paying
for Obsidian Sync and without handing your notes to a cloud provider**. The
community plugin **Self-hosted LiveSync** syncs in near-real-time through a
**CouchDB** database you run yourself.

This guide also adds a second, independent layer: an automatic **git backup**
of the vault every 10 minutes — so a sync bug or a bad bulk edit is always one
`git checkout` away from undone.

**Architecture:**

```
Phone ──┐
Tablet ─┼── LiveSync plugin ⇄ https://sync.example.com (Traefik) ⇄ CouchDB container
Laptop ─┘
                             Server vault copy ── cron ──> private git repo (backup)
```

## Prerequisites

- Docker + Compose on an always-on server.
- A reverse proxy with HTTPS. This guide assumes the Traefik + Cloudflare setup
  from [traefik-cloudflare-docker.md](traefik-cloudflare-docker.md) —
  **HTTPS is required** for the mobile apps to connect.
- Obsidian on your devices with community plugins enabled.

## 1. CouchDB container

```
docker/livesync/
├── .env
├── local.ini
└── docker-compose.yml
```

`.env`:

```dotenv
COUCHDB_USER=PUT_A_USERNAME_HERE
COUCHDB_PASSWORD=PUT_A_STRONG_PASSWORD_HERE
```

`local.ini` — CouchDB settings LiveSync needs (CORS for the Obsidian apps,
large request sizes for attachments):

```ini
[couchdb]
single_node = true
max_document_size = 50000000

[chttpd]
max_http_request_size = 4294967296
enable_cors = true

[chttpd_auth]
require_valid_user = true

[httpd]
enable_cors = true
WWW-Authenticate = Basic realm="couchdb"

[cors]
origins = app://obsidian.md,capacitor://localhost,http://localhost
credentials = true
headers = accept, authorization, content-type, origin, referer
methods = GET, PUT, POST, HEAD, DELETE
max_age = 3600
```

The `origins` line lists how the Obsidian desktop app (`app://obsidian.md`)
and mobile apps (`capacitor://localhost`) identify themselves — without it,
every request is blocked by CORS.

`docker-compose.yml`:

```yaml
services:
  livesync:
    image: couchdb:3.4
    container_name: livesync
    restart: unless-stopped
    environment:
      - COUCHDB_USER=${COUCHDB_USER}
      - COUCHDB_PASSWORD=${COUCHDB_PASSWORD}
    volumes:
      - livesync_data:/opt/couchdb/data
      - ./local.ini:/opt/couchdb/etc/local.d/local.ini
    networks:
      - traefik
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.livesync-secure.rule=Host(`sync.example.com`)"
      - "traefik.http.routers.livesync-secure.entrypoints=https"
      - "traefik.http.routers.livesync-secure.tls=true"
      - "traefik.http.routers.livesync-secure.tls.certresolver=cloudflare"
      - "traefik.http.services.livesync-service.loadbalancer.server.port=5984"

volumes:
  livesync_data:

networks:
  traefik:
    external: true
```

```bash
docker compose up -d
```

Sanity check: `https://sync.example.com/_up` should answer `{"status":"ok"}`.

## 2. Configure the LiveSync plugin

On your **first** device (ideally the one whose vault is "the truth"):

1. Install the community plugin **Self-hosted LiveSync** and enable it.
2. In the plugin's setup wizard, fill in remote database settings:
   - **URI**: `https://sync.example.com`
   - **Username / Password**: from your `.env`
   - **Database name**: e.g. `vault` (LiveSync creates it)
3. Enable **End-to-end encryption** and set a passphrase — with it, the server
   only ever stores encrypted blobs, so even the CouchDB admin password leaking
   doesn't expose your notes. Store the passphrase in your password manager;
   it cannot be recovered.
4. Choose a sync mode — **LiveSync** (continuous) feels magic; **Periodic +
   on save** uses less battery on phones.
5. Let it do the initial upload.

On **every other device**: install the plugin, and use the **Setup URI**
(copy it from the first device: plugin settings → *Copy setup URI*) instead of
typing everything again. Open the URI on the new device, enter the passphrase,
and let it download the vault.

> **Tip:** sync the vault into an **empty** folder on new devices. Merging an
> existing divergent copy is the number one source of conflict spam.

## 3. The git safety net

Sync is not backup — a mistake syncs everywhere instantly. A cron-driven git
mirror gives you history.

On the server, keep a plain copy of the vault (either run Obsidian on the
server too, or use LiveSync's `filesystem-livesync` companion — simplest is a
copy that one of your synced devices pushes to). Then:

```bash
#!/bin/bash
# vault-backup.sh — auto-commit + push the vault. Runs from cron. Silent when clean.
set -euo pipefail

VAULT="/path/to/vault"
cd "$VAULT"

[ -z "$(git status --porcelain)" ] && exit 0

git add --all
CHANGED=$(git diff --cached --name-status | head -20)
git commit -m "Auto-backup $(date +'%Y-%m-%d %H:%M')" -m "$CHANGED" -q
git push origin main -q
```

```bash
# one-time setup
cd /path/to/vault
git init -b main
git remote add origin git@github.com:youruser/vault-backup.git   # PRIVATE repo
printf '.obsidian/workspace*\n.trash/\n' > .gitignore
crontab -e     # add:
# */10 * * * * /path/to/vault-backup.sh
```

Now every change is committed with a file list in the message body, and any
disaster is recoverable with normal git tools.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Mobile app can't connect, desktop works | Almost always TLS: mobile requires a **valid** HTTPS certificate (self-signed won't do). Check the cert in a mobile browser first. |
| "CORS" errors in the plugin log | `local.ini` not loaded (check the bind mount path) or `origins` line missing/mistyped. `docker restart livesync` after edits. |
| Large attachments fail to sync | Raise `max_document_size` / `max_http_request_size` in `local.ini` — the values above allow ~50 MB documents. |
| Conflicted copies everywhere | Two devices edited offline, or a new device merged into a non-empty vault. Resolve with the plugin's conflict resolver; onboard new devices into empty folders. |
| Database grows forever | Old revisions accumulate. Run the plugin's **Database maintenance → Compact** now and then, or `POST /vault/_compact` against CouchDB. |
| Forgot the E2E passphrase | Unrecoverable by design. Wipe the remote database (plugin: *Rebuild everything*) and re-upload from a device that has the full vault. |

## Cost and alternatives

Self-hosting this costs nothing beyond the server you already run. Compared to
the alternatives: **Obsidian Sync** ($4–8/month) is the zero-effort option and
funds the app's development; **syncing the vault through Dropbox/Drive/iCloud**
mostly works on desktop but is unreliable on Android and corrupts the
`.obsidian` folder often enough to be scary. LiveSync with E2E encryption plus
a git history is both private and the most recoverable setup of the three.
