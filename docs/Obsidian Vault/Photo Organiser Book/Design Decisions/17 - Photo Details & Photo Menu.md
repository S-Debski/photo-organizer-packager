# Photo Details & Photo Menu
#design #v3.0

Backlink: [[13 - Culling Sessions]] · [[Stability Contract]]

## Purpose

Support culling decisions with shooting details and quick file access. Read‑only for the source, except opening a photo in another app on request.

---
## Photo Details

Shown under the photo in the full‑screen viewer and Review one by one.

```text
1 Jul 2017, 05:41 · Sony ILCE-7R · FE 24-70mm F4 ZA OSS
24 mm · f/8 · 1/125 s · ISO 100 · -0.3 EV · 2000 × 1335
52.10750, 1.45800  camera GPS · near Butley Village Hall · JPG 396 KB
```

- Endpoint: `GET /api/photo-info?path=<jpg>&path=<raw>`
- Source: cached ExifTool records (scanner's batched read); no extra file access in the common case
- Each field from the first file of the pair that has it; JPG first, then RAW
- Make/Model read from IFD0, then Exif IFD (some editors move them) — also used by camera stats
- Camera name de‑duplicates make (`NIKON CORPORATION` + `NIKON D800` → `NIKON D800`; `FUJIFILM` + `X-T5` → `Fujifilm X-T5`)
- Focal length shows 35 mm equivalent when different
- Files listed with sizes (`JPG 12.1 MB + RAF 33.4 MB`)
- Cached per photo in the page; fast arrow‑key moves never show a stale photo's details
- `I` hides / shows; remembered per browser

### Location Line
Top‑down:
1. Camera GPS (EXIF) → "camera GPS"
2. Folder's assigned location → "assigned to folder"
3. Neither → "No location"

- Nearest saved place within 1.5 km → "near <name>" ([[14 - Saved Places]])
- No online reverse geocoding (coordinates never leave the machine)

---
## Photo Menu (right‑click)

On grid tiles, the viewer image and the review image.

- Keep / Reject / Clear decision (same as K / X)
- Open JPG · Open RAW — default app
- Open JPG with… · Open RAW with… — Windows "How do you want to open this file?" chooser; hidden on macOS
- Show in Explorer / Show in Finder — file selected
- Copy file path (both files of a pair)

### Rules
- Endpoint: `POST /api/file-action {path, action: open | openwith | reveal}`
- Photo files only (`IMAGE_EXTS_ALL`, `.xmp`, `.png`, `.tif`) — nothing executable can be launched
- Opening a photo hands it to another app; this app writes nothing
- Menu stays inside the window; Esc / click outside / scroll / resize closes it
- Esc with the menu open closes only the menu, not the viewer
