# Documentation Style (Canonical)

Authoritative formatting and density rules for this project.
All design and behaviour docs follow this style.
#canonical
  
## Intent

Documentation is written as compact design notes.
Density and precision are prioritised over prose.

---
## View Mode

- Source mode is canonical
- Live Preview is not used for authoring
- Reading View is secondary
---

## Structure

- Headings define responsibility boundaries
- Horizontal rules separate phases or concepts
- Bullet lists contain atomic guarantees or rules
- No narrative padding
---

## Filename Emphasis

- Filenames and module paths are written as inline code
- Boundary‑owned files are bolded for emphasis
- Format: **`path/to/file.py`**
- Used only in design and boundary documentation
---

## Pipelines

- Use arrow models to express flow
- Pipelines define responsibility and order

Example:

Source
    ↓
Mapping
    ↓
Pre‑Import
    ↓
Organize

---

## Language

- Declarative
- No speculation
- No future promises without versioning
- Selection ≠ mutation must be explicit

---

## Formatting Rules

- No blank lines between bullets
- Minimal blank lines elsewhere
- Code blocks only for literals or structures
- Whitespace is intentional

---

## Non‑Goals

- Not optimised for blogs or tutorials
- Not optimised for rendered aesthetics
- Not prose‑first documentation