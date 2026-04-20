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
