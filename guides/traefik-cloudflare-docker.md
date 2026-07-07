# Traefik v3 reverse proxy with free wildcard HTTPS (Cloudflare) — Docker guide

Run any number of self-hosted web apps on **one machine** behind **one reverse
proxy**, each on its own subdomain with a **real, auto-renewing HTTPS
certificate** — even if the services are only reachable inside your LAN.

The trick is Let's Encrypt's **DNS-01 challenge** through Cloudflare: the
certificate is issued by proving you control the DNS zone, so **no port ever
needs to be open to the internet** for certificates to work.

What you end up with:

- `https://app1.example.com`, `https://app2.example.com`, … all served by one
  Traefik container.
- A wildcard certificate (`*.example.com`) that renews itself.
- New services go live by adding a few Docker **labels** — no proxy config files
  to edit.
- Automatic HTTP → HTTPS redirect.

## Prerequisites

| Item | Notes |
|------|-------|
| A Linux machine with Docker + Compose | A Raspberry Pi 4/5 is plenty |
| A domain name | Any registrar, ~$10/year |
| A free Cloudflare account | The domain's DNS must be managed by Cloudflare |

## 1. Point your domain at Cloudflare

1. Create a free account at <https://dash.cloudflare.com> and add your domain.
2. At your registrar, replace the nameservers with the two Cloudflare gives you.
3. In Cloudflare **DNS**, add records for your services. For a LAN-only setup,
   point them at your server's private IP and set them to **DNS only** (grey
   cloud, not proxied):

   | Type | Name | Content |
   |------|------|---------|
   | A | `*` | `192.168.1.10` (your server's LAN IP) |

   A single wildcard record means every subdomain resolves to your server —
   you never touch DNS again when adding services.

> **Privacy note:** a DNS record pointing at a private `192.168.x.x` address is
> harmless — it is unreachable from outside your network. Only devices on your
> LAN can use it.

## 2. Create a Cloudflare API token

Traefik needs permission to create the temporary DNS records that prove domain
ownership.

1. Cloudflare dashboard → **My Profile → API Tokens → Create Token**.
2. Use the **Edit zone DNS** template.
3. Scope it to your zone only. Copy the token — you'll put it in `.env`.

## 3. Directory layout

```
docker/
├── .env
└── traefik/
    ├── docker-compose.yml
    ├── traefik.yml        # static config
    ├── config.yml         # dynamic config (middlewares)
    └── acme.json          # certificate storage (created below)
```

```bash
mkdir -p ~/docker/traefik
cd ~/docker/traefik
touch acme.json
chmod 600 acme.json     # Traefik refuses to start if this is world-readable
docker network create traefik
```

The `traefik` network is shared: every service you want proxied joins it.

## 4. The files

### `.env` (in the parent `docker/` folder, or next to the compose file)

```dotenv
DOMAIN=example.com
CF_API_EMAIL=PUT_YOUR_CLOUDFLARE_EMAIL_HERE
CF_DNS_API_TOKEN=PUT_YOUR_API_TOKEN_HERE
TZ=Europe/Stockholm
```

### `traefik.yml` (static configuration)

```yaml
api:
  dashboard: false

entryPoints:
  http:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: https
          scheme: https
  https:
    address: ":443"

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
  file:
    filename: /config.yml
    watch: true

certificatesResolvers:
  cloudflare:
    acme:
      email: PUT_YOUR_CLOUDFLARE_EMAIL_HERE
      storage: "acme.json"
      dnsChallenge:
        provider: cloudflare
        resolvers:
          - "1.1.1.1:53"
          - "1.0.0.1:53"
```

Key choices:

- `exposedByDefault: false` — containers are **not** proxied unless they carry
  `traefik.enable=true`. Safer default.
- The `http` entrypoint exists only to redirect to HTTPS.

### `config.yml` (dynamic configuration — reusable middlewares)

```yaml
http:
  middlewares:
    default-headers:
      headers:
        frameDeny: true
        browserXssFilter: true
        contentTypeNosniff: true
        forceSTSHeader: true
        stsIncludeSubdomains: true
        stsPreload: true
        stsSeconds: 15552000
        customFrameOptionsValue: SAMEORIGIN

    lan-only:
      ipAllowList:
        sourceRange:
          - "10.0.0.0/8"
          - "192.168.0.0/16"
          - "172.16.0.0/12"

    secured:
      chain:
        middlewares:
          - lan-only
          - default-headers
```

The `lan-only` middleware is handy if you later expose some services to the
internet but want others to answer only on your LAN.

### `docker-compose.yml`

```yaml
services:
  traefik:
    image: traefik:v3.5
    container_name: traefik
    restart: unless-stopped
    networks:
      - traefik
    ports:
      - 80:80
      - 443:443
    environment:
      - TZ=$TZ
      - CF_API_EMAIL=$CF_API_EMAIL
      - CF_DNS_API_TOKEN=$CF_DNS_API_TOKEN
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik.yml:/traefik.yml:ro
      - ./config.yml:/config.yml:ro
      - ./acme.json:/acme.json
    labels:
      - "traefik.enable=true"
      # Request one wildcard certificate for the whole domain up front
      - "traefik.http.routers.traefik-secure.tls.domains[0].main=$DOMAIN"
      - "traefik.http.routers.traefik-secure.tls.domains[0].sans=*.$DOMAIN"

networks:
  traefik:
    external: true
```

Start it:

```bash
docker compose up -d
docker logs traefik --tail 20
```

Within a minute `acme.json` fills with your wildcard certificate. Errors about
the DNS challenge almost always mean a wrong/under-scoped API token.

## 5. Add a service — the label recipe

Any container becomes `https://<name>.example.com` with this block. Example
with a generic web app listening on port 3000:

```yaml
services:
  myapp:
    image: myapp:latest
    container_name: myapp
    restart: unless-stopped
    networks:
      - traefik
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.myapp-secure.rule=Host(`myapp.example.com`)"
      - "traefik.http.routers.myapp-secure.entrypoints=https"
      - "traefik.http.routers.myapp-secure.tls=true"
      - "traefik.http.routers.myapp-secure.tls.certresolver=cloudflare"
      - "traefik.http.services.myapp-service.loadbalancer.server.port=3000"

networks:
  traefik:
    external: true
```

Notes:

- **No `ports:` section needed** — Traefik reaches the container over the
  shared Docker network. Only Traefik itself publishes ports to the host.
- `loadbalancer.server.port` is the port the app listens on **inside** the
  container.
- Router and service names (`myapp-secure`, `myapp-service`) must be unique
  across all containers.
- To restrict a service to your LAN, add:
  `- "traefik.http.routers.myapp-secure.middlewares=secured@file"`

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `acme.json` stays empty, logs mention `cloudflare: failed to find zone` | API token lacks the zone, or wrong account email. Recreate the token with **Edit zone DNS** on the right zone. |
| Browser shows the self-signed `TRAEFIK DEFAULT CERT` | Certificate not issued yet, or the router is missing `tls.certresolver=cloudflare`. Check `docker logs traefik`. |
| `404 page not found` on a subdomain | No router matched: check the `Host()` rule spelling and that the container has `traefik.enable=true` and sits on the `traefik` network. |
| `Bad Gateway` | Traefik reached the container but the wrong port — fix `loadbalancer.server.port`, and confirm the app listens on `0.0.0.0`, not `127.0.0.1`. |
| Traefik exits with a permissions error about `acme.json` | `chmod 600 acme.json`. |
| Edited `config.yml` but changes don't apply | If you edit with a tool that does atomic rename (many editors do), the bind-mounted file's inode changes and the watch can miss it — `docker restart traefik`. |

## Why DNS challenge instead of the usual HTTP challenge?

The common Let's Encrypt flow (HTTP-01) requires port 80 reachable **from the
internet**, which means port-forwarding and exposing your server. DNS-01 only
requires API access to your DNS zone, so it works for LAN-only servers, behind
CGNAT, and it is the only challenge type that can issue **wildcard**
certificates.
