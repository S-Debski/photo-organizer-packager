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

from utils.fs_utils import iter_jpegs
from utils.logging_bus import log_info

from photo_core.mapping.exif_dates import (
    extract_exif_datetime,
    extract_camera_model,
    extract_lens_model,
)

from photo_core.exif.reader import read_exif
from utils.fs_utils import iter_images

# Session registration (v3.0)
from photo_core.pre_import.session_state import (
    register_paths,
    save_session,
)

SCAN_INTERVAL = 5  # seconds between idle checks
error_count = 0


# =============================================================================
# Helpers
# =============================================================================

def get_meta(meta, key):
    """Return EXIF value handling ExifTool namespaces."""
    return (
        meta.get(key)
        or meta.get(f"GPS:{key}")
        or meta.get(f"EXIF:{key}")
        or meta.get(f"Composite:{key}")
    )


def _folder_signature(paths: list[str]) -> tuple:
    """(path, size, mtime) for every file — changes when files are added/replaced."""
    sig = []
    for p in paths:
        try:
            st = os.stat(p)
            sig.append((p, st.st_size, st.st_mtime))
        except OSError:
            sig.append((p, None, None))
    return tuple(sorted(sig))


def _register_pairs_into_session(paths: list[str], ctx) -> None:
    """
    Register all RAW/JPG pairs in `paths` into the active ingest session.

    Safe to call with no active session — silently skips.
    """
    session     = ctx.state.get("session")
    session_dir = ctx.state.get("session_dir")

    if not session or not session_dir:
        # No active session — browsing without ingest, that's fine
        return

    registered = register_paths(session, paths)

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

        paths = list(iter_images(active))

        # ✅ Skip if the folder is unchanged since the last scan.
        # The signature (path, size, mtime) means added/replaced files
        # still trigger a rescan; set_active_folder clears the cache.
        signature = _folder_signature(paths)
        if ctx.exif_cache.get(cache_key) == signature:
            time.sleep(SCAN_INTERVAL)
            continue

        print(f"✅ Starting EXIF scan: {active}")
        print(f"📂 Found {len(paths)} images to scan")

        # -----------------------------------------------------------------
        # v3.0 — Register RAW/JPG pairs into the active session (if any).
        # /api/session/create also registers, so sessions created after
        # this scan still get a complete asset list.
        # -----------------------------------------------------------------
        _register_pairs_into_session(paths, ctx)

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

            except Exception as e:
                error_count += 1
                if error_count <= 3:   # enough to diagnose, without flooding
                    print(f"⚠️ EXIF failed for {path}: {type(e).__name__}: {e}")

        # ✅ Store results
        if records:
            print("✅ FINAL RECORD COUNT:", len(records))
            ctx.state["exif_records"] = records
            ctx.exif_cache[cache_key] = signature

            print(f"✅ EXIF scan complete: {len(records)} files processed")
            print(f"✅ STORED EXIF IN ctx.state: {len(records)}")

        else:
            print("⚠️ No EXIF records found")
            ctx.exif_cache[cache_key] = signature   # don't rescan an empty folder

        if error_count > 0:
            print(f"⚠️ EXIF errors: {error_count} files")

        time.sleep(SCAN_INTERVAL)