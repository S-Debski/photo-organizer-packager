## Purpose

`Mapping` analyses photos in a known location and derives **structured metadata** about them.

Its primary goal is to extract, classify, and validate information (such as dates, locations, or quality signals) **without modifying the photo library itself**.

`Mapping` exists to make later steps (organisation, filtering, testing) predictable and repeatable.

> Design note: Mapping is intentionally informational rather than authoritative.

> See [[Why Mapping Is Informational]] for the design decision behind this behaviour.

``
---

## Behaviour

`Mapping` scans photos within a defined scope and performs **read‑only analysis**.

It inspects file contents and metadata in order to derive higher‑level information, which may be written as mapping output, logs, or reports.

`Mapping` does **not** move, rename, or modify photo files.

---

## Guarantees

`Mapping` guarantees the following:

- Source photo files are never modified
- No files are moved, deleted, or renamed
- Analysis is deterministic for a given input set
- Derived metadata is based solely on observable data
- Output is written only to explicitly defined mapping destinations
- Progress feedback is provided during execution
- Completion ends with a clear summary of what was mapped

---

## Guarantees During Failure

Even in failure scenarios, `Mapping` guarantees:

- Source files remain untouched
- Partial or invalid mapping output is not treated as valid
- Failures are reported clearly rather than silently ignored
- No destructive fallback behaviour is attempted

---

## Design Principles

- Read‑only analysis over invasive inspection
- Explicit classification over heuristic guesswork
- Reproducibility over cleverness
- Failure should be visible and actionable

---

## Constraints

- `Mapping` does not modify photo files under any circumstances
- Mapping output is separated from photo storage
- A single run operates over a clearly defined input scope
- Mapping behaviour is versioned and may evolve conservatively

---

## Failure Modes

### Startup Failures

Examples:

- Input directory is not accessible
- Required metadata cannot be read
- Mapping output location is not writable

**Behaviour**:

- No analysis is performed
- Operation aborts immediately
- A clear error message is emitted

---

### Runtime Failures

#### Individual File Analysis Failure

Examples:

- Corrupt file
- Unsupported format
- Missing or invalid metadata

**Behaviour**:

- Failure is logged
- The affected file is skipped
- Mapping continues where it is safe to do so

---

### Classification Failures

Examples:

- Conflicting metadata
- Insufficient data to classify confidently

**Behaviour**:

- File is marked as unclassified or ambiguous
- No guesswork or forced classification is applied
- Failure or uncertainty is explicitly recorded

---

### Unexpected Exceptions

**Behaviour**:

- Operation aborts
- No partial mapping output is treated as authoritative
- Clear error output is preferred over silent recovery

---

## Non‑Goals

`Mapping` deliberately does **not**:

- Modify, move, rename, or delete photo files
- Perform organisational actions
- Attempt to “fix” or rewrite metadata
- Optimise for speed at the expense of correctness
- Hide uncertainty or ambiguity in derived data

---

## Relationship to Other Commands

- `Mapping` **describes** photos
- `Organize` **copies** photos
- Mapping output may inform Organize, but never performs it

These responsibilities are intentionally kept separate.

---
## Related

  

- [[06 - Mapping]] — Behaviour, guarantees, and failure modes
## Version Notes

- **v2.7**
    
    - Read‑only mapping behaviour
    - Conservative classification rules
- **Future versions**
    
    - Expanded classification capabilities
    - Core read‑only and non‑destructive guarantees remain unchanged
  ## GPS Selection Behaviour

Mapping may allow the user to select or assign a location.

### Responsibilities
- Display detected GPS data
- Allow manual location selection via map UI

### Must
- Provide visual feedback only (markers, previews)
- Expose selected location to Pre‑Import layer

### Must Not
- Write GPS data to files
- Trigger EXIF updates
- Modify working directory or source files

### Output
- Manual selection passed as:
  - `ctx.manual_gps = { lat, lon }`
- 
      