  - `ctx.output_dir` — Destination root for all writes

- `ctx.source` — Source media or directory (read‑only)

- `ctx.run_id` — Unique identifier for this execution

- `ctx.logger` — Structured logging interface

  

(Fields may be added over time; removal is breaking.)

---
## v3.0 — AppContext (**`photo_core/ctx/context.py`**)

### Attributes
- `ctx.shutdown_event` — stops workers; set by tray Quit
- `ctx.exif_cache` — scanner folder signatures (path, size, mtime)
- `ctx.thumb_cache` — legacy; thumbnails now disk‑cached
- `ctx.progress` — `{stage, total, done, active, message}`; stages `import` | `pixel` | `idle`
- `ctx.cache_dir` — `~/AppData/Local/PhotoWizardCache` (thumbnails in `thumbs/`)
- `ctx.output_dir` — `~/Pictures/PhotoWizard` (default root, not the import destination)
- `ctx.sessions_root` — `~/Pictures/PhotoWizard/sessions`
- `ctx.working_dir` — base folder only; no per‑click working folders

### `ctx.state`
- `current_sd_root` — card / drive / folder chosen on the Card step
- `current_active_folder` — folder being browsed (source, read‑only)
- `exif_records` — `[{path, datetime, camera_model, lens, gps: [lat, lon] | None}]`; cleared on folder change
- `session`, `session_dir` — active culling session manifest
- `copy_complete` — gate for `/api/thumbs`
- `working_files` — JPEGs in the active folder
- `pixel_result` — last Send to phone summary

### On disk (`sessions_root`)
- `<name>_<timestamp>/session.json` — culling manifest
- `locations.json` — saved per‑folder locations
- `places.json` — saved places
