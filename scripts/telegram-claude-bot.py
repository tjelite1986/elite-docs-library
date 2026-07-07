#!/usr/bin/env python3
"""
Personal Telegram <-> Claude Code bridge with streaming progress.

Each message from a whitelisted user is forwarded to `claude --print
--output-format stream-json`. The bot reads the JSONL event stream as it
arrives and edits a single Telegram status message in place, so long
operations show live progress instead of a silent typing indicator.
Per-user sessions persist via `claude --resume <id>`.

See the companion guide in guides/telegram-claude-code-bot.md for setup and
the security model. Short version: anyone who can message this bot AND is on
the whitelist can run Claude Code as the OS user the bot runs as. Whitelist
only yourself.

Config via env vars (systemd EnvironmentFile, or a file at CONFIG_PATH):
- TG_BOT_TOKEN          required (from @BotFather)
- TG_ALLOWED_USER_IDS   comma-separated numeric Telegram user IDs
- CLAUDE_BIN            optional, defaults to "claude"
- CLAUDE_CWD            optional, working dir for claude; defaults to $HOME
- CLAUDE_MODEL          optional, e.g. "claude-sonnet-5"

Dependency: pip install python-telegram-bot
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import time
from pathlib import Path

from telegram import Message, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
LOG = logging.getLogger("tg-claude")

CONFIG_PATH = Path(
    os.environ.get("TG_CLAUDE_CONFIG", "~/.config/telegram-claude-bot.env")
).expanduser()
SESSION_PATH = Path(
    os.environ.get("TG_CLAUDE_SESSIONS", "~/.local/state/telegram-claude-sessions.json")
).expanduser()

# Telegram message rules
TG_MAX = 4000
EDIT_THROTTLE_SEC = 2.0
CLAUDE_TIMEOUT_SEC = 1800


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if CONFIG_PATH.is_file():
        for line in CONFIG_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()
TG_BOT_TOKEN = ENV.get("TG_BOT_TOKEN") or os.environ.get("TG_BOT_TOKEN", "")
ALLOWED = {
    int(x)
    for x in (
        ENV.get("TG_ALLOWED_USER_IDS")
        or os.environ.get("TG_ALLOWED_USER_IDS", "")
    ).split(",")
    if x.strip()
}
CLAUDE_BIN = ENV.get("CLAUDE_BIN") or os.environ.get("CLAUDE_BIN", "claude")
CLAUDE_CWD = ENV.get("CLAUDE_CWD") or os.environ.get("CLAUDE_CWD", str(Path.home()))
CLAUDE_MODEL = ENV.get("CLAUDE_MODEL") or os.environ.get("CLAUDE_MODEL", "")


def load_sessions() -> dict[str, str]:
    if SESSION_PATH.is_file():
        try:
            return json.loads(SESSION_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_sessions(sessions: dict[str, str]) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps(sessions, indent=2))


def split_into_chunks(text: str, limit: int = TG_MAX) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(paragraph) > limit:
            for line in paragraph.split("\n"):
                if len(current) + len(line) + 1 > limit:
                    if current:
                        chunks.append(current)
                    current = line[:limit]
                else:
                    current = f"{current}\n{line}" if current else line
            continue
        if len(current) + len(paragraph) + 2 > limit:
            if current:
                chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


async def safe_edit(msg: Message, text: str) -> None:
    try:
        await msg.edit_text(text[:TG_MAX])
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            LOG.warning("edit failed: %s", e)


def _build_preview(tools: list[str], text: str) -> str:
    parts: list[str] = []
    if tools:
        compact: list[str] = []
        for name in tools:
            base = compact[-1].split("×")[0] if compact else ""
            if compact and base == name:
                count = int(compact[-1].split("×")[1]) if "×" in compact[-1] else 1
                compact[-1] = f"{base}×{count + 1}"
            else:
                compact.append(name)
        parts.append("🔧 " + " → ".join(compact))
    if text:
        parts.append(text[-1500:])
    body = "\n\n".join(parts) if parts else "Thinking…"
    return body[:TG_MAX]


async def stream_claude(
    prompt: str,
    session_id: str | None,
    status_msg: Message,
) -> tuple[str, str | None, str]:
    argv = [
        CLAUDE_BIN,
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
    ]
    if CLAUDE_MODEL:
        argv += ["--model", CLAUDE_MODEL]
    if session_id:
        argv += ["--resume", session_id]
    argv.append(prompt)

    LOG.info("invoking: %s", shlex.join(argv))

    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=CLAUDE_CWD,
    )

    final_text = ""
    accumulated = ""
    tool_calls: list[str] = []
    last_edit = 0.0
    last_preview = "Thinking…"  # matches the initial status_msg text
    new_sid = session_id
    stderr_chunks: list[str] = []
    # With --include-partial-messages we get text incrementally via
    # stream_event/content_block_delta. The complete assistant event still
    # arrives later carrying the same text; track whether we already streamed
    # it to avoid double-counting.
    streamed_partial_text = False

    async def drain_stderr() -> None:
        assert proc.stderr is not None
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            stderr_chunks.append(line.decode(errors="replace"))

    stderr_task = asyncio.create_task(drain_stderr())

    try:
        assert proc.stdout is not None
        while True:
            try:
                raw = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=CLAUDE_TIMEOUT_SEC
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return (
                    f"[error: claude timed out after {CLAUDE_TIMEOUT_SEC}s]",
                    session_id,
                    last_preview,
                )
            if not raw:
                break

            line = raw.decode(errors="replace").strip()
            if not line:
                continue

            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue

            ev_type = ev.get("type")

            if ev_type == "system":
                if ev.get("subtype") == "init":
                    sid = ev.get("session_id")
                    if sid:
                        new_sid = sid

            elif ev_type == "stream_event":
                # Partial-message delta. Accumulate text as it arrives so the
                # status preview shows live typing instead of waiting for the
                # full turn to complete.
                inner = ev.get("event", {})
                if inner.get("type") == "content_block_delta":
                    delta = inner.get("delta", {})
                    if delta.get("type") == "text_delta":
                        accumulated += delta.get("text", "")
                        streamed_partial_text = True

            elif ev_type == "assistant":
                content = ev.get("message", {}).get("content", [])
                for block in content:
                    btype = block.get("type")
                    if btype == "text" and not streamed_partial_text:
                        # No partial deltas were observed for this turn —
                        # safe to take the complete text from the assistant event.
                        accumulated += block.get("text", "")
                    elif btype == "tool_use":
                        name = block.get("name", "tool")
                        tool_calls.append(name)
                        tool_calls[:] = tool_calls[-8:]
                # Each assistant turn ends here. Reset the partial-streamed
                # flag so the NEXT turn's text is captured from whichever
                # source actually appears.
                streamed_partial_text = False

            elif ev_type == "result":
                final_text = ev.get("result") or accumulated
                sid = ev.get("session_id")
                if sid:
                    new_sid = sid

            now = time.monotonic()
            if now - last_edit >= EDIT_THROTTLE_SEC:
                preview = _build_preview(tool_calls, accumulated)
                if preview and preview != last_preview:
                    await safe_edit(status_msg, preview)
                    last_preview = preview
                last_edit = now

        await proc.wait()
        await stderr_task

        if proc.returncode != 0:
            stderr = "".join(stderr_chunks)[-600:] or "(no stderr)"
            return (
                f"[error: claude exit {proc.returncode}]\n{stderr}",
                new_sid,
                last_preview,
            )

        return (
            final_text.strip() or accumulated.strip() or "[error: empty]",
            new_sid,
            last_preview,
        )
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or user.id not in ALLOWED:
        if update.message:
            await update.message.reply_text(
                f"Access denied. Your Telegram user ID is {user.id if user else '?'}."
            )
        return
    if update.message:
        await update.message.reply_text(
            "Connected to Claude. Send any message; /reset starts a fresh session."
        )


async def cmd_reset(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or user.id not in ALLOWED:
        return
    sessions = load_sessions()
    sessions.pop(str(user.id), None)
    save_sessions(sessions)
    if update.message:
        await update.message.reply_text("Session reset.")


async def cmd_whoami(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if update.message and user:
        await update.message.reply_text(
            f"user_id={user.id}\nusername={user.username}\nallowed={user.id in ALLOWED}"
        )


async def on_message(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.message
    if not user or not msg or not msg.text:
        return
    if user.id not in ALLOWED:
        await msg.reply_text(
            f"Access denied. Your Telegram user ID is {user.id}."
        )
        return

    sessions = load_sessions()
    sid = sessions.get(str(user.id))

    await msg.chat.send_action(ChatAction.TYPING)
    status_msg = await msg.reply_text("Thinking…")

    final_text, new_sid, last_preview = await stream_claude(msg.text, sid, status_msg)

    if new_sid and new_sid != sid:
        sessions[str(user.id)] = new_sid
        save_sessions(sessions)

    chunks = split_into_chunks(final_text) or ["[empty response]"]
    if chunks[0][:TG_MAX] != last_preview:
        await safe_edit(status_msg, chunks[0])
    for chunk in chunks[1:]:
        await msg.reply_text(chunk)


def main() -> None:
    if not TG_BOT_TOKEN:
        raise SystemExit(f"TG_BOT_TOKEN not set (checked {CONFIG_PATH} and env)")
    if not ALLOWED:
        LOG.warning(
            "TG_ALLOWED_USER_IDS empty -- bootstrap mode: only /whoami works. "
            "Message the bot /whoami, then add your numeric ID to %s.",
            CONFIG_PATH,
        )

    LOG.info("starting bot; %d user(s) whitelisted; cwd=%s", len(ALLOWED), CLAUDE_CWD)

    app = Application.builder().token(TG_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
