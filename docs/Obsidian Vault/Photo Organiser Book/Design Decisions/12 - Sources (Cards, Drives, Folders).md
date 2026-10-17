# Sources (Cards, Drives, Folders)
#design #v3.0

Backlink: [[Stability Contract]]

## Purpose

Where photos are read from. Sources are read‑only; nothing is written to them.

---
## Source Kinds

| Kind | Meaning | Default list |
|---|---|---|
| `card` | Camera card: FAT/exFAT, card‑sized (0.5 GB – 2 TB) | yes |
| `external` | USB / FireWire / SD‑bus drive that isn't a card | yes |
| `disk` | Internal disk of this computer | with "Also show…" |
| `network` | Mapped network share (NAS) | with "Also show…" |
| folder | Any folder via "Choose a folder…" | always available |

- Owner: **`backend/services/sdcard.py`** `list_all_sources()`
- `GET /api/sd-cards` → card + external; `?all=true` → everything
- Grouped in the list by kind; sizes shown
- Empty reader slots and optical drives excluded

---
## Detection Rules

### Windows
- `GetDriveType` = REMOTE → `network`
- Card rules (`filter_windows_sd_cards`) → `card`
- Removable, or disk bus USB / 1394 / SD / MMC → `external`
    - Bus from `IOCTL_STORAGE_QUERY_PROPERTY` (`STORAGE_DEVICE_DESCRIPTOR.BusType`); no admin rights
    - Needed because Windows reports USB hard disks as `DRIVE_FIXED`
- Otherwise → `disk` (e.g. NVMe, SATA)
- Sizes via `GetDiskFreeSpaceEx` (network shares read as 0 otherwise)

### macOS
- `/Volumes/*`, excluding the boot volume
- Network filesystems (smbfs, afpfs, nfs, webdav) → `network`
- msdos/exfat within card size → `card`
- `diskutil` `Internal = false` → `external`; else `disk`

---
## Detection Timing

- On app open
- On window focus while on the Card step (card inserted, user returns)
- On "Detect cards" and when "Also show…" is toggled
- User's selection kept across refreshes if still present
- Not while a chosen folder is selected

---
## Folder Candidates (Analyse)

Card / drive / folder
    ↓
`DCIM/` present → each DCIM sub‑folder with photos, or its photo sub‑folders (shoot folders)
    ↓
No `DCIM/` → the chosen folder itself if it holds photos, then its top‑level folders

- Display names relative to DCIM (`100_2809/2026-10-10 - Wylam…`)
- A bare drive (`F:`) is resolved to its root
- Phones over USB (MTP) are not drives and are not sources — copy to a folder first

---
## Guarantees

- Read‑only: detection and analysis never write
- Source is never an import destination (validated)
- Analysis of a card with no photos reports zero, never fails
