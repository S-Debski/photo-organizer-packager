## Current (v3.0)

See [[File Responsibilities (Design Contract)]] → v3.0 Modules for the authoritative list.

---
## main.js

- Steps: 1 Card · 2 Folders · 3 Browse & cull · 3b Review · 4 Cameras & lenses · 5 Locations · 6 Import
- Cameras & lenses: per photo, from scanner records (`/api/exif-records`); RAW+JPG pair counts once
    - No Chart.js; list with bars
- Folder switching anywhere: `activateFolder()`
- Grid: `/api/thumb` previews, S/M/L size, pinned header
- Import: shoot folder panel (`initShootPanel`), preview, Send to phone panel

---
## sdcard.py

- See [[12 - Sources (Cards, Drives, Folders)]]
- Replaces the v2 rules below (label exclusions, removable/DCIM inclusion)

---
## reader.py / lens.py

- `reader.py` → **only** talks to ExifTool (`-json -n -G1`)
- Batched reads (`prefetch_exif`), cache keyed on path + size + mtime
- Missing ExifTool → `{}` (logged at start‑up: "ExifTool not found")
- `lens.py` → interprets EXIF

---
## Superseded (v2 notes, kept for history)

MAIN.js
From your `main.js`, Step 3 is **purely derived state**:

- Inputs:
    - `analyzedFolders` (from Analyze)
- Derived:
    - `cameraStats[camera_model] += photo_count`
    - `lensStats[lens] += photo_count`
- Output:
    - List groups (camera + lens)
    - Two bar charts (Chart.js)
- Trigger:
    - Clicking the sidebar item for Step 3

SD_CARDS.py
Detects Camera cards not cloud drives
### HARD EXCLUSIONS (must happen first)

A drive is **never** an SD card if its label or path contains:

- `google`
- `my drive`
- `onedrive`
- `dropbox`
- `icloud`
- `box`

### POSITIVE INCLUSION

A drive is an SD card if **any** of these are true:

1. Windows reports it as **removable**
2. It contains a `DCIM` directory at root
