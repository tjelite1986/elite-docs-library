# Chat with Claude Code from your phone — a personal Telegram bridge

Run Claude Code on your always-on server and talk to it from Telegram: ask
about your projects, kick off tasks, get research summaries — from anywhere,
with live progress streaming into the chat while Claude works.

The bridge is one Python script (published in this repo:
[`scripts/telegram-claude-bot.py`](../scripts/telegram-claude-bot.py)). Each
Telegram message becomes a `claude --print` invocation; the JSONL event
stream is rendered as a self-updating status message (tool calls + partial
text), and each user keeps a persistent conversation via `--resume`.

## Read this first — the security model

This bot gives the whitelisted Telegram account **the ability to run Claude
Code as the OS user the bot runs as** — reading files, and doing whatever
that Claude installation is permitted to do. Treat it accordingly:

- **Whitelist only your own numeric user ID.** The whitelist is the entire
  access control. Never leave it empty in production, never add people you
  wouldn't hand a shell.
- The whitelist must be on **numeric user IDs**, never usernames — Telegram
  usernames are changeable and reusable by others.
- Run the bot as a dedicated, low-privilege user if you want a harder
  boundary between "phone Claude" and the rest of the machine.
- The bot token is a credential: anyone holding it can *impersonate the
  bot* (though not pass your whitelist). Keep it in the env file, mode 600.

## Prerequisites

- A Linux server with [Claude Code](https://claude.com/claude-code)
  installed and authenticated.
- Python 3.10+ and `pip install python-telegram-bot`.

## 1. Create the bot

1. In Telegram, message **@BotFather** → `/newbot` → pick a name and a
   unique username. BotFather replies with the **bot token**.
2. Optional but recommended: `/setjoingroups` → **Disable**, so the bot
   can't be added to groups.

## 2. Install and configure

```bash
mkdir -p ~/.config ~/.local/state
curl -o ~/telegram-claude-bot.py \
  https://raw.githubusercontent.com/tjelite1986/elite-docs-library/main/scripts/telegram-claude-bot.py

cat > ~/.config/telegram-claude-bot.env <<'EOF'
TG_BOT_TOKEN=PUT_YOUR_BOT_TOKEN_HERE
TG_ALLOWED_USER_IDS=
# CLAUDE_CWD=/home/youruser/projects     # where claude runs (defaults to $HOME)
# CLAUDE_MODEL=claude-sonnet-5           # optional model override
EOF
chmod 600 ~/.config/telegram-claude-bot.env
```

**Find your numeric user ID (bootstrap mode):** with the whitelist empty,
the bot only answers `/whoami`. Start it once in the foreground:

```bash
python3 ~/telegram-claude-bot.py
```

Message your bot `/whoami` in Telegram — it replies with your `user_id`.
Put that number in `TG_ALLOWED_USER_IDS`, stop the bot, and continue.

## 3. Run it as a systemd service

`/etc/systemd/system/telegram-claude-bot.service`:

```ini
[Unit]
Description=Personal Telegram <-> Claude Code bridge
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=youruser
Group=youruser
WorkingDirectory=/home/youruser
ExecStart=/usr/bin/python3 /home/youruser/telegram-claude-bot.py
Restart=on-failure
RestartSec=15
StandardOutput=append:/home/youruser/.local/state/telegram-claude-bot.log
StandardError=append:/home/youruser/.local/state/telegram-claude-bot.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-claude-bot
sudo systemctl status telegram-claude-bot
```

The bot uses **long polling** — it makes outbound requests to Telegram's
API, so it needs **no open ports, no public IP, no webhook**. It works from
behind any NAT.

## 4. Using it

- Just message the bot. While Claude works, the "Thinking…" message updates
  in place every couple of seconds with the tools being used
  (`🔧 Read → Grep×3 → Bash`) and the latest partial text.
- **`/reset`** — start a fresh Claude session (per user; sessions otherwise
  persist across messages *and* bot restarts via `--resume`).
- **`/whoami`** — show your user ID and whitelist status.
- Long answers are split into 4000-character chunks (Telegram's limit).

## How it works (for tinkerers)

The interesting part is streaming. `claude --print --output-format
stream-json --verbose --include-partial-messages` emits one JSON event per
line; the bot consumes them incrementally:

- `system/init` and `result` events carry the **session id**, saved per
  Telegram user for `--resume`.
- `stream_event` deltas (`text_delta`) accumulate the partial answer text.
- `assistant` events list `tool_use` blocks — the names feed the `🔧` trail.
  A subtlety: a turn's complete text *also* arrives in the `assistant`
  event, so the script tracks whether it already streamed that text as
  deltas to avoid duplicating it.
- Telegram rate-limits message edits, so the status edit is throttled to
  one per 2 seconds, and "message is not modified" errors are ignored.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Bot replies "Access denied. Your Telegram user ID is …" | That ID isn't in `TG_ALLOWED_USER_IDS` — this is also the intended way to *find* an ID. |
| No reply at all | Service down or token wrong — `systemctl status`, then check the log. |
| `[error: claude exit 1]` | Claude Code isn't authenticated for the service user, or `CLAUDE_CWD` doesn't exist. Run `claude --print "hi"` manually as that user. |
| Replies stall then time out | Very long tasks hit the 30-minute timeout (`CLAUDE_TIMEOUT_SEC`). Raise it, or break the task up. |
| Two bots answer | You're running the foreground bootstrap instance *and* the service — Telegram delivers to only one poller at a time, unpredictably. Stop one. |
| Session confusion after experiments | `/reset`, or delete the sessions JSON (`TG_CLAUDE_SESSIONS`, default `~/.local/state/telegram-claude-sessions.json`). |
