# Home Assistant in plain Docker (no supervisor) — setup and survival guide

Run Home Assistant as an ordinary Docker container ("Home Assistant
Container" in the official docs). This is the right choice when HA is one
service among many on a machine you manage yourself — a Raspberry Pi that
also runs your other containers — instead of dedicating the whole machine to
Home Assistant OS.

The trade-off, and what this guide is really about: **you have no
supervisor**. No add-on store, no `hassio.*` services, and several
automation examples on the forums silently assume APIs you don't have. The
second half of this guide lists the standalone-specific gotchas that
otherwise cost you an evening each.

## Prerequisites

- Docker + Compose on a Linux machine.
- Basic YAML editing.

## 1. Compose file

```yaml
services:
  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    container_name: homeassistant
    restart: unless-stopped
    network_mode: host
    environment:
      - TZ=Etc/UTC          # set your timezone
    volumes:
      - ./config:/config
      - /etc/localtime:/etc/localtime:ro
      # USB stick for Zigbee/Z-Wave, if you have one:
      # - /dev/serial/by-id/PUT_YOUR_STICK_ID_HERE:/dev/ttyUSB0
```

**`network_mode: host` is not optional in practice.** Device discovery
(mDNS/SSDP for Chromecast, ESPHome, HomeKit, many integrations) needs the
container to sit directly on your LAN. With a bridged network half your
integrations mysteriously find nothing. Consequence: HA occupies port
`8123` on the host, and you cannot attach it to Docker networks — a reverse
proxy reaches it via the host IP instead (below).

Start it and do onboarding at `http://<server-ip>:8123`:

```bash
docker compose up -d
docker logs homeassistant --tail 50
```

Everyday commands:

```bash
docker restart homeassistant            # after configuration.yaml changes
docker logs homeassistant --tail 50     # first stop when something breaks
docker exec homeassistant python -m homeassistant --script check_config -c /config
```

## 2. Reverse proxy (optional)

Because of host networking, a proxy in a Docker network can't reach HA by
container name — point it at the host. With Traefik (see the Traefik guide
in this repo), use a file-provider service or host-gateway address:

```yaml
# traefik dynamic config
http:
  routers:
    ha:
      rule: Host(`ha.example.com`)
      entryPoints: [https]
      tls:
        certResolver: cloudflare
      service: ha
  services:
    ha:
      loadBalancer:
        servers:
          - url: "http://192.168.1.10:8123"   # the host's LAN IP
```

And in `configuration.yaml`, HA must be told to trust the proxy or it
rejects the forwarded requests:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.16.0.0/12      # your proxy's Docker network range
    - 192.168.1.10       # or the proxy host's IP
```

## 3. The REST API — your automation escape hatch

Without a supervisor, the REST API on port 8123 is how scripts and other
services talk to HA.

1. Create a token: your **user profile → Security → Long-lived access
   tokens → Create**. Store it in a password manager or env file — HA shows
   it once.
2. Use it:

```bash
TOKEN="PUT_YOUR_LONG_LIVED_TOKEN_HERE"
BASE="http://localhost:8123/api"

# Is the API up?
curl -s -H "Authorization: Bearer $TOKEN" $BASE/

# Read one entity
curl -s -H "Authorization: Bearer $TOKEN" $BASE/states/sensor.outdoor_temperature

# Call a service (turn on a light)
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_id": "light.kitchen"}' $BASE/services/light/turn_on
```

> **`GET /api/states` returns EVERYTHING and can be enormous** (megabytes on
> a big install). Don't pipe it straight into a parser or a chat window —
> save it to a file first and query with `jq`/Python:
> `curl -s -H "Authorization: Bearer $TOKEN" $BASE/states > /tmp/states.json`

## 4. Standalone-specific gotchas

These are the ones that bite people coming from Home Assistant OS, or
following forum examples written for it:

| Gotcha | Reality in standalone Docker |
|--------|------------------------------|
| `hassio.*` services, add-on store, "Supervisor" panel | Don't exist. Anything an add-on would do (MQTT broker, Node-RED, Zigbee2MQTT) runs as its **own Docker container** next to HA. |
| `update.enable_auto_update` / `update.disable_auto_update` in automations | These services don't exist here. Track your own flag with an `input_boolean` instead. |
| Calling `update.install` when no update is pending | The action **fails and kills the automation**. Add `continue_on_error: true` to that step. |
| `trigger.to_state` in templates | **Undefined when you run the automation manually** (Run action). Guard with `{% if trigger.to_state is defined %}` or manual test runs will error. |
| Time trigger limited to weekdays | A time trigger has no weekday option — combine `trigger: time` with a separate condition: `condition: time` + `weekday: [mon, tue, wed, thu, fri]`. |
| Updating HA itself | `docker compose pull && docker compose up -d`. Pin a version tag instead of `stable` if you want to choose when. Take a copy of `./config` before major upgrades. |
| Editing dashboards as YAML | If you use YAML mode dashboards, custom cards installed via HACS load from `/hacsfiles/...` resources — after adding a card, add its resource entry too, or you get "Custom element doesn't exist". |

## 5. Backups

Your entire installation is the `./config` directory (plus any containers
you added beside it). No supervisor backups needed:

```bash
tar czf ha-backup-$(date +%F).tar.gz ./config
```

Automate it with the `git-auto-backup.sh` script in this repo's `scripts/`
section (put `secrets.yaml` in `.gitignore` and use a **private** repo),
or a nightly tar to another disk.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Integrations discover nothing | You're not on `network_mode: host`. |
| `400 Bad Request` behind the reverse proxy | Missing `use_x_forwarded_for` / `trusted_proxies` in `configuration.yaml`. |
| Config change didn't take effect | Most `configuration.yaml` changes need `docker restart homeassistant`; check config first with the `check_config` command above. |
| Zigbee/Z-Wave stick vanished after reboot | Map the stick by stable path `/dev/serial/by-id/...`, never `/dev/ttyUSB0` directly (the number changes). |
| Container healthy but UI dead slow | The database. Keep `recorder:` history short (`purge_keep_days`), or move the recorder DB off the SD card. |
