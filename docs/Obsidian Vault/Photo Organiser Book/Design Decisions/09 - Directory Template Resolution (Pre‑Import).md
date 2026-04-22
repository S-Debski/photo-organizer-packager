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
- EXIF is not used for directory naming at this stage
- Title is sanitized before substitution
- **Questions to ask**

- Is the DCIM‑subfolder rule exactly what you want?
- What happens with:
    - multiple shoot folders?
    - mixed cameras?
    - empty cards?
- Is `date.today()` still acceptable, or do you want EXIF‑earliest next?
- “Reset title/date to card defaults”?

assumes:
each folder’s photo_count is reliable
photos belong to exactly one camera/lens

Questions to answer:
Does photo_count reflect files, not folders?
Are mixed‑camera folders possible?

chart.js - Does the chart add value over the list, or is it redundant?