
# Stability Contract (v2.8.x)
#stability #contract #architecture

> Canonical behavioural guarantees of the system as of **v2.8.1-stable**.  
> Any change that violates this contract must be **intentional, explicit, and versioned**.

Backlink reference (for feature notes, PRs, and refactors):  
[[Stability Contract]]

---

## Core Principles

- No implicit destructive actions
- State is the single source of truth
- Navigation never mutates core state
- Async work is observable and cancellable
- Initialization is safe to repeat

---

## Global Invariants

- **Organize is the only destructive operation**
- No background jobs start without explicit user intent
- UI reflects state; UI actions alone do not change state
- Heavy work is gated by explicit prerequisites

---

## Workflow Model

Detect → Select Folder → Analyze → Review → Organize

Capabilities unlock based on **state**, not navigation order.

---

## Step Contracts

### SD Detection
- Read-only
- Does not trigger downstream steps

---

### Folder Selection
- Explicit, user-confirmed
- Changing folder invalidates prior analysis

---

### Analyze
- Requires folder selection
- Read-only (no file mutation)
- Results are reusable by all review views
- May emit partial / progressive results

---

### Stats / Map / Thumbnails
- Require analysis data
- Passive views derived from analysis
- May skip initialization if data is absent
- Must not re-run analysis implicitly

---

### Organize
- Requires completed analysis and explicit confirmation
- Only step allowed to modify files
- Progress must be visible
- Must not auto-start or run silently

---

## Async Job Contract

idle → queued → running → finishing → complete | failed | cancelled

Rules:
- Progress is monotonic
- Terminal states stop polling
- Errors are explicit and surfaced

---

## Initialization Rules

These must be **idempotent** (safe to call multiple times):

- `initMap`
- `loadThumbnails`
- `bindOrganizeEvents`
- `pollJobStatus`

They must:
- Check prerequisites
- Avoid duplicate listeners, DOM nodes, or timers

---

## Navigation & UX Rules

- Visible ≠ enabled
- Navigating does not reset state unless inputs change
- Returning to a tab does not re-run heavy work unnecessarily

---

## Error Handling

- Errors are contextual and non-destructive
- Fatal errors halt further actions without data loss

---

## Change Discipline

Changes that affect:
- Step prerequisites
- Implicit behaviour
- Organize semantics
- Job lifecycle

Must include:
- Contract update
- Version note

---

## Explicit Non‑Goals

This contract does not define:
- Visual design
- Performance targets
- Refactor strategy
- Future workflow ideas

---

# Release Checklist (v2.8+)

Use this before tagging any stable release.

### Safety
- [ ] No new implicit file mutations
- [ ] Organize still requires explicit confirmation
- [ ] Folder change still invalidates analysis

### State & Flow
- [ ] All gated steps still unlock based on state only
- [ ] Navigation does not trigger side effects
- [ ] State survives tab switching

### Async Jobs
- [ ] Jobs follow the defined lifecycle
- [ ] Polling stops on terminal states
- [ ] Errors surface clearly and halt safely

### Initialization
- [ ] `init*` functions are idempotent
- [ ] No duplicate listeners, timers, or markers introduced

### UX
- [ ] Empty states handled explicitly
- [ ] Progress visible for long operations
- [ ] No silent failures

---

# Contract → Module Mapping

This section anchors the contract to code ownership.

### State Management
- Central app state / store
- Capability flags (`canAnalyze`, `canOrganize`, etc.)
- Job status model

### SD Detection
- SD detection module
- Hardware / filesystem probe layer

### Folder Selection
- Folder picker UI
- Analysis invalidation logic

### Analyze
- Analyzer pipeline
- Metadata extraction
- Results cache / model

### Stats
- Camera / lens stats module
- Aggregate computation layer

### Map
- Leaflet integration
- GPS filtering & marker building
- Map initialization guard logic (`initMap`)

### Thumbnails
- Thumbnail loader
- Lazy loading / viewport logic
- `loadThumbnails` entry point

### Organize
- Organize UI & confirmation layer
- Job creation & execution
- `bindOrganizeEvents`
- Progress reporting

### Async Jobs
- Job lifecycle model
- Polling / cancellation (`pollJobStatus`)

### Navigation
- Tab controller
- Gating / enablement logic

---

## Usage Notes (Obsidian)

- Link this doc from:
  - Feature notes
  - Refactor plans
  - PR review notes
- Use as a **diff lens**:
  _“Which bullets in this contract does this change touch?”_