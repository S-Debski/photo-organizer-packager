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
#
# -----------------------------------------------------------------------------
# Pipeline Role
# -----------------------------------------------------------------------------
#
# copy_to_working() → sets copy_complete = True
#       ↓
# exif_scanner_worker detects ready state
#       ↓
# iterates JPEG files
#       ↓
# extracts EXIF → GPS → metadata
#       ↓
# writes ctx.exif_records
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
SCAN_INTERVAL = 5  # seconds between idle checks

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
        # ✅ already numeric
        if isinstance(value, (int, float)):
            return float(value)

        # ✅ ExifTool sometimes returns list/tuple
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60) + (s / 3600)

        # ✅ Sometimes nested lists like [[54,32,12]]
        if isinstance(value, (list, tuple)) and len(value) == 1:
            return to_decimal(value[0])

        # ✅ string fallback
        value = str(value).strip()

        # ✅ simple float string
        try:
            return float(value)
        except:
            pass

        # ✅ DMS format string
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

def exif_scanner_worker(ctx):
    """
    Background worker for EXIF metadata extraction.

    Behaviour:
        • Runs continuously in a loop
        • Waits until copy_complete is True before scanning
        • Processes all JPEG files in the working directory
        • Extracts metadata including GPS coordinates
        • Stores results in ctx.exif_records
        • Uses cache to avoid duplicate scans

    Execution Flow:
        WAIT → SCAN → STORE → CACHE → SLEEP → LOOP

    Important:
        • Must NOT access files while copy is running (avoids locks)
        • Must write ctx.exif_records only after full scan completes
        • Sleeping occurs AFTER full scan cycle (critical for performance)
    """
    log_info(ctx, "[EXIF] Scanner worker started")
    log_info(ctx, msg=f"[WORKER CTX ID] {id(ctx)}")

    waiting_logged = False  # ✅ ensures "waiting" prints only once

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
            time.sleep(SCAN_INTERVAL)
            continue

        print("✅ Starting EXIF scan...")

        paths = list(iter_images(active))
        print("📂 FILES FOUND:", len(paths))

        print("🔍 ACTIVE (worker):", active)

        for root, dirs, files in os.walk(active):
            print("📁 WALK:", root, "FILES:", len(files))
            break

        records = []
        count = 0

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
                        # ✅ force numeric values
                        lat = float(str(lat).split()[0])
                        lon = float(str(lon).split()[0])

                        # ✅ apply EXIF hemisphere refs
                        if lat_ref and str(lat_ref).upper().startswith("S"):
                            lat = -lat
                        if lon_ref and str(lon_ref).upper().startswith("W"):
                            lon = -lon

                        # ✅ UK correction (FINAL source of truth)
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
                count += 1

            except Exception as e:
                print("⚠️ EXIF error:", path, e)

        # ✅ Store results
        if records:
            ctx.exif_records = records
            ctx.exif_cache[cache_key] = True

            print("✅ EXIF scan complete:", len(records))
        else:
            print("⚠️ No EXIF records found")

        time.sleep(SCAN_INTERVAL)