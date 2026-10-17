# Import Session Metadata

## Purpose
Capture explicit user intent for an import session. Session metadata provides human meaning and corrects unreliable or missing camera metadata. Does not modify source files or affect Organize guarantees.

---
## Pipeline Position
Source
    ↓
Mapping (read‑only, informational)
    ↓
Pre‑Import
    - Session metadata
    - Destination selection
    - Optional culling
    ↓
Organize (safe copy only)

---

## Core Rules
- Session metadata is optional
- No source files are modified
- No metadata is written to photos
- Organize behaviour is unchanged

---

## Session Fields

### Title
- Free‑text, user‑supplied
- Describes subject or shoot
- Informational only

Examples:
- Lake District Walk
- Wedding Reception
- Studio Portraits

---

### Shoot Date
- Explicit user‑supplied date
- Represents actual date photos were taken
- May differ from EXIF timestamps

Rationale:

- EXIF may be missing
- EXIF may be incorrect due to camera misconfiguration
- User intent supersedes inferred values

Mapping may suggest candidate dates.

Final value is explicit user intent.

---

## Relationship to EXIF

- EXIF timestamps are not modified
- EXIF is not corrected or rewritten
- EXIF is used only as informational input
- No automatic inference or extrapolation

Session date does not assert EXIF accuracy.

---

## Relationship to Destination Layout

Session metadata may be used to derive a subdirectory under `ctx.output_dir`.
- All derived paths are previewable
- Layout is resolved before Organize starts
- Final destination is immutable per run

Session metadata does not mandate any directory structure.

---

## Relationship to Organize
Organize:
- Does not interpret session metadata
- Receives a resolved destination path
- Copies files only
- Applies identical guarantees regardless of session data

---

## Failure Behaviour

If session metadata capture fails or is aborted:
- No files are copied
- No directories are created
- Operation aborts safely

---

## Context (`ctx`)
  

### ctx.session
- Structured object
- Captures import intent only
- Immutable once Organize begins

Example:

```text

ctx.session = {

  title: "Lake District Walk",

  shoot_date: "2024-09-15"

}
### Manual GPS

- Stored as part of session metadata:
  - `ctx.manual_gps`

- Represents user-defined location override

### Lifecycle
- Set during Mapping
- Stored during Pre‑Import
- Applied during Post‑Organize

### Constraints
- Must not be inferred
- Must not be modified after ctx is frozen

---
## v3.0 Implementation

### Title & Shoot Date
- Defaults and ownership: [[Infer title from date and let user edit details]]
- Edited on the Import step; per shoot folder

### Location (supersedes `ctx.manual_gps`)
- Assigned per shoot folder on the Locations step
- "Use for all folders" assigns one location to every folder on the card
- Saved: `sessions/locations.json` via `/api/locations`
- Key: folder path + first photo name + size (a new card in the same slot does not inherit it)
- Survives restart; removable ("Remove location")
- Saved places offer reusable coordinates: [[14 - Saved Places]]

### Application (at import, copies only)
- JPG → EXIF GPS with N/S/E/W ref tags (`write_gps_tags`)
- RAW → XMP sidecar `<stem>.xmp`, created or updated (`write_gps_sidecar`)
- Written after copying, so a sidecar copied from the card is updated, not clashed
- Source never written: `write_gps.py` defers any path under the card/source

### Fields No Longer Used
- `ctx.state["title"]`, `ctx.state["shoot_date"]` (set by analyse; ignored)
