## Pipeline
1. CTX
2. Mapping
3. Pre‑Import
4. Organize
---

## CTX
- Constructed before execution
- Validated once
- Read‑only during execution
- Owns invariants and immutability
- ctx builders and validators only
---

## Mapping
- Read‑only analysis
- No decisions
- No file operations
- Produces informational outputs only
---

## Pre‑Import
- Captures explicit user intent
- Resolves destination and selection
- Validates and freezes inputs
- No file system mutation
---

## Organize
- Consumes fully resolved ctx
- Copies files only
- No interpretation or prompting
- Enforces safety guarantees
---

## Invariants
- ctx immutable once Organize starts
- Mapping may inform but never decide
- Selection ≠ mutation
- Organize remains minimal and boring
---
=================================================================================================================================================

## IMPLEMENTATION NOTES:

## CTX
- Constructed before execution
- Validated once
- Read-only during execution
- Owns invariants and immutability
- **`context.py`**
- ctx builders and validators only
- Accepts resolved output_dir and input_files
- Freezes ctx before Organize starts
---

## Mapping
- Read-only analysis
- No decisions
- No file operations
- Produces informational outputs only
- **`mapping/`**
- **`mapping/exif_dates.py`**
- **`mapping/quality_classification.py`**
- **`mapping/date_suggestions.py`**
- Outputs suggestions and signals only
---

## Pre-Import
- Captures explicit user intent
- Resolves destination and selection
- Validates and freezes inputs
- No file system mutation
- **`pre_import/`**
- **`pre_import/session_metadata.py`**
- **`pre_import/directory_templates.py`**
- **`pre_import/culling.py`**
- **`pre_import/validation.py`**
- Owns session metadata, culling, directory templates
---

### Pre-Import Implementation Notes
Inputs:
- `ctx.session.title`
- `ctx.session.shoot_date`
- user-selected directory template
- user culling decisions
- source file list

Responsibilities:
- Parse directory template
- Expand to relative subpath only
- Validate expansion (no absolute paths, no traversal)
- Preview final resolved destination
- Apply explicit culling to source file list
- Require user confirmation

Output:
- **`ctx.output_dir`** (fully resolved, absolute)
- **`ctx.input_files`** (final filtered list)

Invariant:
Pre-Import may derive but must not create directories or modify source files.
---

## Organize
- Consumes fully resolved ctx
- No interpretation or prompting
- Copies files only
- Enforces safety guarantees
- **`organize.py`**
- Directory creation and file copy execution only
- Must treat ctx as immutable
---
=================================================================================================================================================

## CULLING — IMPLEMENTATION NOTES

## Culling
- Explicit user‑driven exclusion of files
- Selection only, never mutation
- Default behaviour: no culling
- Source files remain untouched
- **`pre_import/culling.py`**
- Owns exclusion decisions only
- Produces filtered input set
---

## Culling Responsibilities
- Accept explicit user culling decisions
- Apply exclusions to source file list
- Preserve original source list unchanged
- Produce final filtered list for execution
- No automatic or inferred exclusions

---
## Mapping Relationship
- Mapping may provide informational signals
- Mapping does not mark files as excluded
- Mapping does not apply thresholds
- Mapping does not decide culling
- Mapping output is advisory only

---
## Pre‑Import Integration
- Culling occurs after session metadata capture
- Culling occurs before ctx freeze
- Exclusions must be previewable
- Exclusions must be reversible until execution starts

---
## Output
- **`ctx.input_files`** — final filtered list
- No changes to source media
- No filesystem interaction

---
## Organize Relationship
- Organize receives filtered input list only
- Organize does not know what was excluded
- Organize copies provided files unchanged
- Guarantees remain identical

---
## Failure Behaviour
- If culling fails or is aborted:
  - No files copied
  - No partial selection applied
  - Operation aborts safely
---