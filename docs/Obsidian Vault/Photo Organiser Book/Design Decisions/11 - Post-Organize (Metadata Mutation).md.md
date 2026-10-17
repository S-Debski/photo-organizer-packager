# Post‑Organize (Metadata Mutation)
#architecture #stability

Backlink:
[[Stability Contract]]

---

## Role

- Applies metadata updates to files after Organize completes
- Operates strictly on working directory outputs
- Consumes immutable execution ctx

---

## Responsibilities

- Apply GPS metadata (EXIF)
- Perform all file-level mutations
- Ensure no source file modification occurs

---

## Must

- Operate only on `ctx.input_files`
- Use working directory paths exclusively
- Be deterministic and repeatable
- Be safe to re-run (idempotent where possible)

---

## Must Not

- Access source (SD card) files
- Perform analysis or inference
- Change file selection
- Execute before Organize completes

---

## Inputs

- `ctx.input_files`
- `ctx.output_dir`
- `ctx.manual_gps` (optional)

---

## Outputs

- Files with updated metadata (e.g. GPS EXIF)
- Updated dataset ready for user consumption

---

## Invariants

- No mutation occurs before Organize
- Source files remain untouched
- All changes occur in working directory only

---

## Notes

- This stage includes:
  - GPS application
  - Future EXIF enhancements
- This stage isolates side effects from earlier steps

---
## v3.0

- Runs inside `/api/organize`, after all copies complete — not a separate step
- Inputs: copied file paths + the folder's saved location
- JPG copies → EXIF GPS + Ref tags (signed values stored correctly; fixes east/west inversion)
- RAW copies → XMP sidecar `<stem>.xmp` (created, or updated in place)
- No working directory: copies in the destination are the only mutation targets
- `/api/write-gps` on a source path → deferred (reported, nothing written)
- Failures reported per file; copies remain