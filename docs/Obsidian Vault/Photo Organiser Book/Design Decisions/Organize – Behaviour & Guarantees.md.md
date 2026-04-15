## Purpose

`Organize` safely copies photos from a selected source (SD card or folder) into a single, known destination directory.

Its primary goal is to move photos out of temporary or removable media and into a stable library location **without risking data loss**.

`Organize` is intentionally conservative.  
If unsure, it does less — not more.

---

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

- ## Verification

- [[Organize Testing Checklist (v2.7)]]
- [[Organize Testing – Manual Run Log]]
- [[v2.7 Mapping & Organize Freeze]]
