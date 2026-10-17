# Directory Template Resolution

  

## Purpose

Derive a deterministic destination subdirectory from explicit Pre‑Import inputs. Directory templates influence layout only and do not affect Organize guarantees.

  

---

## Pipeline (High‑Level)

Source
  ↓
Mapping (informational)
  ↓
Pre‑Import (session metadata, destination selection)
  ↓
Organize (safe copy)

## Pre‑Import (Detailed)

Mapping (informational only)
  ↓
Pre‑Import
   ├─ session metadata
   ├─ directory template selection
   ├─ preview + validation
   ├─ user confirmation
   └─ ctx freeze
  ↓
Organize (copy only)

---

## Core Rules

- Template resolution is optional
- No directories are created during Pre‑Import
- Final destination is resolved before Organize starts
- Resulting path is immutable per run
- The session title should be derived from the first directory _below_ `DCIM` that actually contains images.

  

---

## Inputs
Template resolution may reference:
- Session title
- User‑supplied shoot date
- Static path segments

No EXIF metadata is used directly.

---

## Template Characteristics

- Deterministic

- Previewable

- Free of side effects

- Does not modify filenames

  

Templates expand to a relative path only.

  

---

## Resolution Flow

- User selects or accepts a template

- Template expands to a relative subpath

- Subpath is joined with `ctx.output_dir`

- Resolved path is shown for confirmation

  

No implicit fallbacks.

  

---

## Relationship to Organize

Organize:

- Receives a fully resolved destination path

- Does not evaluate templates

- Copies files only

- Applies unchanged guarantees

  

---

## Failure Behaviour

If template resolution fails:

- No files are copied

- No directories are created

- Operation aborts safely

## Directory Templates — Default

**Default template:**

{YYYY}/{MM}/{DD} - {title}

### Rationale
- Chronological sorting at all levels
- Human‑readable folder names
- Collision‑resistant
- Industry‑standard practice for photography archives

### Scope
- Applies to new sessions by default
- User‑editable during Pre‑Import
- No automatic changes to existing sessions

### Notes
- EXIF is not used for directory naming directly; it informs the default title/date only
- Title is sanitized before substitution (`< > : " / \ | ? *` → `-`)

---
## Offered Layouts (v3.0)

| Layout | Template | Example |
|---|---|---|
| Year / Month / Day - Title (default) | `{YYYY}/{MM}/{DD} - {title}` | `2026/10/10 - Wylam Waggonay Bike Ride` |
| Year / Date - Title | `{YYYY}/{date} - {title}` | `2026/2026-10-10 - Wylam…` |
| Date - Title | `{date} - {title}` | `2026-10-10 - Wylam…` |
| Title only | `{title}` | `Wylam Waggonay Bike Ride` |
| Card folder name (old layout) | — | `<path below DCIM> - <card label>` |

- Tokens: `{title}` `{YYYY}` `{YY}` `{MM}` `{DD}` `{date}`
- Layout choice is remembered per browser
- Old layout sends no title; backend uses the legacy name

---
## Resolution & Validation (v3.0)

- One resolver for preview and import: **`photo_core/organize/destination.py`** `resolve_destination()`
- Preview: `POST /api/pre-import/preview` — path only; creates nothing
- Refused before any directory is created:
    - destination missing, or a file
    - destination on the card or inside the source folder
    - unknown token, absolute path, drive letter, `..`
    - resolved path outside the destination
    - destination not writable
- Preview shows root + highlighted relative part; states "new folder" or "exists — files skipped"

---
## Answered Questions (v3.0)

- DCIM‑subfolder rule → kept, plus named‑folder rule: see [[Infer title from date and let user edit details]]
- Multiple shoot folders → one import per folder; each has its own title/date/ownership
- Mixed cameras → irrelevant to layout; stats are per photo
- Empty cards → analysis reports zero folders; import refused ("no photos")
- `date.today()` → replaced: earliest capture date, else folder‑name date, else today (stated)
- Reset → "Reset title and date to the card's" link
- `photo_count` → counts files (RAW+JPG pair = 2)
- Chart.js → removed; per‑photo list with bars replaces it