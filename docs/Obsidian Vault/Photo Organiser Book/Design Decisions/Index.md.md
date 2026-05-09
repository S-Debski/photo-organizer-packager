## Design Decisions
Authoritative design and behaviour decisions for this project.
Documentation format follows [[Documentation Style (Canonical)]].

---
## Pipeline

1. CTX
2. Mapping
3. Pre-Import
4. Organize
---
## Core Concepts
- [[06 - Mapping]]
- [[Organize – Behaviour & Guarantees]]
- [[07 - Pre-Import Workflow]]
- [[01 - CTX]]
- [[05 - Why Mapping Is Informational]]
  
---
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