# Platform Testing Checklist
**Scope:** Cross‑platform design validation (runtime vs packaging)  
**Project:** photo-organizer-packager

---

## 0. Meta Information

- **Tester:** Steve Debski  
- **Date:** 2026‑04‑29  
- **Test branch:** cross-platform-smoke-test  
- **Platforms tested:**
  - ☑ macOS (Apple Silicon, macOS 14)
  - ☑ Linux (Ubuntu 22.04)
- **Testing focus:**
  - ☑ Runtime behaviour
  - ☑ Packaging / installation

---

## 1. Runtime Environment Validation

### 1.1 Environment Setup

- ☑ Fresh clone succeeded
- ☑ Python 3.12 available on both platforms
- ☑ Virtualenv creation worked
- ⚠ One Linux dependency not explicitly documented

**Notes:**
Linux required libgl1 for UI rendering; not listed in docs.

---

### 1.2 Runtime Startup

- ☑ App starts on macOS without modification
- ☑ App starts on Linux after installing missing dependency
- ⚠ Error message on Linux was a traceback, not user‑friendly

**Notes:**

Startup error handling should abstract OS‑level dependency failures.

---

### 1.3 Core Runtime Workflows

Workflows tested:
- Import photos
- Auto‑organization by date
- UI navigation

Results:
- ☑ Behaviour consistent across platforms
- ⚠ File dialogs differ slightly but acceptable
- ☑ Performance acceptable

**Notes:**

Design is largely OS‑agnostic at runtime.

---

### 1.4 Filesystem & Data Handling

- ☑ Case‑sensitive paths handled correctly
- ☑ Unicode filenames safe
- ☑ No Windows‑specific path assumptions discovered
- ⚠ Permission error on Linux when writing outside HOME

**Design observations:**

Future design should restrict writes to user-owned directories.

---

### 1.5 UI & UX Runtime Differences

- ☑ Layout scales well on both platforms
- ⚠ Font rendering slightly small on macOS Retina
- ☑ Assets load correctly

**Design impact notes:**

Font sizing should use relative units exclusively.

---

## 2. Packaging & Installation Validation

### 2.1 Build Script Execution

- ☑ build.sh works on Linux
- ⚠ setup_mac.py requires undocumented manual step
- ☑ Clear failure output

**Notes:**

macOS packaging expects developer familiarity; not end‑user friendly.

---

### 2.2 Installation Expectations

macOS:
- ⚠ Unsigned app warning from Gatekeeper
- ⚠ No app bundle produced

Linux:
- ☑ Executable permissions handled
- ⚠ No desktop integration

**Design impact notes:**

Packaging is currently developer‑oriented, not consumer‑oriented.

---

### 2.3 Runtime vs Packaging Boundary

- ☑ Runtime logic OS‑agnostic
- ⚠ Packaging concerns leaked into docs and setup logic

**Boundary issues discovered:**

Need clearer abstraction between runtime and installer concerns.

---

## 3. Documentation Accuracy Check

- ☑ Core setup docs mostly accurate
- ⚠ Linux dependency missing
- ⚠ macOS signing expectations undocumented

**Corrections needed:**

Add per‑platform setup notes.

---

## 4. Design Feedback Summary

### ✅ Design Works Well

Core runtime behaviour is clean and cross‑platform.

### ⚠ Acceptable but Awkward

Packaging flow is functional but developer‑centric.

### ❌ Design Constraint / Architectural Issue

Error handling assumes developer context during setup.

---

## 5. Platform Support Decision

- ☑ macOS = first‑class runtime support
- ☑ Linux = first‑class runtime support
- ⚠ Packaging = best‑effort (for now)

**Rationale:**

Runtime design is solid; packaging needs strategic decisions.

---

## 6. Follow‑Up Actions

- ☑ Docs update required
- ☑ Backlog items created
- ☐ Runtime refactor deferred

---

## 7. Commit Strategy

- ☑ Docs‑only commit
- ☑ No runtime changes bundled

Expected commit:

Docs: record cross‑platform runtime and packaging observations

