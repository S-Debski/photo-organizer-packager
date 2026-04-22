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

✅ No backend calls  
✅ No mutation of session state  
✅ No coupling to Pre‑Import or Organize

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

### ✅ POSITIVE INCLUSION

A drive is an SD card if **any** of these are true:

1. Windows reports it as **removable**
2. It contains a `DCIM` directory at root

===================================================
- `reader.py` → **only** talks to ExifTool
- `lens.py` → interprets EXIF

photo_core/exif/reader.py
------------------------------------------------------------
ExifTool wrapper with caching

- Uses exiftool (industry standard)
- Reads EXIF + XMP + MakerNotes
- Cached for performance
- OS-agnostic
------------------------------------------------------------

### Design notes (important)

- Uses **`-json`** → stable, machine‑readable
- Uses **LRU cache** → extremely fast after first read
- Raises a clear error if exiftool is missing
- Does **not** guess or normalise yet (that’s higher‑level logic)


photo_core/exif/lens.py
Lens resolution logic


