# Auto-deploy to your own server: GitHub Actions → GHCR → Watchtower

Push to `main`, and a few minutes later the new version is running on your
server. No SSH deploy scripts, no webhooks, no exposed ports.

**The pipeline:**

1. **GitHub Actions** runs your tests, builds a multi-architecture Docker image
   and pushes it to **GHCR** (GitHub Container Registry — free for public
   repos).
2. **Watchtower** runs on your server, periodically checks GHCR for a newer
   image, and when it finds one: pulls it, recreates the container with the
   same settings, and deletes the old image.

Works great on ARM servers (Raspberry Pi) because the workflow cross-builds
`linux/arm64` images on GitHub's x64 runners via QEMU.

## Prerequisites

- A GitHub repo containing your app with a working `Dockerfile`.
- A Linux server with Docker + Compose.

## 1. The GitHub Actions workflow

`.github/workflows/docker-build.yml`:

```yaml
name: Build & Push Docker image

on:
  push:
    branches: [main]
  release:
    types: [published]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npm test

  build-and-push:
    needs: test        # a red test suite never reaches production
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      # QEMU + Buildx enable cross-building for ARM servers
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata (tags, labels)
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=raw,value=latest,enable={{is_default_branch}}
            type=semver,pattern={{version}}
            type=sha,prefix=sha-

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64,linux/arm64
```

Notes:

- `secrets.GITHUB_TOKEN` is automatic — no secret to create for GHCR.
- Every push also gets an immutable `sha-<commit>` tag, so you can always roll
  back: `docker compose pull` a specific tag.
- `cache-from/to: type=gha` makes rebuilds fast (dependency layers cached
  between runs).
- The image lands at `ghcr.io/<user>/<repo>`. For a **private** repo, your
  server needs a login:
  `echo PUT_A_READ_PACKAGES_PAT_HERE | docker login ghcr.io -u <user> --password-stdin`

## 2. The app's compose file on the server

```yaml
services:
  myapp:
    container_name: myapp
    image: ghcr.io/youruser/myapp:latest
    pull_policy: always
    restart: unless-stopped
    volumes:
      - myapp_data:/app/data
    ports:
      - "3000:3000"
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

volumes:
  myapp_data:
```

The important line is the **Watchtower label** — with label-based scoping (next
step), only containers that carry it are auto-updated.

## 3. Watchtower on the server

```yaml
services:
  watchtower:
    container_name: watchtower
    image: nickfedor/watchtower:latest   # maintained fork; original is unmaintained
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_LABEL_ENABLE=true     # only touch labelled containers
      - WATCHTOWER_CLEANUP=true          # remove superseded images
      - WATCHTOWER_POLL_INTERVAL=3600    # check hourly
      - TZ=Europe/Stockholm
```

`WATCHTOWER_LABEL_ENABLE=true` is the setting that makes this safe to run on a
server full of other containers: nothing updates unless you opted it in with
the label.

That's the whole system. Push to `main` → CI builds → within the hour (or your
poll interval) Watchtower swaps the container.

## 4. Deploying *right now* (don't wait for the poll)

```bash
cd /path/to/compose/dir
docker compose pull && docker compose up -d
```

### The race everyone hits once

You push, immediately run `docker compose pull` — and get the **old** image,
because CI hasn't finished building yet. Worse, since the pull found "no
change", `up -d` doesn't recreate anything, and it *looks* deployed.

If you script an immediate deploy, wait for the CI run of **your commit** to
finish first (GitHub CLI):

```bash
git push
gh run watch $(gh run list --commit $(git rev-parse HEAD) --json databaseId -q '.[0].databaseId')
docker compose pull && docker compose up -d
```

### Verify the deploy actually happened

Compare the running container's image ID with the freshly pulled one:

```bash
docker inspect myapp --format '{{.Image}}'
docker image inspect ghcr.io/youruser/myapp:latest --format '{{.Id}}'
```

Same hash = the new version is live. This is more trustworthy than "the pull
printed something", and catches the not-recreated case above.

> **PWA/browser caveat:** if your app is a PWA or uses aggressive caching, your
> browser may keep serving old JavaScript after a successful deploy. Verify
> with a hard reload or a private window before debugging the server.

## 5. Rollback

Every commit has an immutable tag:

```bash
# in the compose file, temporarily:
image: ghcr.io/youruser/myapp:sha-abc1234
docker compose pull && docker compose up -d
```

Fix forward, then switch back to `:latest`.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `denied` when CI pushes to GHCR | Missing `permissions: packages: write` in the job, or org settings block GITHUB_TOKEN package writes. |
| Server can't pull the image | Private repo: `docker login ghcr.io` with a PAT that has `read:packages`. Public repo: check the package's visibility on GitHub (Packages → package → settings). |
| `exec format error` at container start | Image was built for the wrong CPU. Ensure `platforms:` includes your server's arch (`linux/arm64` for a Pi) and QEMU/Buildx steps are present. |
| Watchtower never updates the app | The app container is missing the `com.centurylinklabs.watchtower.enable=true` label (required with `WATCHTOWER_LABEL_ENABLE=true`). |
| Watchtower updates *everything*, including things it shouldn't | You run it without `WATCHTOWER_LABEL_ENABLE=true`. Turn it on and label the containers you want managed. |
| CI is green but native module fails on the server | Your lockfile was generated on a different CPU arch and CI installs missed a platform binary — see the multi-arch notes in the Next.js Docker guide in this repo. |

## Why this instead of SSH-based deploys?

- **No inbound access needed** — the server only makes outbound pulls. Nothing
  to expose, no deploy keys on the server.
- **The registry is the source of truth** — what runs is exactly what CI built
  and tested, never "whatever was on the server plus a git pull".
- **Trivially repeatable** — a new server needs only the compose file and a
  `docker compose up -d`.

The trade-off is latency (up to one poll interval) — acceptable for personal
projects, and section 4 covers forcing it.
