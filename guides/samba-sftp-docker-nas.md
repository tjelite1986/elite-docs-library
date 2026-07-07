# Turn a Linux server into a simple NAS — Samba + SFTP in Docker

Share the disks on an always-on Linux box (a Raspberry Pi with a USB hard
drive is the classic) so that:

- **Windows / macOS / Android file managers** browse it as a network drive
  (Samba/SMB),
- **command-line tools, scripts, and other Linux machines** reach the same
  folders over **SFTP** (great for `sshfs`, rsync-style backups, and apps that
  speak SFTP).

Both run as Docker containers with a shared user/password from one `.env`
file, and both simply bind-mount the host folders you choose.

## Prerequisites

- Linux machine with Docker + Compose.
- The folders you want to share (e.g. a big disk mounted at `/mnt/storage`).

## 1. Layout

```
docker/nas/
├── .env
└── docker-compose.yml
```

`.env`:

```dotenv
SHARE_USER=PUT_A_USERNAME_HERE
SHARE_PASS=PUT_A_STRONG_PASSWORD_HERE
TZ=Europe/Stockholm
```

## 2. `docker-compose.yml`

```yaml
services:
  samba:
    image: dperson/samba:latest
    container_name: samba
    restart: unless-stopped
    environment:
      - TZ=$TZ
    ports:
      - "445:445"
    command: >
      -u "${SHARE_USER};${SHARE_PASS}"
      -s "Storage;/mnt/storage;yes;no;no;${SHARE_USER}"
      -s "Media;/mnt/media;yes;no;no;${SHARE_USER}"
      -s "Backups;/mnt/backups;yes;no;no;${SHARE_USER}"
    volumes:
      - /mnt/storage:/mnt/storage
      - /mnt/storage/media:/mnt/media
      - /mnt/backups:/mnt/backups

  sftp:
    image: atmoz/sftp:latest
    container_name: sftp
    restart: unless-stopped
    ports:
      - "2222:22"
    command: ${SHARE_USER}:${SHARE_PASS}:1000:1000
    volumes:
      - /mnt/storage:/home/${SHARE_USER}/Storage
      - /mnt/backups:/home/${SHARE_USER}/Backups
```

### Reading the Samba `-s` share syntax

```
-s "Name;/path/in/container;browsable;readonly;guest;users"
        │        │              │        │      │     └ who may log in
        │        │              │        │      └ "no" = password required
        │        │              │        └ "no" = writable
        │        │              └ "yes" = visible when browsing
        │        └ must match a volume mount
        └ what clients see as the folder name
```

So `-s "Storage;/mnt/storage;yes;no;no;${SHARE_USER}"` =
a browsable, writable, password-protected share named **Storage**.

Add a share = add one `-s` line **and** one matching volume line, then
`docker compose up -d` (the container is recreated in seconds).

Start everything:

```bash
cd ~/docker/nas
docker compose up -d
```

## 3. Connect from each device

| Client | How |
|--------|-----|
| **Windows** | Explorer address bar: `\\192.168.1.10` → log in → optionally *Map network drive* |
| **macOS** | Finder → Go → Connect to Server → `smb://192.168.1.10` |
| **Android** | Any file manager with SMB support (Solid Explorer, CX, Material Files) → add SMB `192.168.1.10` |
| **Linux (GUI)** | Files → Other Locations → `smb://192.168.1.10` |
| **Linux (mount, SFTP)** | `sshfs -p 2222 user@192.168.1.10:/home/user/Storage /mnt/remote` |
| **Scripts / CLI** | `sftp -P 2222 user@192.168.1.10` or any SFTP-capable tool |

### Auto-mount on another Linux machine (systemd + sshfs)

For a desktop that should always see the server's disk, a systemd automount is
much more robust than an `fstab` line, because it mounts lazily on first
access and survives the server rebooting.

`/etc/systemd/system/mnt-remote.mount`:

```ini
[Unit]
Description=SSHFS mount of the file server

[Mount]
What=user@192.168.1.10:/home/user/Storage
Where=/mnt/remote
Type=fuse.sshfs
Options=_netdev,port=2222,IdentityFile=/home/me/.ssh/id_ed25519,reconnect,ServerAliveInterval=15,allow_other

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/mnt-remote.automount`:

```ini
[Unit]
Description=Automount for the file server

[Automount]
Where=/mnt/remote
TimeoutIdleSec=600

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now mnt-remote.automount
```

(Key-based auth: copy your public key into the container user's
`.ssh/authorized_keys` — with `atmoz/sftp`, bind-mount it to
`/home/user/.ssh/keys/id_ed25519.pub:ro`.)

## 4. Permissions

The SFTP container runs the user as UID/GID `1000:1000` (set in the `command`
line). Files it creates on the host are owned by host user 1000 — on most
single-user Linux installs that's you, which is what you want. If your shared
folders are owned by another user, either change the UID/GID in the compose
`command`, or open up the folders:

```bash
sudo chown -R 1000:1000 /mnt/storage
```

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Windows: "cannot access" / endless password prompt | Wrong credentials, or port 445 already used by Samba installed directly on the host — stop/remove the host `smbd` first. |
| Share visible but *empty* on clients | The `-s` path doesn't match a `volumes:` mount — the container is sharing an empty internal folder. |
| SFTP: "Permission denied" writing files | UID mismatch — see the Permissions section. |
| The server shows up **twice** in file managers / VLC | The host runs Avahi (mDNS) alongside the container's NetBIOS announcement, or announcements leak over multiple interfaces. Bind Samba and Avahi to a single interface, or disable host-side discovery of it. |
| Symlinks inside a share don't open | Add Samba globals: `-g "unix extensions = no" -g "follow symlinks = yes" -g "wide links = yes"`. Only do this on a trusted LAN — wide links let a symlink escape the share. |
| Works on LAN, want access from outside | Do **not** port-forward 445 (SMB on the internet is a magnet for attacks). Use a VPN (WireGuard/Tailscale) and reach the same LAN addresses through it. |

## Why containers instead of installing Samba on the host?

Same reasons as any other service: the config lives in one compose file you
can back up and re-deploy in minutes, upgrades are `docker compose pull`, and
removing it leaves no trace on the host. The one host-level thing you still
manage is folder ownership.
