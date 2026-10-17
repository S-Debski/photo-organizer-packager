# Culling Sessions
#design #v3.0

Backlink: [[Stability Contract]] · [[07 - Pre‑Import Workflow]]

## Purpose

Persist keep/reject decisions per folder so culling survives reloads and restarts — for the same photos only.

---
## Manifest

- Owner: **`photo_core/pre_import/session_state.py`**
- Location: `sessions/<name>_<timestamp>/session.json`; atomic writes (temp + replace)
- Per asset (RAW/JPG pair by stem):

```text
{ asset_id, raw_source, jpg_source,
  decision: "keep" | "reject" | null,
  selected: decision == "keep",
  sizes: { "DSCF0001.JPG": 8241034, ... },
  copied: { raw, jpg } }
```

- `imports[]` log: time, mode, destination, copied, skipped, clashes, errors, location

---
## Lifecycle

Folder opened
    ↓
`POST /api/session/create` → find matching session, else create
    ↓
Register every RAW/JPG pair in the folder
    ↓
Decisions restored to the UI
    ↓
Each change → `POST /api/session/select` (queued, in order)

---
## Resume Rule (same photos, not same path)

A session resumes only when made from the photos now in the folder:

- Same `source_folder` path, and
- With recorded sizes: ≥ 1 match and ≥ 50 % of recorded files still present by name also match by size
- Legacy manifests (no sizes): ≥ 90 % photo‑name overlap both ways
- Most recent matching session wins

Rationale: the next card in the same reader slot has the same path (`F:\DCIM\100_FUJI`) and often the same names (`DSCF0001`); sizes differ.

---
## Guarantees

- Unknown asset ids are registered, never dropped
- Rapid toggles cannot be applied out of order
- Counts: kept / rejected / unculled reported separately
- Closing a session keeps it on disk
- A different card never inherits decisions (tested)
