# Self-hosting Next.js in Docker — multi-stage builds, native modules, and the traps

A battle-tested recipe for running a Next.js app in Docker on your own server
(including ARM machines like a Raspberry Pi), with special attention to the
things that break in practice:

- native Node modules (`better-sqlite3`, `sharp`) crashing with
  `ERR_DLOPEN_FAILED`
- images that balloon to 3 GB because of a `chown -R`
- dev dependencies leaking into the runtime image
- when the popular "standalone output" strategy is the **wrong** choice

Everything below assumes Next.js 14/15, but the ideas apply generally.

## 1. Two deployment strategies — pick by dependency type

| Strategy | When to use | Deploy cycle |
|----------|-------------|--------------|
| **A. Build on host + bind-mount standalone output** | No native modules | `npm run build && docker restart app` — seconds |
| **B. Multi-stage build inside Docker** | Any native module (`better-sqlite3`, `sharp`, `canvas`, …) | `docker compose build && docker compose up -d` |

**Why native modules force strategy B:** a native module is compiled C++ bound
to a specific Node ABI. If you build on the host with Node 22 and run inside a
`node:20` container, the module was compiled for the wrong ABI and the app dies
at startup with `ERR_DLOPEN_FAILED`. Compiling inside the image guarantees the
build and runtime environments match.

## 2. Strategy A — bind-mounted standalone output

Fastest possible deploys when your dependency tree is pure JavaScript.

1. In `next.config.mjs`:

   ```js
   const nextConfig = { output: "standalone" };
   export default nextConfig;
   ```

2. Minimal runner Dockerfile (no `npm ci`, no build — it only runs):

   ```dockerfile
   FROM node:20-slim
   WORKDIR /app
   ENV NODE_ENV=production
   ENV NEXT_TELEMETRY_DISABLED=1
   RUN addgroup --system --gid 1001 nodejs \
     && adduser --system --uid 1001 nextjs
   USER nextjs
   EXPOSE 3000
   ENV PORT=3000 HOSTNAME=0.0.0.0
   CMD ["node", "server.js"]
   ```

3. Compose bind-mounts the build output from the host:

   ```yaml
   services:
     myapp:
       build: .
       container_name: myapp
       restart: unless-stopped
       volumes:
         - /path/to/project/.next/standalone:/app
         - /path/to/project/.next/static:/app/.next/static
         - /path/to/project/public:/app/public
         - myapp_data:/app/data     # named volume for persistent data
   volumes:
     myapp_data:
   ```

4. Deploy after a code change:

   ```bash
   npm run build && docker restart myapp
   ```

The image only needs rebuilding when `package.json` changes.

## 3. Strategy B — multi-stage build (the robust default)

Four stages: **deps** (all deps, compiles native code), **builder** (runs
`next build`), **prod-deps** (production-only deps, native code compiled
again), **runner** (slim final image).

```dockerfile
# ---- deps: full install, native modules compiled here ----
FROM node:20-slim AS deps
RUN apt-get update && apt-get install -y python3 make g++ \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ---- builder: next build ----
FROM node:20-slim AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- prod-deps: production-only node_modules for the runtime ----
FROM node:20-slim AS prod-deps
RUN apt-get update && apt-get install -y python3 make g++ \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

# ---- runner: what actually ships ----
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs \
  && mkdir -p /app/data && chown nextjs:nodejs /app/data

COPY --from=prod-deps --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder   --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder   --chown=nextjs:nodejs /app/public ./public
COPY --chown=nextjs:nodejs package.json next.config.mjs ./

USER nextjs
EXPOSE 3000
CMD ["npx", "next", "start"]
```

### Why the separate `prod-deps` stage?

Copying `node_modules` from **deps** would ship TypeScript, Tailwind, `@types/*`
and every other dev dependency into production. A fresh
`npm ci --omit=dev` keeps the runtime image hundreds of MB smaller — and still
compiles native modules against the right Node version.

### The `chown -R` layer-duplication trap

Never do this in a Dockerfile:

```dockerfile
COPY --from=builder /app/.next ./.next
RUN chown -R nextjs:nodejs /app        # ← duplicates every file!
```

Docker layers are immutable. A `chown -R` after a `COPY` rewrites the metadata
of every file, which stores **a second full copy** of them in a new layer — an
easy way to turn a 2 GB image into 3 GB. Use `COPY --chown=user:group ...`
instead; the files are owned correctly from the start and no extra layer is
created.

### Runtime OS packages

If your app shells out to system tools (ffmpeg for video thumbnails, poppler
for PDF rendering, libheif for iPhone HEIC photos), install them **only in the
runner stage**:

```dockerfile
RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg poppler-utils libheif-examples \
  && rm -rf /var/lib/apt/lists/*
```

### Build caching — day-to-day workflow

`npm ci` layers are cached as long as `package.json`/`package-lock.json` are
unchanged, so an ordinary code-change rebuild skips dependency install
entirely and is fast.

```bash
docker compose build && docker compose up -d     # normal deploy
```

Only reach for `--no-cache` when `package.json` changed in a confusing way or
something is genuinely broken. And clean up occasionally — build cache grows
fast:

```bash
docker builder prune -f
```

## 4. Persistent data

Never write app data (SQLite files, uploads) into the container filesystem —
it vanishes on rebuild. Use a **named volume**:

```yaml
services:
  myapp:
    build: .
    volumes:
      - myapp_data:/app/data
volumes:
  myapp_data:
```

Point the app at it with an env var (e.g. `DATA_DIR=/app/data`) rather than a
hard-coded path, so development on the host keeps working.

## 5. Gotchas checklist

| Symptom | Cause / fix |
|---------|-------------|
| `ERR_DLOPEN_FAILED` at startup | Native module compiled for a different Node version. Build inside Docker (strategy B) and make sure every stage uses the same `node:XX` base. |
| Works locally, `sharp` missing in CI | Lockfile generated on ARM (e.g. a Pi) doesn't list the x64 binary packages `npm ci` needs on GitHub's runners. In CI, add: `npm install --no-save @img/sharp-linux-x64 @img/sharp-libvips-linux-x64` after `npm ci`. |
| Image is gigabytes bigger than expected | `RUN chown -R` after COPY (see above), or dev deps shipped — check for the `prod-deps` stage. |
| App unreachable from other machines | Next binds to `localhost` by default in some setups — set `HOSTNAME=0.0.0.0`. |
| `docker build ... \| tail` "succeeded" but old code runs | Piping through `tail` makes the shell report **tail's** exit code, hiding a failed build — the old image then starts happily. Run the build unpiped, or capture `$?` from the build itself, and verify the change landed (e.g. check for a new string in the served page). |
| Query-builder/ORM package "not found" in production | It's in `devDependencies`. Anything imported at runtime must be in `dependencies` — `npm ci --omit=dev` strips the rest. |

## 6. Which Node base image?

- `node:20-slim` (Debian) — best default. `apt-get` available for native-module
  build tools and runtime packages.
- `node:20-alpine` — smaller, but musl libc occasionally breaks prebuilt
  native binaries; you trade size for debugging time.
- Match the major version to what you develop with, and pin it — silent major
  bumps are how `ERR_DLOPEN_FAILED` sneaks back in.
