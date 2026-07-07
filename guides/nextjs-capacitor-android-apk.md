# Turn a Next.js app into an Android APK with Capacitor — built on Linux, no Android Studio

Wrap an existing Next.js web app in a native Android shell and hand out a
real APK — built entirely from the command line on a Linux machine (works on
ARM, e.g. a Raspberry Pi). No Android Studio, no Google Play account.

Two architectures to choose from:

| Mode | How it works | Use when |
|------|--------------|----------|
| **Server-backed** (this guide's default) | The APK is a thin WebView pointing at your running Next.js server | The app needs API routes/SSR/a database — most real apps |
| **Fully offline** | `next export` static files bundled inside the APK | Pure client-side apps only: no API routes, no SSR |

## Prerequisites

- A working Next.js app.
- Node 18+ (note: **Capacitor 5/6 work on Node 18; the newest Capacitor
  releases require Node 22+** — pick the major that matches your Node).
- Java 17 (`sudo apt install openjdk-17-jdk`).
- ~5 GB disk for the Android SDK.

## 1. Install the Android SDK (command line only)

```bash
mkdir -p ~/android-sdk/cmdline-tools
cd ~/android-sdk/cmdline-tools
# Get the current "commandlinetools-linux-....zip" URL from
# https://developer.android.com/studio#command-line-tools-only
wget https://dl.google.com/android/repository/PUT_CURRENT_VERSION_HERE.zip
unzip PUT_CURRENT_VERSION_HERE.zip && mv cmdline-tools latest

export ANDROID_HOME=$HOME/android-sdk
export ANDROID_SDK_ROOT=$HOME/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin

sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
yes | sdkmanager --licenses
```

Add the three `export` lines to your `~/.bashrc` — every build needs them.

## 2. Add Capacitor to the project

```bash
npm install @capacitor/core @capacitor/cli @capacitor/android
npx cap init "My App" "com.example.myapp" --web-dir public
npx cap add android
```

Two traps right here:

- **The project folder name must be ASCII.** A path with e.g. Swedish
  characters (`beställningar/`) breaks the Android tooling — make sure
  `package.json`'s `name` and the directory are plain ASCII.
- **Use `capacitor.config.json`, not `capacitor.config.ts`.** The TypeScript
  config is sometimes silently ignored by the native tooling; JSON always
  works.

## 3. Point the shell at your server

`capacitor.config.json` for the server-backed mode:

```json
{
  "appId": "com.example.myapp",
  "appName": "My App",
  "webDir": "public",
  "server": {
    "url": "http://192.168.1.10:3000",
    "cleartext": true
  }
}
```

- `server.url` is your Next.js server — a LAN IP for a home app, or an
  `https://` URL for a public one.
- `cleartext: true` is required for plain `http://` (Android blocks it by
  default). Only acceptable for LAN-only apps; with an HTTPS URL, remove it.
- `webDir` is almost unused in this mode (the WebView loads the server), but
  Capacitor requires it to exist and contain an `index.html` — `public/`
  with any placeholder file satisfies it.

## 4. Build the APK

```bash
export ANDROID_HOME=$HOME/android-sdk
export ANDROID_SDK_ROOT=$HOME/android-sdk

npx cap sync android
cd android && ./gradlew assembleDebug
cp app/build/outputs/apk/debug/app-debug.apk ../myapp.apk
```

First Gradle run downloads ~1 GB and takes a while (on a Pi: go make
coffee); later builds are much faster.

Install it: copy `myapp.apk` to the phone (or serve it from your server and
download it in the phone's browser), open, and allow "install unknown apps".

> A **debug** APK is fine for personal/family use. Publishing to Play
> requires a signed release build (`assembleRelease` + a keystore) — out of
> scope here.

## 5. Make the Android back button behave

Out of the box the system back gesture may exit your app instead of
navigating back in the WebView. Two pieces:

1. In `android/app/src/main/AndroidManifest.xml`, on the `<application>`
   element, make sure you do **not** enable the new predictive-back opt-in
   unless you handle it (`android:enableOnBackInvokedCallback="false"` is the
   safe value with `targetSdk 34`).
2. Handle back in JavaScript with Capacitor's App plugin:

```ts
import { App } from "@capacitor/app";

App.addListener("backButton", ({ canGoBack }) => {
  if (canGoBack) window.history.back();
  else App.exitApp();
});
```

(`npm install @capacitor/app`, then `npx cap sync android` again.)

## 6. Iterating

The shell only wraps a URL, so day-to-day you just deploy your Next.js app
as usual — **the APK doesn't need rebuilding for web changes.** Rebuild only
when you change `capacitor.config.json`, plugins, icons, or anything under
`android/`.

## Gotchas checklist

| Symptom | Cause / fix |
|---------|-------------|
| Blank white screen on launch | The phone can't reach `server.url` — wrong IP, server down, or phone on another network. Test the URL in the phone's browser first. |
| `net::ERR_CLEARTEXT_NOT_PERMITTED` | Plain `http://` without `"cleartext": true`. |
| Build explodes on paths with non-ASCII characters | Rename the folder / `package.json` name to ASCII (see step 2). |
| `capacitor.config.ts` changes have no effect | Use `capacitor.config.json` (see step 2). |
| Capacitor CLI refuses to run | Node too old for that Capacitor major — check the version table in Capacitor's docs; on Node 18, install Capacitor 5/6 (`npm i @capacitor/cli@5`). |
| `SDK location not found` | The `ANDROID_HOME`/`ANDROID_SDK_ROOT` exports are missing in this shell. |
| Back gesture exits the app immediately | Step 5 not done. |
| **Shell dies during cleanup** | Never `rm -rf android` while your shell's working directory is inside `android/` — `cd` out first. |
