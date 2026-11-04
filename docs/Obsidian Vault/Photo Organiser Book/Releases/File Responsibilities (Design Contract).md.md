# File Responsibilities (Design Contract)
#architecture #stability

This section defines what each **top‑level project file or module is responsible for by design**.

If a file begins to violate its declared role, that is a **design regression**, even if behaviour still appears correct.

Backlink:  
[[Stability Contract]]

---

## Application Entry & Lifecycle

### `main.py`
**Role**
- Single application entry point
- Bootstraps runtime environment
- Initializes core subsystems
- Starts UI / server layer

**Must**
- Perform minimal logic
- Defer behaviour to controllers
- Be safe to reason about linearly

**Must Not**
- Contain business logic
- Perform analysis or file operations

---

### `app.py`
**Role**
- UI application wiring
- Routes user actions to controllers
- Owns high‑level app structure

**Must**
- Reflect state, not own it
- Bind views to capabilities

**Must Not**
- Access filesystem directly
- Perform long‑running work

---

### `api_server.py`
**Role**
- Backend service / IPC boundary
- Exposes controlled operations to UI or CLI

**Must**
- Act as a thin orchestration layer
- Validate inputs
- Delegate to worker modules

**Must Not**
- Hold UI state
- Include presentation logic

---

## State, Concurrency & Safety

### `thread_manager.py`
**Role**
- Centralized control of background threads
- Job scheduling, lifecycle coordination

**Must**
- Respect job lifecycle contract
- Track running work explicitly
- Terminate cleanly on shutdown

**Must Not**
- Contain domain logic
- Modify files directly

---

### `mutex.py`
**Role**
- Cross‑process / cross‑thread locking
- Prevents concurrent destructive operations

**Must**
- Guard Organize and other critical sections
- Fail safely and loudly

**Must Not**
- Implement business rules
- Be optional for destructive steps

---

## Command Line & Automation

### `cli.py`
**Role**
- Command‑line interface
- Scriptable access to core operations

**Must**
- Share logic with UI (no duplication)
- Call the same controllers as the UI

**Must Not**
- Bypass safety or confirmation checks
- Maintain its own logic paths

---

## Configuration & Environment

### `config.py`
**Role**
- Central configuration source
- Paths, flags, environment‑derived settings

**Must**
- Be deterministic
- Be loadable without side effects

**Must Not**
- Perform I/O beyond config loading
- Mutate global state implicitly

---

### `version.py` / `version.txt`
**Role**
- Single source of truth for app version

**Must**
- Be machine‑readable
- Match tagged releases

**Must Not**
- Contain logic

---

## File Operations & Organize Safety

> **Reminder:**  
> *Only Organize‑related modules may modify files.*

### Organize Flow (logical group)
- Organize controllers
- Destination resolution
- Rename / move logic

**Must**
- Be explicitly triggered
- Emit progress and failure states
- Respect mutex locking

**Must Not**
- Run implicitly
- Be triggered from navigation alone

### Organize (extended)
- Consumes fully resolved ctx
- Copies files only
- Applies metadata mutations (e.g. GPS)
- No interpretation or prompting

Must:
- Apply all mutations to working directory only
- Use ctx as immutable input
- Emit progress and failures

Must Not:
- Read from source paths
- Perform analysis or inference

---

## Build & Packaging

### `app.spec`, `photo-organizer-*.spec`
**Role**
- Packaging definitions (PyInstaller)

**Must**
- Be declarative only
- Match runtime assumptions

**Must Not**
- Contain application logic

---

### `build.sh`, `build.ps1`, `build.bat`, `build_win.cmd`
**Role**
- Build automation wrappers

**Must**
- Be repeatable
- Fail clearly

**Must Not**
- Modify runtime behaviour
- Patch application code

---

## Documentation & Metadata

### `README.txt`
**Role**
- User‑facing overview
- Installation and usage guidance

---

### `CHANGELOG.md`
**Role**
- Human‑readable release history

**Must**
- Note behaviour changes
- Reference contract changes explicitly

---

### `CLAUDE.md`
**Role**
- AI / tooling notes (non-runtime)

**Must Not**
- Affect shipped behaviour

---

## v3.0 Modules

### `app.py`
- Entry point (there is no `main.py`): logging, single‑instance check, starts server threads, runs tray on the main thread

### `tray/tray_icon.py`
- Tray / menu‑bar icon: Open, Quit
- Must not contain application logic

### **`photo_core/organize/destination.py`**
- Resolve and validate the import destination (layout, title, date)
- Shared by preview and import; pure path logic, creates nothing

### **`photo_core/pre_import/session_state.py`**
- Culling session manifests; same‑photos resume rule
- One RAW/JPG extension list via `utils/fs_utils.py`

### **`photo_core/export/pixel.py`**
- Send to phone via adb; never overwrites on the phone
- Must not read from the source card

### `photo_core/exif/reader.py`
- ExifTool resolution (env → bundled → PATH → Homebrew), batched `prefetch_exif`, per‑file `read_exif`
- Caches keyed on path + size + mtime

### `utils/thumb_cache.py`
- Disk‑cached downscaled previews (grid 320 / strip 160 / preview 1600); RAW via embedded preview

### `backend/services/sdcard.py`
- Source detection: card / external / disk / network

### `backend/api_server.py` (v3.0 additions)
- `/api/whoami` — identifies the app for the start‑up port check
- `/api/photo-info` — read‑only EXIF summary for the viewer
- `/api/file-action` — open / open with / reveal; photo files only
- `/api/pre-import/preview`, `/api/locations`, `/api/places`, `/api/pixel/*`, `/api/exif-records`, `/api/thumb`

### `backend/routes/write_gps.py`
- `write_gps_tags` (JPG EXIF), `write_gps_sidecar` (RAW XMP); defers any source path

### Build files (current)
- `photo-organizer.spec`, `build.bat`, `build_mac.sh`, `.github/workflows/build.yml`
- Older `app.spec` / `photo-organizer-*.spec` / `build_exe.bat` references above are superseded

### Tests
- `tests/test_pipeline.py` — end‑to‑end pipeline checks on a temporary card
- `tests/fake_adb.py` — stand‑in adb

---

## Lock & Runtime Artifacts

### `my_wizard_app.lock`
**Role**
- Runtime safety artifact
- Prevents concurrent execution

**Must**
- Be ephemeral
- Never be relied on as state

---

## Explicit Non‑Responsibilities

- Third‑party libraries (`.venv/`, `site-packages/`)
- Build artifacts (`.dmg`, `.spec` outputs)
- IDE metadata (`.idea/`)

These are **outside the architecture contract**.

---

## Maintenance Rules

When adding a new file:
1. Declare its role here
2. Link back to `[[Stability Contract]]`
3. Assign ownership before adding behaviour

If a file’s purpose becomes unclear, it is a design smell.

---
## Architecture Hygiene

Project architecture is enforced through lightweight tooling.

### Role Annotation

- A `# Role:` header is required for all stabilised source files.
- Roles declare *intent*, not implementation.
- Role headers are managed by `tools/role_annotator.py`.

**Before committing changes that add or move files:**
```

# Dev check
python tools/role_annotator.py --check

# Fix issues
python tools/role_annotator.py --fix --apply

#Audit
python tools/role_annotator.py --report

# Recap
python tools/role_annotator.py --report   ✅ audit
python tools/role_annotator.py --check    ✅ enforce
python tools/role_annotator.py --fix --apply  ✅ repair