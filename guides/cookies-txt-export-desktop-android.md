# Export a `cookies.txt` for yt-dlp / gallery-dl (desktop and Android)

Many self-hosted media tools — `yt-dlp`, `gallery-dl`, and anything built on
them — can act on a site *as you* by loading an exported cookie file. That's
what lets them fetch content that's behind a login, age-gated, or
rate-limited for anonymous visitors (Instagram, for instance, blocks
anonymous profile reads almost immediately; public TikTok profiles usually
download fine without one).

This guide covers the one format those tools expect, how to export it from a
**desktop** browser, how to export it from an **Android** phone or tablet
(which normally can't run extensions), where the file goes, and how to keep
it working.

## What you'll need

- A browser logged in to the target site as the account you want the tool to
  use. **Use a secondary / throwaway account** where automation risks a ban —
  see [Safety](#safety).
- A "cookies.txt" exporter — a browser extension or userscript (below).
- Somewhere to put the file that your tool reads from.

## Glossary

- **Netscape `cookies.txt`** — the classic tab-separated cookie file format
  (each line: domain, flag, path, secure, expiry, name, value). It starts with
  `# Netscape HTTP Cookie File`. This is what `yt-dlp` and `gallery-dl`
  consume. **A JSON cookie export will not work** — you specifically need a
  `cookies.txt` exporter.
- **`#HttpOnly_` prefix** — some exporters prefix HttpOnly cookie lines with
  `#HttpOnly_`. That's correct; leave it. (The Python stdlib cookie jar drops
  those, so a good loader re-adds handling for them — don't strip the prefix
  yourself.)

## 1. Desktop export (easiest)

1. Log in to the target site in Chrome, Edge, or Firefox.
2. Install a cookies exporter extension. A widely used one is
   **"Get cookies.txt LOCALLY"** (Chrome and Firefox) — the *LOCALLY* variant
   keeps everything on-device, which matters because a cookie file is a live
   credential.
3. With the site's tab focused, open the extension and **Export** →
   save the file as `cookies.txt`.

That's it — skip to [Where the file goes](#3-where-the-file-goes).

## 2. Android export (phone / tablet)

The catch on Android: normal mobile Chrome has no extension support, so the
easy desktop route isn't available. Two ways around it:

### Option A — a Chromium build with extensions (recommended)

**[Ultimatum](https://github.com/gonzazoid/Ultimatum)** is a Chromium fork for
Android (ARM64) that adds desktop-style **webextension support** — it can run
a `cookies.txt` exporter exactly like desktop Chrome. Tested extensions
include uBlock Origin and Tampermonkey.

1. Install Ultimatum. It's distributed as an APK / built from source (it is
   **not** on the Play Store) — follow the instructions in its repository.
2. In Ultimatum, install a cookies exporter (e.g. **Get cookies.txt LOCALLY**
   from the Chrome/Opera store, or a Tampermonkey userscript that dumps
   `cookies.txt`).
3. Log in to the target site in Ultimatum, run the extension, and export
   `cookies.txt`.
4. Move the file to wherever your tool runs (SFTP, a network share, or
   `scp`/`docker cp`).

> **Security caveats (from Ultimatum's own README):** it does **not** show a
> permission-confirmation prompt when an extension requests elevated access,
> and some Chrome APIs are incomplete. Only install extensions you trust,
> prefer a *local-only* cookies exporter, and lean on a dedicated/throwaway
> account rather than your main login.

### Option B — export on a desktop instead

If you'd rather not install a custom browser, just do the desktop export
(section 1) on any computer and copy the file to your server. A cookie file
isn't device-bound — one exported on desktop works fine for a tool running
elsewhere.

(There are also rooted-device / ADB methods to pull a browser's cookie
database directly, but they're far more fiddly than either option above.)

## 3. Where the file goes

This depends on the tool. As a rule it's either a path you pass on the command
line or one set by config/environment:

- **`yt-dlp`:** `yt-dlp --cookies /path/to/cookies.txt <url>`
- **`gallery-dl`:** `gallery-dl --cookies /path/to/cookies.txt <url>`, or a
  `cookies` entry in `gallery-dl.conf`.
- **A containerized app:** put the file on the **host** side of a bind mount
  and point the tool's cookie path/variable at the in-container path. A common
  convention is a per-service folder, e.g.
  `/srv/<service>/cookies/cookies.txt`.

### Rotating several accounts

Some tools support a *pool* of cookie files to spread rate limits across
accounts — often "a default `cookies.txt` plus one per subfolder", with a
blocked account automatically cooled down and skipped for a while. If yours
does, the layout usually looks like:

```
cookies/
├── cookies.txt          # default account
├── acct-a/cookies.txt
└── acct-b/cookies.txt
```

Check your tool's docs for whether it scans subfolders like this.

## 4. Verifying and refreshing

- **Verify:** run the tool once and watch its log — a good one reports whether
  it loaded a working cookie (e.g. `cookies: present` vs
  `none (public download)`).
- **They expire:** logged-in sessions die periodically — you log out, change
  your password, or the site invalidates the session server-side. When
  fetches suddenly fail with auth/login errors, **re-export a fresh
  `cookies.txt` and replace the file.** Most tools pick up the new file on the
  next run with no restart.
- **Pace yourself:** if the tool exposes delay/rate-limit settings, use them.
  Hammering a site while logged in is the fastest way to get the account
  flagged.

## Safety

- Automated access usually violates a site's Terms of Service and can get the
  account **restricted or banned**. Use a secondary account you don't care
  about — never your main one.
- `cookies.txt` **is** a login credential — anyone with the file is logged in
  as that account. Keep it readable only where it's needed, never commit it to
  a repo, and delete or rotate it when it's no longer in use.

## Troubleshooting

| Symptom | Likely cause / fix |
| ------- | ------------------ |
| Tool says the cookie file is invalid or empty | You exported JSON, not Netscape `cookies.txt`. Use a `cookies.txt`-specific exporter. |
| Worked yesterday, now "login required" | Session expired — re-export and replace the file. |
| HttpOnly cookies seem missing | Don't strip `#HttpOnly_` lines; a correct loader needs them. |
| Android: no way to run the exporter | Use Ultimatum (Option A) or just export on desktop (Option B). |
| Account got restricted | You were logged in during heavy automated access. Use a throwaway account and slow the request rate. |
