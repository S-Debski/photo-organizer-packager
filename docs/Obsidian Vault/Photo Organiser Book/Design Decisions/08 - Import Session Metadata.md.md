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