# Send to Phone
#design #v3.0

Backlink: [[Stability Contract]] · [[Organize – Behaviour & Guarantees]]

## Purpose

Copy an imported shoot onto an Android phone over USB. The app only copies to the phone; it uploads nothing. The phone's own backup (e.g. Google Photos on the author's Pixel XL, free original‑quality storage) takes it from there.

---
## Pipeline

Import completes
    ↓
"Send to phone" panel (Import step)
    ↓
`POST /api/pixel/send` (background) → progress via `/api/pixel/result`
    ↓
adb push → `/sdcard/DCIM/PhotoOrganizer/`
    ↓
Media scan per file

---
## Rules

- Reads the imported copies only; refuses card paths
- One phone folder for every shoot — a phone backup app is pointed at it once
- JPG by default; RAW optional ("Include RAW files")
- Never overwrites on the phone:
    - same name + same size → skipped (safe to re‑send)
    - same name, different size → numbered (`DSCF0001_2.JPG`)
- States shown: tools not installed · no phone · "Allow USB debugging" pending · ready
- Background job uses `ctx.progress` stage `pixel`

---
## adb (Android SDK Platform‑Tools)

- Not bundled (Google licence); found in order:
    - `PHOTO_ORGANIZER_ADB`
    - `PATH`
    - `C:\Users\Public\Tools\platform-tools\adb.exe` (beside ExifTool)
    - Android SDK `platform-tools`; Homebrew (`/opt/homebrew/bin/adb`)
- Phone: Developer options → USB debugging on; accept the computer's key once

---
## Files

- **`photo_core/export/pixel.py`** — resolve adb, list devices, plan names, push, scan
- `backend/api_server.py` — `/api/pixel/status`, `/send`, `/result`
- `tests/fake_adb.py` — stand‑in adb emulating a phone for tests

---
## Non‑Goals

- Uploading to Google Photos or any cloud service (possible future option for other users)
- iPhone / MTP file transfer without adb
