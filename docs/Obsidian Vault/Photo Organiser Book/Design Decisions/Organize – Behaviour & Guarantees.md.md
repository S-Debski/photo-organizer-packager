## Purpose

`Organize` safely copies photos from a selected source (SD card or folder) into a single, known destination directory.

Its primary goal is to move photos out of temporary or removable media and into a stable library location **without risking data loss**.

`Organize` is intentionally conservative.  
If unsure, it does less — not more.

---
### Organize

- Requires completed analysis and explicit confirmation
- Only step allowed to prepare files for mutation
- Progress must be visible
- Must not auto-start or run silently

### Responsibilities
- Copy files to working directory
- Prepare dataset for execution stage
- Emit progress and completion state

### Must
- Operate only on ctx.input_files
- Respect mutex locking
- Produce deterministic output

### Must Not
- Modify source files
- Perform analysis or decision-making

### Output
- Files exist in working directory
- Ready for metadata mutation stage

## Behaviour

`Organize` scans a source location and copies supported photo files into a managed output directory.

The operation is **copy‑only** and never deletes or modifies source files.

All writes occur under a single destination directory defined by `ctx.output_dir`.

---

## Guarantees

`Organize` guarantees the following:

- Source files are never deleted
- Files are copied, not moved
- File integrity is preserved
- RAW + JPG pairs are kept together
- All output is written exclusively to `ctx.output_dir`
- Progress feedback is provided during execution
- Completion ends with a clear success message indicating how many photos were copied

---

## Guarantees During Failure

Even in failure scenarios, `Organize` guarantees:

- Source files remain untouched
- Partial or corrupt destination files are not kept
- No writes occur outside `ctx.output_dir`
- Failures are reported clearly rather than silently ignored

---

## Design Principles

- Correctness and data safety are prioritised over flexibility
- Predictable behaviour is preferred over configurability
- Explicit behaviour is favoured over implicit or “magical” behaviour
- Silent failure is avoided wherever possible

---

## Constraints

- `Organize` always writes to `ctx.output_dir`
- Only a single output directory is used per run
- In **v2.7**, the output directory is fixed and non‑configurable
- Output directory configuration is planned for **v2.8+**

---

## Failure Modes

### Startup Failures

Examples:

- `ctx.output_dir` does not exist
- `ctx.output_dir` is not writable
- Source directory or media is not accessible

**Behaviour**:

- No files are copied
- Operation aborts immediately
- A clear error message is emitted

---

### Runtime Failures

#### Individual File Copy Failure

Examples:

- Read error from source
- Write error to destination
- Permission issues

**Behaviour**:

- Failure is logged
- The affected file is skipped
- Operation continues where it is safe to do so

(Exact behaviour may be tightened in future versions.)

---

### Integrity Failures

Examples:

- Partial copy detected
- Checksum mismatch (if implemented)

**Behaviour**:

- Destination file is discarded
- Source file is left untouched
- Failure is reported

---

### Unexpected Exceptions

**Behaviour**:

- Operation aborts
- No cleanup is attempted that could risk data loss
- Clear error output is preferred over silent recovery

---

## Non‑Goals

`Organize` deliberately does **not**:

- Delete, move, or modify source files
- Reorganise or restructure existing libraries
- Perform destructive operations of any kind
- Attempt to be a general‑purpose photo management tool
- Infer destination paths from metadata
- Optimise for speed at the expense of correctness

---

## Version Notes

- **v2.7**
    
    - Fixed output directory
    - Conservative, safety‑first behaviour
- **v2.8+ (planned)**
    
    - Configurable output directory
    - Core guarantees remain unchanged
- **v3.0 (hybrid ingest)** — supersedes the v2.7 constraints above

---
## v3.0 Behaviour

Endpoint: `POST /api/organize` (**`backend/api_server.py`**)

Destination
    ↓
`<destination>/<layout(title, shoot date)>` — [[09 - Directory Template Resolution (Pre‑Import)]]
    ↓
Validate (nothing created on failure)
    ↓
Copy (kept or all)
    ↓
Apply location to copies
    ↓
Record in session manifest

### Guarantees (added)
- Destination chosen by the user; validated before any directory is created
- Never on the card or inside the source
- Copy via `<name>.part` then rename — an interrupted copy never leaves a partial file under the real name
- Size verified before rename
- Existing same name + same size → skipped (already imported)
- Existing same name + different size → reported as a clash, never overwritten
- RAW + JPG pairs and `.xmp` sidecars travel together (kept mode)
- Progress via `ctx.progress`, polled by `/api/progress`
- Source untouched; verified by tests

### Completion
- "Copied to <folder>"; counts copied / skipped / location written
- "You can now safely format the card" only when mode is `all` with no errors or clashes
- Kept mode: reminder that rejected/unculled photos remain on the card

### Constraints (v3.0)
- One destination folder per import
- Copy‑only; no moves, deletes or renames at source

- ## Verification

- [[Organize Testing Checklist (v2.7)]]
- [[Organize Testing – Manual Run Log]]
- [[v2.7 Mapping & Organize Freeze]]
