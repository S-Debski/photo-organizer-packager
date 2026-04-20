# Directory Template Resolution

  

## Purpose

Derive a deterministic destination subdirectory from explicit Pre‑Import inputs. Directory templates influence layout only and do not affect Organize guarantees.

  

---

## Pipeline Position

Source

    ↓

Mapping (informational)

    ↓

Pre‑Import (session metadata, destination selection)

    ↓

Organize (safe copy)

  

---

## Core Rules

- Template resolution is optional

- No directories are created during Pre‑Import

- Final destination is resolved before Organize starts

- Resulting path is immutable per run

  

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