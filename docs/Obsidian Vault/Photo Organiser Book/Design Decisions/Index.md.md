## Design Decisions
Authoritative design and behaviour decisions for this project.
Documentation format follows [[Documentation Style (Canonical)]].

---
## Pipeline
1. CTX
2. Mapping
3. Pre‑Import
4. Organize
5. Post‑Organize (Metadata Mutation)
---
## Core Concepts
- [[06 - Mapping]]
- [[Organize – Behaviour & Guarantees]]
- [[07 - Pre-Import Workflow]]
- [[01 - CTX]]
- [[05 - Why Mapping Is Informational]]
  
---
## Post‑Organize (Metadata Mutation)

- Applies metadata updates (e.g. GPS, EXIF)
- Operates strictly on working directory files
- Consumes immutable ctx
- Runs only after Organize completes

### Responsibilities
- Apply user‑defined metadata (manual GPS, etc.)
- Ensure all mutations occur on copied files only
- Maintain deterministic, repeatable behaviour

### Must
- Operate on `ctx.input_files` only
- Use working directory paths exclusively
- Be idempotent (safe to re-run)

### Must Not
- Access source (SD card) files
- Perform analysis or inference
- Modify selection or structure

### Invariants
- No mutation occurs before Organize
- Source files remain untouched
- All mutations are applied post-copy only

## Supporting Decisions
- [[04 - GPS Quality Classification]]
---
## Releases
See [[Releases/Index]] for frozen behaviour per version.

#How stuff works
workers/exif_scanner.py       → background collection
photo_core/exif/reader.py    → ExifTool interface ✅
photo_core/exif/*            → structured metadata access
photo_core/mapping/*         → analysis + transformation
backend/routes/*             → API exposure
ui                           → display

Your `reader.py` :

- calls ExifTool ✅
- returns a dict ✅
- maybe caches ✅

EXIF extraction functions
reader.py → raw EXIF ✅
accessor.py → clean interface ✅
mapping/* → business logic ✅