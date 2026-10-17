# Saved Places
#design #v3.0

Backlink: [[06 - Mapping]] · [[08 - Import Session Metadata]]

## Purpose

Reusable named coordinates for repeat venues and walks. Selection only — choosing a place assigns nothing until the user does.

---
## Behaviour

- "Saved places…" list on the Locations step
- Pick → fills latitude/longitude, moves the map and marker
- Then "Assign to this folder" or "Use for all folders" as usual
- "Save this point as a place" → name prompt; same name (any case) replaces after confirmation
- "Delete saved place" → removes the place only; assigned locations unchanged

---
## Storage

- `GET /api/places`, `POST /api/places {name, lat, lon}` / `{name, delete: true}`
- `sessions/places.json`; shared by every card; sorted by name
- Coordinates validated: −90…90, −180…180
- Seed (first use): Butley Village Hall — 52.1072, 1.4575 (example venue; formerly hard‑coded in `analyze_card.py`)
