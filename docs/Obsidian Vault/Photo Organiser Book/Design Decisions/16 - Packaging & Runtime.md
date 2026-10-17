# Packaging & Runtime
#design #v3.0 #packaging

Backlink: [[Stability Contract]] · [[Platform Testing]]

## Purpose

Standalone desktop app for Windows and macOS (Linux later). No Python install needed.

---
## Runtime Model

App start
    ↓
Second launch? → open the running instance's page, exit
    ↓
Flask + EXIF scanner in background threads
    ↓
Main thread: tray (Windows) / menu‑bar (macOS) icon — Open, Quit
    ↓
Browser opens `http://127.0.0.1:5000`

- Owner: **`app.py`**, **`tray/tray_icon.py`**
- No console; stdout/stderr → log file (append, rolls over at 2 MB)
    - Windows: `%LOCALAPPDATA%\PhotoWizardCache\photo-organizer.log`
    - macOS: `~/Library/Logs/PhotoOrganizer/photo-organizer.log`
- macOS: menu‑bar only (`LSUIElement`), no Dock icon
- Same‑origin UI; no CORS
- Front‑end libraries local (`ui/static/libs`) — offline except map tiles

---
## ExifTool

- Bundled into `<bundle>/exiftool/`
    - Windows: `exiftool.exe` + `exiftool_files/`
    - macOS: `exiftool` script + `lib/` only, run by the system Perl (the distribution's `t/` test files break code signing)
- Lookup: `PHOTO_ORGANIZER_EXIFTOOL` → bundled → `PATH` → Homebrew paths
- Subprocess rules: UTF‑8 decode, `stdin=DEVNULL`, no console window (`CREATE_NO_WINDOW`)
- Batched reads: one process per 200 files (`prefetch_exif`)

---
## Build

- Spec: **`photo-organizer.spec`** (one spec, both platforms)
- Windows: `build.bat` → `dist\Photo Organizer\Photo Organizer.exe`
- macOS: `build_mac.sh` → `dist/Photo Organizer.app` + `PhotoOrganizer-mac.zip`; ad‑hoc signed
- CI: `.github/workflows/build.yml` — Actions → "Build desktop apps" → Run workflow, or a `v*` tag
- ExifTool downloads come from SourceForge (exiftool.org links there)
- `templates/*.html` must stay un‑ignored in `.gitignore`; `*.sh` keeps LF endings (`.gitattributes`)

---
## Install

- Windows: unzip; keep `Photo Organizer.exe` with `_internal\`; SmartScreen → More info → Run anyway
- macOS: unzip; first open with right‑click → Open
    - If blocked ("damaged" / "can't be verified"):

```text
xattr -dr com.apple.quarantine ~/Downloads/"Photo Organizer.app"
```

    - Allow access to removable volumes when asked
