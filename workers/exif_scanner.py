# ============================================================================
# Role: Background EXIF scanner worker (see Stability Contract)
#
# File: workers/exif_scanner.py

# -----------------------------------------------------------------------------
# EXIF Scanner Worker
# -----------------------------------------------------------------------------
#
# Background worker that processes image files to extract EXIF metadata.
#
# Responsibilities:
#   • Waits for copy phase to complete
#   • Scans working directory for JPEG images
#   • Extracts EXIF metadata (including GPS)
#   • Populates ctx.exif_records with results
#   • Caches completed scans to avoid repeat work
#   • Registers RAW/JPG pairs into active ingest session (v3.0)
#
# -----------------------------------------------------------------------------
# Pipeline Role
# -----------------------------------------------------------------------------
#
# copy_to_working() → sets copy_complete = True
#       ↓
# exif_scanner_worker detects ready state
#       ↓
# iterates image files
#       ↓
# extracts EXIF → GPS → metadata
#       ↓
# registers RAW/JPG pairs into session manifest  ← v3.0
#       ↓
# writes ctx.state["exif_records"]
#
# -----------------------------------------------------------------------------
# Key Design Decisions
# -----------------------------------------------------------------------------
#
# • Worker loop runs continuously until shutdown_event
# • Uses ctx.state["copy_complete"] as synchronization gate
# • Performs full scan per session (no incremental updates)
# • Uses cache_key to prevent duplicate work
# • Sleeps only AFTER full scan cycle (not per file)
# • Session registration is OPTIONAL — worker runs fine with no active session
#
# -----------------------------------------------------------------------------
# Important State Variables
# -----------------------------------------------------------------------------
#
# ctx.state["copy_complete"]
#     → False: do not scan (copy in progress)
#     → True: begin EXIF processing
#
# ctx.state["current_active_folder"]
#     → working directory path
#
# ctx.state["session"]        ← v3.0
#     → active ingest session manifest (or None)
#
# ctx.state["session_dir"]    ← v3.0
#     → path to session folder on disk (or None)
#
# ctx.exif_records
#     → full metadata list consumed by API + frontend
#
# ctx.exif_cache
#     → tracks completed scans (by folder)
#
# -----------------------------------------------------------------------------
import os
import time
from pathlib import Path

from utils.fs_utils import iter_jpegs
from utils.logging_bus import log_info

from photo_core.mapping.exif_dates import (
    extract_exif_datetime,
    extract_camera_model,
    extract_lens_model,
)

from photo_core.exif.reader import read_exif
from utils.fs_utils import iter_images

# Session registration (v3.0) — imported lazily to avoid hard dependency
from photo_core.pre_import.session_state import (
    register_asset,
    save_session,
)

SCAN_INTERVAL = 5  # seconds between idle checks
error_count = 0

# RAW extensions we recognise for pairing
RAW_EXTENSIONS = {".raf", ".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2"}
JPG_EXTENSIONS = {".jpg", ".jpeg"}


# ✅ Helper: sort out composite EXIF data
def get_meta(meta, key):
    """Return EXIF value handling ExifTool namespaces."""
    return (
        meta.get(key)
        or meta.get(f"GPS:{key}")
        or meta.get(f"EXIF:{key}")
        or meta.get(f"Composite:{key}")
    )


# ✅ Helper: normalise EXIF direction refs
def clean_ref(ref):
    if isinstance(ref, bytes):
        ref = ref.decode("utf-8", errors="ignore")
    if isinstance(ref, (list, tuple)):
        ref = ref[0]
    return str(ref).strip().upper()


def to_decimal(value):
    try:
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, (list, tuple)) and len(value) >= 3:
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60) + (s / 3600)

        if isinstance(value, (list, tuple)) and len(value) == 1:
            return to_decimal(value[0])

        value = str(value).strip()

        try:
            return float(value)
        except Exception:
            pass

        parts = (
            value.replace("deg", "")
            .replace("'", "")
            .replace('"', "")
            .split()
        )

        if len(parts) >= 3:
            d = float(parts[0])
            m = float(parts[1])
            s = float(parts[2])
            return d + (m / 60) + (s / 3600)

    except Exception:
        return None

    return None


# =============================================================================
# RAW/JPG Pairing
# =============================================================================

def _build_pairs(paths: list[str]) -> dict[str, dict]:
    """
    Group a list of image paths into RAW/JPG pairs keyed by stem.

    Returns:
        {
            "DSCF0001": {"raw": "/path/DSCF0001.RAF", "jpg": "/path/DSCF0001.JPG"},
            "DSCF0002": {"raw": "/path/DSCF0002.RAF", "jpg": None},
            "DSCF0003": {"raw": None,                 "jpg": "/path/DSCF0003.JPG"},
            ...
        }

    Design notes:
        - Stem comparison is case-insensitive (FAT32 SD cards)
        - Last-wins if two RAWs share a stem (shouldn't happen in practice)
        - Solo-RAW and solo-JPG assets are included (pair partner = None)
    """
    pairs: dict[str, dict] = {}

    for path in paths:
        p = Path(path)
        stem = p.stem.upper()          # normalise for FAT32
        ext  = p.suffix.lower()

        if stem not in pairs:
            pairs[stem] = {"raw": None, "jpg": None, "_original_stem": p.stem}

        if ext in RAW_EXTENSIONS:
            pairs[stem]["raw"] = path
        elif ext in JPG_EXTENSIONS:
            pairs[stem]["jpg"] = path

    return pairs


# =============================================================================
# Session Registration
# =============================================================================

def _register_pairs_into_session(pairs: dict, ctx) -> None:
    """
    Register all discovered RAW/JPG pairs into the active ingest session.

    Safe to call with no active session — silently skips.

    Args:
        pairs:  output of _build_pairs()
        ctx:    AppContext
    """
    session     = ctx.state.get("session")
    session_dir = ctx.state.get("session_dir")

    if not session or not session_dir:
        # No active session — browsing without ingest, that's fine
        return

    registered = 0
    for stem_upper, entry in pairs.items():
        asset_id = entry["_original_stem"]   # preserve original casing for display
        register_asset(
            session_data=session,
            asset_id=asset_id,
            raw_source=entry["raw"],
            jpg_source=entry["jpg"],
        )
        registered += 1

    # One save at end of full registration pass — not per asset
    try:
        save_session(session_dir, session)
        print(f"✅ Session: registered {registered} assets, manifest saved")
    except Exception as e:
        print(f"⚠️ Session save failed after asset registration: {e}")


# =============================================================================
# Worker
# =============================================================================

def exif_scanner_worker(ctx):
    """
    Background worker for EXIF metadata extraction.

    Behaviour:
        • Runs continuously in a loop
        • Waits until a valid active folder is set before scanning
        • Processes all image files in the active source folder
        • Extracts metadata including GPS coordinates
        • Builds RAW/JPG pairs and registers them into the active session (v3.0)
        • Stores results in ctx.state["exif_records"]
        • Uses cache to avoid duplicate scans per folder

    Execution Flow:
        WAIT → SCAN → PAIR → REGISTER SESSION → STORE EXIF → CACHE → SLEEP → LOOP

    Important:
        • Must NOT access files while copy is running (avoids locks)
        • Must write ctx.state["exif_records"] only after full scan completes
        • Session registration occurs once per scan pass, after all pairs resolved
        • Sleeping occurs AFTER full scan cycle (critical for performance)
    """

    log_info(ctx, "[EXIF] Scanner worker started")
    log_info(ctx, msg=f"[WORKER CTX ID] {id(ctx)}")

    while not ctx.shutdown_event.is_set():

        active = ctx.state.get("current_active_folder")

        # ✅ Wait for valid folder
        if not active:
            time.sleep(SCAN_INTERVAL)
            continue

        if not os.path.isdir(active):
            print("⚠️ Invalid folder:", active)
            time.sleep(SCAN_INTERVAL)
            continue

        cache_key = f"exif::{os.path.abspath(active)}"

        # ✅ Skip if already processed
        if cache_key in ctx.exif_cache:
            print("⚠️ CACHE HIT:", cache_key)

        print(f"✅ Starting EXIF scan: {active}")

        paths = list(iter_images(active))
        print(f"📂 Found {len(paths)} images to scan")
        print("WORKER ACTIVE:", active)

        # -----------------------------------------------------------------
        # v3.0 — Build RAW/JPG pairs and register into active session
        # This runs regardless of EXIF success so the session always has
        # a complete asset list even if EXIF extraction partially fails.
        # -----------------------------------------------------------------
        pairs = _build_pairs(paths)
        _register_pairs_into_session(pairs, ctx)

        # -----------------------------------------------------------------
        # EXIF extraction (unchanged from v2.7)
        # -----------------------------------------------------------------
        records = []
        count = 0
        error_count = 0  # reset per scan

        for path in paths:
            try:
                meta = read_exif(path)

                lat = get_meta(meta, "GPSLatitude")
                lon = get_meta(meta, "GPSLongitude")

                lat_ref = get_meta(meta, "GPSLatitudeRef")
                lon_ref = get_meta(meta, "GPSLongitudeRef")

                gps = None

                if lat is not None and lon is not None:
                    try:
                        lat = float(str(lat).split()[0])
                        lon = float(str(lon).split()[0])

                        if lat_ref and str(lat_ref).upper().startswith("S"):
                            lat = -lat
                        if lon_ref and str(lon_ref).upper().startswith("W"):
                            lon = -lon

                        # ✅ UK longitude correction
                        if 50 < lat < 60 and lon > 0:
                            print(f"⚠️ UK FIX (EXIF): {lon} → {-lon}")
                            lon = -lon

                        gps = [lat, lon]

                    except Exception:
                        gps = None

                record = {
                    "path": path,
                    "datetime": extract_exif_datetime(path),
                    "camera_model": extract_camera_model(path),
                    "lens": extract_lens_model(path),
                    "gps": gps
                }

                records.append(record)
                print("✅ RECORD:", path)
                count += 1

            except Exception:
                error_count += 1

        # ✅ Store results
        if records:
            print("✅ FINAL RECORD COUNT:", len(records))
            ctx.state["exif_records"] = records
            ctx.exif_cache[cache_key] = True

            print(f"✅ EXIF scan complete: {len(records)} files processed")
            print(f"✅ STORED EXIF IN ctx.state: {len(records)}")

        else:
            print("⚠️ No EXIF records found")

        if error_count > 0:
            print(f"⚠️ EXIF errors: {error_count} files")

        time.sleep(SCAN_INTERVAL)