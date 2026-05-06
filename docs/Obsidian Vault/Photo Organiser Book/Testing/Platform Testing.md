# Platform Testing Checklist
**Scope:** Cross‑platform design validation (runtime vs packaging)  
**Purpose:** Identify *design constraints and platform assumptions early*  
**Non‑Goal:** Release hardening or cosmetic perfection

---

## 0. Meta Information

- **Tester:**  
- **Date:**  
- **Test branch:**  
- **Platforms tested:**
  - ☐ macOS (Intel / Apple Silicon)
  - ☐ Linux (distro & version: __________)
- **Testing focus:**
  - ☐ Runtime behaviour
  - ☐ Packaging / installation
  - ☐ Both

---

## 1. Runtime Environment Validation (Design-Critical)

This section answers:  
> *“Does the application’s design make sense on this platform when running?”*

---

### 1.1 Environment Setup

- ☐ Fresh clone (no copied config)
- ☐ Python version as expected
- ☐ Virtualenv creation documented & works
- ☐ Dependency install succeeds without platform hacks

**Notes:**

---

### 1.2 Runtime Startup

- ☐ Application starts without modification
- ☐ No hard‑coded OS paths
- ☐ Clear error messages on failure
- ☐ Config files discovered correctly

**Notes:**

---

### 1.3 Core Runtime Workflows

List **only 1–3 key flows**.

Example:
- Import photos
- Organize / rename files
- UI load & interaction

For each workflow:
- ☐ Behaviour matches Windows intent
- ☐ No platform‑specific surprises
- ☐ Performance acceptable
- ☐ Errors handled gracefully

**Notes:**

---

### 1.4 Filesystem & Data Handling (High Impact)

Explicitly validate:

- ☐ Case‑sensitive paths handled correctly (Linux/macOS)
- ☐ Unicode filenames safe
- ☐ Permissions errors handled clearly
- ☐ No reliance on Windows path semantics
- ☐ Hidden/system files handled intentionally

**Design observations:**


---

### 1.5 UI & UX Runtime Differences

- ☐ Layout scales appropriately
- ☐ Fonts readable across DPIs
- ☐ Assets load correctly
- ☐ No clipped or overlapping elements

macOS:
- ☐ Retina scaling acceptable
- ☐ Native file dialogs sensible

Linux:
- ☐ Theme variations acceptable
- ☐ Contrast and readability preserved

**Design impact notes:**


---

## 2. Packaging & Installation Validation (Design Direction)

This section answers:  
> *“Is our packaging strategy realistic and sustainable?”*

---

### 2.1 Build Script Execution

- ☐ Build script runs as documented
- ☐ Failure modes are clear
- ☐ No undocumented manual steps
- ☐ Build assumptions are explicit

Scripts tested:
- ☐ build.sh
- ☐ setup_mac.py
- ☐ Other: ___________________

**Notes:**


---

### 2.2 Installation Expectations

- ☐ Installation flow matches platform norms
- ☐ Permissions requirements documented
- ☐ User does not need dev knowledge to install

macOS:
- ☐ App bundle vs script expectations clear
- ☐ Gatekeeper / unsigned behaviour understood

Linux:
- ☐ Executable permissions handled
- ☐ Distro assumptions explicit
- ☐ AppImage / tarball / system install expectations clear

**Design impact notes:**


---

### 2.3 Runtime vs Packaging Boundary

Answer explicitly:

- ☐ Runtime design is OS‑agnostic where possible
- ☐ Platform differences isolated to packaging
- ☐ No runtime logic depends on installer choices

**Boundary issues discovered:**


---

## 3. Documentation Accuracy Check

This section answers:  
> *“Do the docs describe what actually happens?”*

---

- ☐ Setup instructions copy‑paste safe
- ☐ Platform‑specific notes present where required
- ☐ Windows assumptions avoided in general docs
- ☐ Known limitations documented

Docs reviewed:
- ☐ Architecture
- ☐ Release checklist
- ☐ Setup guides

**Corrections needed:**


---

## 4. Design Feedback Summary (Most Important Section)

Categorise findings — **do not fix yet**.

---

### ✅ Design Works Well

(Keep current approach)



---

### ⚠ Acceptable but Awkward

(Consider future improvement)



---

### ❌ Design Constraint / Architectural Issue

(Must influence future decisions)



---

## 5. Platform Support Decision

Based on this testing, decide:

- ☐ macOS = first‑class support
- ☐ Linux = first‑class support
- ☐ Best‑effort support only
- ☐ Experimental / community supported

**Rationale:**


---

## 6. Follow‑Up Actions (Deferred)

- ☐ Docs update required
- ☐ Design change required
- ☐ Backlog item created
- ☐ No action required

**Links / references:**


---

## 7. Commit Strategy

- ☐ Findings committed as docs‑only
- ☐ No runtime refactors bundled
- ☐ Commit message uses `Docs:` prefix

Expected commit:

Docs: record cross-platform runtime and packaging observations

---

## End of Checklist