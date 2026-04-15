## Self notes on this: `ctx.output_dir` — detailed explanation (README / future‑me level)

### What `ctx.output_dir` Is

`ctx.output_dir` is the **single, authoritative destination directory** for all files written by the `Organize` operation.

It represents the **root of the managed photo library** for the duration of a run.  
No files are written outside of this directory.

In other words:

> If a file is created, copied, or modified by `Organize`, it **must** live somewhere under `ctx.output_dir`.

---

### Why It Exists

`ctx.output_dir` exists to enforce **predictability and safety**:

- Prevents accidental writes to arbitrary locations
- Makes dry‑runs, testing, and logging simpler
- Allows the rest of the codebase to assume a _single write boundary_
- Reduces the risk of destructive bugs caused by path mis‑calculation

This is a deliberate design choice rather than a limitation.

---

### Behavioural Contract

The following are **hard guarantees** associated with `ctx.output_dir`:

- All copied photos are placed under `ctx.output_dir`
- No files are written outside this directory tree
- Path resolution is always relative to `ctx.output_dir`
- `Organize` does not infer or auto‑select alternative destinations
- Failure to access or write to `ctx.output_dir` is treated as a fatal error

---

### Version-Specific Notes

- **v2.7**
    
    - `ctx.output_dir` is fixed and non-configurable
    - Its value is determined before `Organize` starts
    - Users cannot override it via flags or configuration
- **v2.8+ (planned)**
    
    - `ctx.output_dir` becomes user-configurable
    - The guarantee that _all writes occur under `ctx.output_dir`_ remains unchanged

---

### What `ctx.output_dir` Is _Not_

To avoid future ambiguity:

- It is **not** inferred from the source directory
- It is **not** automatically created from metadata (dates, camera, etc.)
- It is **not** allowed to change during execution
- It is **not** optional