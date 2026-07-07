# Stream movies & TV over IPTV with TorBox + TiviMate — Beginner Guide

A complete, copy-paste guide to build your own "personal Netflix" that plays in
the **TiviMate** app on an Android TV box or Fire Stick. You never download
anything to your own disk — the media lives in the **TorBox** cloud and streams
on demand.

This version needs **no domain name, no Cloudflare, and no reverse proxy**. You
reach every tool in your web browser on `http://localhost:<port>`.

> **Read this first — which computer?**
> This stack uses a *FUSE mount* and a privileged container. That works reliably
> **only on Linux**. Docker Desktop on **Windows/Mac runs in a VM and the mount
> will not work properly.** If you only have Windows or a Mac, install
> **Ubuntu Server** in a free VM (VirtualBox) or on a spare/mini PC, and follow
> this guide there. A Raspberry Pi 4/5 or any small always-on Linux box is ideal.

---

## 1. What you are building (in plain words)

| Piece | What it is |
|-------|-----------|
| **TorBox** | A paid cloud service. You give it a torrent/magnet; it downloads it *in the cloud* and lets you stream the file back. Nothing lands on your disk. |
| **Decypharr** | The "bridge". It logs into TorBox, makes the cloud files look like a normal folder on your computer, and pretends to be a torrent program so Sonarr/Radarr can talk to it. |
| **Prowlarr** | A search engine manager. You add torrent/usenet sites here once, and it shares them with Sonarr & Radarr. |
| **Radarr** | Handles **movies**: search, pick a release, organize. |
| **Sonarr** | Same as Radarr but for **TV shows**. |
| **m3u-editor** | Turns your movie/TV folder into an "IPTV channel list" (an *Xtream* feed) that player apps understand. |
| **TiviMate** | The player app on your TV. It logs into m3u-editor and shows your movies & series with posters. |

**The flow:** you add a movie in Radarr → it downloads in TorBox → Decypharr
makes it appear in your movies folder → m3u-editor publishes it → TiviMate plays
it on your TV.

---

## 2. What it costs

| Item | Price |
|------|-------|
| **TorBox Pro** | **$10 / month** (required — this is the cloud + streaming) |
| **TiviMate Premium** | **~$13 / month** (or a cheaper yearly plan). The free version works but limits playlists/recordings. |
| The 6 tools above | Free (they run on your own computer) |
| Electricity | A small always-on PC/Pi uses very little |

---

## 3. Glossary (words you'll see)

- **Docker** — software that runs each tool in its own sealed box.
- **Container** — one running tool (e.g. the Radarr container).
- **Image** — the downloadable template a container is made from.
- **docker compose** — a single text file (`docker-compose.yml`) that describes
  all your containers, so you start everything with one command.
- **Volume / bind mount** — a folder on your computer that a container can see,
  so its data survives restarts.
- **Port** — the "door number" a tool listens on. `localhost:7878` = Radarr.
- **FUSE mount** — the trick that makes TorBox's cloud files show up as a normal
  folder.
- **Symlink** — a tiny "shortcut" file that points at the real (cloud) file.
  Your disk stores the shortcut; the movie itself stays in TorBox.

---

## 4. Get a Linux computer + Docker ready

### 4a. If your only computer is Windows or Mac — make an Ubuntu VM first

This stack needs Linux. The easiest way on a Windows/Mac machine is a free
virtual machine (a "computer inside your computer") running Ubuntu.

1. **Download the tools** (free):
   - VirtualBox: <https://www.virtualbox.org/wiki/Downloads>
   - Ubuntu Server 24.04 LTS ISO: <https://ubuntu.com/download/server>
2. **Create the VM** in VirtualBox → *New*:
   - Type Linux / Ubuntu (64-bit). Give it **4 GB+ RAM** and **40 GB+ disk**.
   - Under *Settings → Storage*, attach the Ubuntu ISO you downloaded.
   - Under *Settings → Network*, set the adapter to **Bridged Adapter** (so the
     VM gets its own address on your home network — TiviMate needs to reach it).
3. **Start the VM** and follow the Ubuntu installer (accept defaults; create a
   username + password; enable "Install OpenSSH server" when asked).
4. When it reboots, log in. Find its address with `hostname -I` — that is the IP
   you'll use for TiviMate later. Everything from here runs inside this VM.

> On a real spare PC or a Raspberry Pi 4/5, just install Ubuntu directly and skip
> the VM. If your machine already runs Linux, go straight to 4b.

### 4b. Install Docker

In the Ubuntu terminal, run these one at a time:

```bash
# Install Docker Engine + Compose plugin
curl -fsSL https://get.docker.com | sudo sh

# Let your user run docker without sudo (log out/in after this)
sudo usermod -aG docker $USER

# Verify (after logging back in)
docker version
docker compose version
```

---

## 5. Create your TorBox account

1. Open: <https://www.torbox.app/subscription?referral=81e7dd1a-8471-4341-89ce-49b54a4895ab>
   > **Disclosure:** this is a referral link — signing up through it gives the
   > guide author account credit at no extra cost to you. Prefer a clean
   > signup? Use <https://www.torbox.app/> instead.
2. Sign up and subscribe to the **Pro Plan ($10/month)**.
3. Go to **Settings → API**, create/copy your **API key**, and make sure
   **WebDAV** access is enabled for it.
4. Keep this key handy — you paste it into one file in Step 7.

---

## 6. Create the folders

```bash
# Media library (the movie/TV folders + the shortcut folder)
sudo mkdir -p /mnt/media/movies /mnt/media/tvshows /mnt/media/symlinks
# Where TorBox's cloud files will appear
sudo mkdir -p /mnt/decypharr
# Let your normal user own them
sudo chown -R $USER:$USER /mnt/media /mnt/decypharr

# The stack folder (compose file + each tool's settings)
mkdir -p ~/torbox-stack/decypharr
cd ~/torbox-stack
```

---

## 7. Add your TorBox key (Decypharr config)

Create the file `~/torbox-stack/decypharr/config.json` with this content, and
replace **`PUT_YOUR_TORBOX_API_KEY_HERE`** with the key from Step 5:

```json
{
  "url_base": "/",
  "port": "8282",
  "log_level": "info",
  "download_folder": "/mnt/media/symlinks",
  "default_download_action": "symlink",
  "categories": ["sonarr", "radarr"],
  "use_auth": false,
  "mount": {
    "type": "rclone",
    "mount_path": "/mnt/decypharr",
    "rclone": {
      "cache_dir": "/app/cache/rclone",
      "vfs_cache_mode": "writes",
      "transfers": 4,
      "uid": 1000,
      "gid": 1000
    }
  },
  "debrids": [
    {
      "provider": "torbox",
      "name": "torbox",
      "api_key": "PUT_YOUR_TORBOX_API_KEY_HERE",
      "use_webdav": true,
      "rate_limit": "100/minute",
      "download_rate_limit": "30/minute",
      "repair_rate_limit": "10/minute",
      "workers": 1,
      "torrents_refresh_interval": "2m",
      "download_links_refresh_interval": "30m"
    }
  ]
}
```

---

## 8. The compose file (copy this whole thing)

Create `~/torbox-stack/docker-compose.yml`:

```yaml
services:
  # --- The bridge: TorBox <-> normal folder + fake torrent client ---
  decypharr:
    image: cy01/blackhole:latest
    container_name: decypharr
    restart: unless-stopped
    environment:
      - TZ=Europe/Stockholm
      - PUID=1000
      - PGID=1000
      - UMASK=002
    ports:
      - "8282:8282"           # web UI: http://localhost:8282
    volumes:
      - /mnt:/mnt:rshared     # shares the TorBox mount with the other tools
      - ./decypharr:/app      # its settings (config.json from Step 7)
    devices:
      - /dev/fuse:/dev/fuse:rwm
    cap_add:
      - SYS_ADMIN
    security_opt:
      - apparmor:unconfined

  # --- Search engine manager ---
  prowlarr:
    image: lscr.io/linuxserver/prowlarr:latest
    container_name: prowlarr
    restart: unless-stopped
    environment:
      - TZ=Europe/Stockholm
      - PUID=1000
      - PGID=1000
    ports:
      - "9696:9696"           # http://localhost:9696
    volumes:
      - ./prowlarr:/config

  # --- Movies ---
  radarr:
    image: lscr.io/linuxserver/radarr:latest
    container_name: radarr
    restart: unless-stopped
    environment:
      - TZ=Europe/Stockholm
      - PUID=1000
      - PGID=1000
    ports:
      - "7878:7878"           # http://localhost:7878
    volumes:
      - ./radarr:/config
      - /mnt:/mnt:rslave      # sees the movies folder + TorBox files

  # --- TV shows ---
  sonarr:
    image: lscr.io/linuxserver/sonarr:latest
    container_name: sonarr
    restart: unless-stopped
    environment:
      - TZ=Europe/Stockholm
      - PUID=1000
      - PGID=1000
    ports:
      - "8989:8989"           # http://localhost:8989
    volumes:
      - ./sonarr:/config
      - /mnt:/mnt:rslave

  # --- Turns your library into an IPTV (Xtream) feed ---
  m3u-editor:
    image: sparkison/m3u-editor:latest
    container_name: m3u-editor
    restart: unless-stopped
    environment:
      - TZ=Europe/Stockholm
      - APP_URL=http://localhost:36400
      - APP_PORT=36400
      # built-in database + cache (leave as-is; just change the two passwords)
      - ENABLE_POSTGRES=true
      - PG_DATABASE=m3ue
      - PG_USER=m3ue
      - PG_PASSWORD=change-this-db-password
      - DB_CONNECTION=pgsql
      - DB_HOST=localhost
      - DB_PORT=5432
      - DB_DATABASE=m3ue
      - DB_USERNAME=m3ue
      - DB_PASSWORD=change-this-db-password
      - REDIS_ENABLED=true
      - REDIS_SERVER_PORT=36790
      - REDIS_HOST=localhost
      - REDIS_PASSWORD=change-this-token
      - M3U_PROXY_ENABLED=true
      - M3U_PROXY_PORT=38085
      - M3U_PROXY_HOST=localhost
      - M3U_PROXY_TOKEN=change-this-token
    ports:
      - "36400:36400"         # admin UI: http://localhost:36400
    volumes:
      - ./m3u-editor/data:/var/www/config
      - ./m3u-editor/storage:/var/www/html/storage/app/public
      - m3u_pgdata:/var/lib/postgresql/data
      - /mnt/media/movies:/media/movies
      - /mnt/media/tvshows:/media/tvshows
      - /mnt:/mnt:rslave

volumes:
  m3u_pgdata:
```

Now start everything:

```bash
cd ~/torbox-stack
docker compose up -d
```

Wait ~1–2 minutes for first start, then check they're running:

```bash
docker compose ps
# And confirm TorBox is mounted (should list your cloud files):
ls /mnt/decypharr
```

---

## 9. Configure each tool (in your browser)

Do these in order. Where a tool asks for another tool's address, use the
**container name** (e.g. `radarr`), not `localhost` — the containers talk to each
other by name.

### 9a. Decypharr — http://localhost:8282
Open it and confirm it shows your TorBox account and that the mount is active.
(The API key came from your `config.json`.)

### 9b. Prowlarr — http://localhost:9696
1. Finish the first-run wizard (set a username/password).
2. **Indexers → Add Indexer** → Prowlarr ships with a large built-in catalog;
   pick the indexers you have the right to use and add 3–5 of them:
   - Type a name in the "Add Indexer" search box, click it, leave the defaults,
     and **Test → Save**. If one fails the test (sites go down often), just use
     another — that's why you add several.
   - Private trackers or a Usenet indexer work the same way (they ask for an
     API key / login).
   > This guide doesn't recommend any specific indexer. Which ones you add —
   > and what you download through them — is your responsibility; only add
   > sources and content you're legally allowed to use.
3. **Settings → Apps → Add Application**:
   - **Radarr** → Prowlarr Server: `http://prowlarr:9696`, Radarr Server:
     `http://radarr:7878`, API key from Radarr (9c).
   - **Sonarr** → Prowlarr Server: `http://prowlarr:9696`, Sonarr Server:
     `http://sonarr:8989`, API key from Sonarr (9d).
   This pushes all your indexers to both automatically.

### 9c. Radarr — http://localhost:7878
1. Finish the first-run wizard. Find the API key under **Settings → General**.
2. **Settings → Download Clients → Add → qBittorrent**:
   - Host: `decypharr`  ·  Port: `8282`  ·  Category: `radarr`
   - Leave username/password empty.  Save.
3. **Settings → Media Management → Root Folders → Add** → `/mnt/media/movies`.
4. Add a movie, pick a release, and watch it appear in the folder after TorBox
   caches it.

### 9d. Sonarr — http://localhost:8989
Same as Radarr, but:
- Download client category: `sonarr`
- Root folder: `/mnt/media/tvshows`

### 9e. m3u-editor — http://localhost:36400

This is the step most people get stuck on, so here it is click-by-click. The
goal: point m3u-editor at your `/media/movies` and `/media/tvshows` folders so it
publishes them as **VOD** (movies) and **Series** (TV).

1. Log in with **admin / admin** and change the password immediately
   (top-right user menu → Profile).
2. In the left sidebar open **Media Server Integrations → New / Create**.
3. Fill in the form:
   - **Server Type:** `Local Media`
   - **Display Name:** anything, e.g. `Media`
   - **Enabled:** on
4. In the **Local Media Paths** section click **Add** twice and enter two rows
   (these paths are the folders the compose file mounted into m3u-editor):

   | Name | Path | Type |
   |------|------|------|
   | `Movies` | `/media/movies` | `Movies` |
   | `TvShows` | `/media/tvshows` | `TV Shows` |

5. **Save.** m3u-editor scans the folders and shows an item count per library
   (e.g. "Movies — 38 items"). Saving also **auto-creates a matching Playlist**.
   > Movies must sit as files inside `/media/movies`. TV must be organised as
   > `TvShows/Series Name/Season 01/episode.mkv` — Sonarr already does this for
   > you. Loose TV files without season folders are skipped.
6. Go to **Playlists** in the sidebar and open the playlist that was just created
   (named after your integration). This is your VOD + Series source.
7. On the playlist page, open the **Links / Xtream** panel. It shows the
   **Server URL, Username and Password** for Xtream logins — **write these
   down**, TiviMate uses them in Step 10.
   - To hand out a separate login (recommended over reusing admin), use the
     playlist's **Auth / Users** action to create a username + password.
8. *(Optional)* Add an **EPG → New** XMLTV source if you also want a TV guide;
   not needed for movies/series playback.

---

## 10. Set up TiviMate on your TV

1. On the Android TV box / Fire Stick, install **TiviMate** from the Play Store.
   Buy **Premium** for the best experience (or try the free tier first).
2. **Add playlist → Xtream Codes**:
   - **Server URL:** `http://<your-computer-ip>:36400`
     (find the IP with `hostname -I` on the Linux box, e.g. `http://192.168.1.50:36400`)
   - **Username / Password:** the Xtream user from Step 9e.
3. TiviMate loads your **Movies** and **Series** with posters. Press play — it
   streams from TorBox. Done!

> TiviMate and the computer must be on the **same home network**. (Reaching it
> from outside your home safely needs a domain + reverse proxy — that's the
> "advanced" version and not covered here.)

---

## 11. Everyday commands

```bash
cd ~/torbox-stack
docker compose ps            # what's running
docker compose logs -f decypharr   # watch one tool's logs
docker compose restart radarr      # restart one tool
docker compose down          # stop everything
docker compose up -d         # start everything
docker compose pull && docker compose up -d   # update to newest versions
```

---

## 12. If something breaks

| Problem | What to check |
|---------|---------------|
| `ls /mnt/decypharr` is empty | Wrong/expired TorBox API key, or WebDAV not enabled on it. Check Decypharr logs. |
| Radarr/Sonarr "can't connect to client" | Download client must be Host `decypharr`, Port `8282`, and the Category must match (`radarr`/`sonarr`). |
| Download stuck in queue | TorBox hasn't finished caching that release yet — wait, or pick another release. |
| Movie not in TiviMate | Confirm the file is in `/mnt/media/movies`, then rescan the library in m3u-editor. |
| Playback buffers a lot | The file isn't fully cached on TorBox yet, or your internet upload is slow. Try again shortly. |
| Nothing works after reboot | Run `docker compose up -d` again; Decypharr recreates the mount on start. |

---

## 13. Important notes

- **Never expose Decypharr (port 8282) to the internet.** It holds your TorBox
  access. Keep it on your home network only.
- Your disk only ever stores **shortcuts (symlinks) + settings** — the actual
  movies and shows stay in the TorBox cloud.
- Everything here is legal to run; **what you choose to add via indexers is your
  responsibility.** Respect the laws where you live.
- Want it reachable on nice `https://` web addresses instead of
  `localhost:<port>`? That's **Part B** below — a domain name + Cloudflare + the
  Traefik reverse proxy in front of these same containers.

---

# Part B (optional) — Nice HTTPS addresses with Traefik + Cloudflare

Everything above works fine on `http://localhost:<port>`. This part is the
upgrade: instead of remembering port numbers, you get real web addresses like
`https://radarr.example.com` with a valid padlock, all handled by one extra
container called **Traefik**.

**Get the localhost version fully working first, then do this.**

### B1. What Traefik does (plain words)

- **Traefik** is a *reverse proxy*: one front door that receives all web traffic
  and forwards it to the right container based on the address you typed.
- It also gets **free HTTPS certificates** automatically, so every tool is
  `https://` with a valid padlock — no browser warnings.
- Result: `https://radarr.example.com` instead of `http://localhost:7878`.

### B2. What you need first

1. **A domain name** you own (e.g. `example.com`), with its DNS managed by
   **Cloudflare** (free plan is fine).
2. In Cloudflare DNS, add a **wildcard record** so every sub-address points at
   your computer/router:
   - Type `A`, Name `*`, Content = your public IP (or `AAAA` for IPv6).
   - Now `anything.example.com` resolves to you — no new record per tool.
3. A **Cloudflare API token** so Traefik can prove you own the domain:
   - Cloudflare dashboard → **My Profile → API Tokens → Create Token**
   - Use the **"Edit zone DNS"** template, scoped to your domain. Copy the token.

> Replace `example.com` everywhere below with your real domain.

### B3. Secrets file

Create `~/torbox-stack/.env` (Docker Compose reads it automatically):

```dotenv
CF_API_EMAIL=you@example.com
CF_DNS_API_TOKEN=paste-your-cloudflare-token-here
DOMAIN=example.com
```

### B4. Traefik's own config

Create `~/torbox-stack/traefik/traefik.yml`:

```yaml
entryPoints:
  http:
    address: ":80"
    http:
      redirections:           # send all http:// to https:// automatically
        entryPoint:
          to: https
          scheme: https
  https:
    address: ":443"

providers:
  docker:
    exposedByDefault: false   # only containers you explicitly enable are exposed

certificatesResolvers:
  cloudflare:
    acme:
      email: you@example.com  # same as CF_API_EMAIL
      storage: /acme.json
      dnsChallenge:
        provider: cloudflare
```

Create an empty file for the certificates and lock it down:

```bash
touch ~/torbox-stack/traefik/acme.json
chmod 600 ~/torbox-stack/traefik/acme.json
```

### B5. Add Traefik to your compose file

Add this **new service** inside the `services:` block of your
`~/torbox-stack/docker-compose.yml` (alongside the others):

```yaml
  traefik:
    image: traefik:latest
    container_name: traefik
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    environment:
      - CF_API_EMAIL=${CF_API_EMAIL}
      - CF_DNS_API_TOKEN=${CF_DNS_API_TOKEN}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik/traefik.yml:/traefik.yml:ro
      - ./traefik/acme.json:/acme.json
    labels:
      # one wildcard certificate that covers every *.example.com address
      - "traefik.enable=true"
      - "traefik.http.routers.traefik.tls.certresolver=cloudflare"
      - "traefik.http.routers.traefik.tls.domains[0].main=${DOMAIN}"
      - "traefik.http.routers.traefik.tls.domains[0].sans=*.${DOMAIN}"
      # reusable http->https redirect middleware
      - "traefik.http.middlewares.https-redirect.redirectscheme.scheme=https"
```

### B6. Tell each tool its web address (add labels)

For each tool you want on a web address, add a `labels:` block to that service.
Here is the pattern — the only things that change per tool are the **name**, the
**subdomain**, and the **port**:

```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.NAME.rule=Host(`SUB.${DOMAIN}`)"
      - "traefik.http.routers.NAME.entrypoints=https"
      - "traefik.http.routers.NAME.tls=true"
      - "traefik.http.routers.NAME.tls.certresolver=cloudflare"
      - "traefik.http.services.NAME.loadbalancer.server.port=PORT"
```

Fill it in per tool:

| Tool (service) | NAME | SUB | PORT |
|----------------|------|-----|------|
| radarr | `radarr` | `radarr` | `7878` |
| sonarr | `sonarr` | `sonarr` | `8989` |
| prowlarr | `prowlarr` | `prowlarr` | `9696` |
| m3u-editor | `m3u` | `m3u` | `36400` |

So Radarr's block becomes:

```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.radarr.rule=Host(`radarr.${DOMAIN}`)"
      - "traefik.http.routers.radarr.entrypoints=https"
      - "traefik.http.routers.radarr.tls=true"
      - "traefik.http.routers.radarr.tls.certresolver=cloudflare"
      - "traefik.http.services.radarr.loadbalancer.server.port=7878"
```

Do **not** add labels to **decypharr** — the debrid gateway must stay on your
LAN only. Leave its `ports: - "8282:8282"` as-is and skip Traefik for it.

Also update m3u-editor's `APP_URL` so it knows its real address — change the
environment line to:

```yaml
      - APP_URL=https://m3u.${DOMAIN}
```

You can drop the `ports:` lines from radarr/sonarr/prowlarr/m3u-editor now
(Traefik reaches them over the internal network), or keep them for local access.

### B7. Apply and use

```bash
cd ~/torbox-stack
docker compose up -d
```

Give Traefik a minute to fetch the certificate the first time. Then open:

- `https://radarr.example.com`
- `https://sonarr.example.com`
- `https://prowlarr.example.com`
- `https://m3u.example.com`

In **TiviMate**, use the new address as the server URL:
`https://m3u.example.com` (with the same Xtream username/password).

> **Opening it to the internet:** for access from *outside* your home you must
> forward ports **80** and **443** on your router to this computer. Only do that
> if you understand the security implications — every service you expose is now
> reachable from the internet, so use strong passwords everywhere.
