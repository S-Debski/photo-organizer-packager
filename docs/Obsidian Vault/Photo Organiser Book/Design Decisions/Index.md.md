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
## Pipeline (v3.0)
Source (card / external drive / folder)
    ↓
Browse & cull — source read in place
    ↓
Cameras & lenses · Locations (informational / intent only)
    ↓
Import — copy kept or all, apply location to copies
    ↓
Send to phone (optional)
---
## Core Concepts
- [[06 - Mapping]]
- [[Organize – Behaviour & Guarantees]]
- [[07 - Pre‑Import Workflow]]
- [[01 - CTX]]
- [[05 - Why Mapping Is Informational]]
---
## v3.0 Decisions
- [[12 - Sources (Cards, Drives, Folders)]]
- [[13 - Culling Sessions]]
- [[08 - Import Session Metadata]] — title, date, location
- [[09 - Directory Template Resolution (Pre‑Import)]] — layouts, preview, validation
- [[Infer title from date and let user edit details]] — two title rules
- [[14 - Saved Places]]
- [[15 - Send to Phone]]
- [[16 - Packaging & Runtime]]
- [[11 - Post-Organize (Metadata Mutation)]]
- [[02 - Known `ctx` Fields]]
  
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