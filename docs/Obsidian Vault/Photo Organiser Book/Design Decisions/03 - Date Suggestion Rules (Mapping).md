## Purpose

Provide candidate shoot dates to inform Pre‑Import session metadata. Suggestions are informational only and never authoritative.

  

---

## Scope

- Read‑only analysis
- No file modification
- No metadata rewriting
- No implicit decisions

  

---

## Candidate Date Sources

Mapping may extract candidate dates from:

- EXIF DateTimeOriginal
- EXIF DateTimeDigitized
- File system timestamps
- Capture sequence ordering

  

Each source is treated independently.

  

---

## Confidence Characteristics

- EXIF may be missing

- EXIF may be incorrect due to camera misconfiguration

- File system timestamps may reflect copy time, not capture time

  

No source is assumed correct by default.

  

---

## Suggestion Model

- Mapping may present one or more candidate dates

- Each candidate includes its source

- No automatic selection is performed

  

Mapping does not reconcile or extrapolate dates.

  

---

## Relationship to Pre‑Import

- Suggested dates may be displayed during Pre‑Import

- User provides the final shoot date explicitly

- User input supersedes all suggested values

  

---

## Relationship to Organize

- Organize does not receive suggested dates

- Organize does not interpret date information

- Suggested dates do not affect file operations

  

---

## Failure Behaviour

If date extraction fails:

- No suggestions are produced

- Import remains possible

- No special handling required
