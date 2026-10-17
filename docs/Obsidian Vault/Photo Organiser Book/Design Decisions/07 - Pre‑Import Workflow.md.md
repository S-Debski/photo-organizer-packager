# Pre‑Import

## Purpose

Explicit non‑destructive decisions before import. Selection + destination only. Organize guarantees unchanged.

---
## Pipeline

Source
    ↓
Mapping (read‑only)
    ↓
Pre‑Import (destination, culling)
    ↓
Organize (safe copy)

---
## Guarantees

- Source untouched
- No writes pre‑Organize
- Selection only
- Organize unchanged
---
## Destination Selection

### When

After Mapping, before Organize. Immutable once started.
### Validation

- Path exists
- Writable
- Directory
- Not source or subdir

Failure fatal. No copy until valid.
### Immutability

- `ctx.output_dir` fixed
- No alternate outputs
- All writes under destination

---
## Culling

### Rules

- Optional
- Default none
- Source untouched
- Organize unchanged
### Excluded

- Not passed to Organize
- Not copied
- Remains at source
- May be included later

Selection only.

### Reversibility

- No source state
- No irreversible actions
- Changeable pre‑Organize

### Ambiguity

- No auto‑exclude
- Ambiguity surfaced
- Explicit intent required

---
## Mapping

- Informational only
- No decisions
- No thresholds
- No authority

---
## Organize

- Receives final input set
- Unaware of Pre‑Import
- Guarantees unchanged

---
## Failure

- No files copied
- No dirs created
- No partial selection
- Abort safely

---
## ctx

### ctx.output_dir

- Absolute path
- Set pre‑import
- Immutable during run

Single write root.

### ctx.destination_source

- enum
  - fixed (v2.7)
  - user_selected (v2.8+)

Diagnostics only.

### ctx.pre_import

```text

{destination_confirmed:true,culling_applied:false}


## Metadata Intent (GPS)

Pre-Import may capture metadata intent but must not apply it.

Example:
- Manual GPS selection from Mapping step

Stored as:
- `ctx.manual_gps = { lat, lon }`

### Rules
- Must be explicit user input
- Must be previewable
- Must be mutable until execution starts
- Must be frozen before Organize executes
- Must not trigger file mutation

### Notes
- This is informational at this stage
- Actual EXIF writing occurs at import, on the copies only (see [[11 - Post-Organize (Metadata Mutation)]])

---
## v3.0 — Hybrid Ingest

Source browsed in place; nothing copied before culling.

Source (card / drive / folder)
    ↓
Browse & cull (K / X)
    ↓
Locations (optional)
    ↓
Import (destination + shoot folder + preview)

### Culling Persistence
- Decisions: `keep` | `reject` | unculled; stored per asset in the session manifest
- Asset = RAW/JPG pair sharing a filename stem
- Saved on every change; requests serialised (no out‑of‑order saves)
- Restored on reload and on reopening the same photos
- See [[13 - Culling Sessions]]

### Import Modes
- `kept`: kept files + same‑stem partners/sidecars (RAW, JPG, `.xmp`)
- `kept` with nothing kept → refused; never falls back to all
- `all`: every recognised file in the folder

### Destination Validation
- See [[09 - Directory Template Resolution (Pre‑Import)]]
- Never on the card or inside the source

### Metadata Intent (v3.0)
- Locations persist on disk until import: [[08 - Import Session Metadata]]
- `ctx.manual_gps` superseded by per‑folder saved locations