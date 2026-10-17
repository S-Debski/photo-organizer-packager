
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
- Metadata mutation is strictly post-organize
- Mapping and Pre‑Import remain mutation-free


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
- File or module responsibilities

Must include:
- Contract update
- Version note

---

## v3.0 Amendments (hybrid ingest)

Version note: v3.0.0 — contract changes below are intentional and versioned.

### Workflow Model (v3.0)

Detect / choose source → Folders → Browse & cull → (Cameras & lenses, Locations) → Import → (Send to phone)

### Added Invariants
- The source (card, drive, folder) is never written — not by culling, Locations, or import
- Import never overwrites: same name + different content is reported, not replaced
- No partial files under real names (copy via `.part` + rename)
- Destination validated before any directory is created; never on the card or inside the source
- Culling decisions and locations resume only for the same photos (name + size), never by path alone
- Location is applied to copies only (JPG EXIF, RAW `.xmp` sidecar)
- Send to phone copies only; never overwrites on the phone; uploads nothing
- "Safely format the card" shown only after a complete `all` import with no errors

### Step Contracts (v3.0)
- Card detection — read‑only; also runs on app open and window focus (Card step)
- Folder change — clears the previous folder's EXIF records; any folder picker goes through `activateFolder()`
- Browse — returning to the step reuses the loaded grid
- Locations — selection persisted to disk, not to files
- Import — explicit choice (kept / everything); refused when kept is empty

### Release Checklist Additions
- [ ] `python -m unittest discover -s tests` passes (includes source‑unchanged test)
- [ ] Card swap in the same slot starts with no decisions or locations
- [ ] Import preview path equals the actual import folder
- [ ] Windows and macOS builds green in Actions
- [ ] Standalone exe reads EXIF with the bundled ExifTool (no system ExifTool)

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
### Architectural Intent Declaration

**Responsibility**

- Declares the architectural role of each stabilised source file
- Ensures module intent is explicit, reviewable, and not inferred from structure alone
- Prevents silent responsibility drift during refactors

**Contract Coverage**

- Applies to all stabilised files (see Stability Contract)
- Required when:
  - introducing new files
  - moving or renaming files
  - changing module responsibilities

**Enforcement**

- Role declarations are enforced via the role annotation tool  
  (`tools/role_annotator.py`)
- Tooling is advisory in development and enforceable in CI

**Ownership Model**

- Each file owns its declared role
- Higher‑level architecture reviews reason *through* role declarations
- Missing or outdated role declarations are considered architecture regressions


### State Management
- Central app state / store
- Capability flags (`canAnalyze`, `canOrganize`, etc.)
- Job status model
- State transitions must align with declared module roles

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
- Rules:
	  - Organize is the final preparation step before mutation
- No metadata mutation occurs during Organize
- All metadata mutation occurs in Post‑Organize stage

### Async Jobs
- Job lifecycle model
- Polling / cancellation (`pollJobStatus`)

### Navigation
- Navigation modules must not assume responsibilities outside their declared role
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
-  Structural changes should be accompanied by a role annotation check.

## Architectural Intent Declaration

All stabilised source files must explicitly declare their architectural role.

- Each eligible file begins with a one‑line `Role:` header.
- Roles describe **intent**, not implementation.
- Role declarations are required for:
  - new files
  - moved or renamed files
  - refactors that change responsibilities

This requirement is enforced via lightweight tooling.

Before committing structural changes:
```bash
python tools/role_annotator.py --check

