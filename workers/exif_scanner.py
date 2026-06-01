# ============================================================================
# Role: Background EXIF scanner worker (see Stability Contract)
#
# File: workers/exif_scanner.py
#
# Responsibilities:
#   - Scan images for EXIF metadata (read-only)
#   - Populate ctx.exif_records
#   - Update unified progress state (ctx.progress)
#
# Notes:
#   - Runs continuously as background worker
#   - Must NOT modify files
#   - Uses working directory paths only
# ============================================================================

# =============================================================================
# Role: Background EXIF scanner worker (single source of truth)
# File: workers/exif_scanner.py
# =============================================================================

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

    log_info(ctx, "[EXIF] Scanner worker started")
    log_info(ctx, msg=f"[WORKER CTX ID] {id(ctx)}")

    while not ctx.shutdown_event.is_set():

        active = ctx.state.get("current_active_folder")
        # ✅ Wait for copy to finish
        if not ctx.state.get("copy_complete"):
            print("⏳ Waiting for copy to complete...")
            time.sleep(SCAN_INTERVAL)
            continue

        print("🧪 ACTIVE:", active)

        # ✅ Skip if no active folder
        if not active or not os.path.isdir(active):
            print("🚫 Skipping: no active folder")
            time.sleep(SCAN_INTERVAL)
            continue

        cache_key = f"exif::{os.path.abspath(active)}"

        print("🧪 CACHE KEY:", cache_key)
        print("🧪 CACHE KEYS:", ctx.exif_cache.keys())

        # ✅ Resote cache from before problems
        if cache_key in ctx.exif_cache:
            print("🚫 Skipping: already in cache")
            time.sleep(SCAN_INTERVAL)
            continue

        records = []
        count = 0

        log_info(ctx, f"[EXIF] Scanning JPEGs in {active}")

        # ✅ MAIN LOOP

        paths = list(iter_jpegs(active))
        print("📂 JPEG FILES FOUND:", len(paths))

        for path in paths:
            try:
                meta = read_exif(path)

                # ✅ DEBUG — confirm we are processing files
                print("✅ PROCESSING:", path)

                log_info(ctx, msg=f"[META KEYS] {list(meta.keys())}")

                # ✅ GPS extraction (correct for YOUR files)# ✅("GPSLatitude")
                lat = get_meta(meta, "GPSLatitude")
                lon = get_meta(meta, "GPSLongitude")

                lat_ref = get_meta(meta, "GPSLatitudeRef")
                lon_ref = get_meta(meta, "GPSLongitudeRef")

                # ✅ Fallback for Composite GPSPosition
                if lat is None or lon is None:
                    pos = meta.get("Composite:GPSPosition") or meta.get("GPSPosition")
                    if pos:
                        try:
                            parts = str(pos).strip().split()
                            if len(parts) >= 2:
                                lat = float(parts[0])
                                lon = float(parts[1])
                        except Exception:
                            pass

                # ✅ DEBUG HERE (RAW values)
                if count < 3:
                    log_info(ctx, msg=f"[META KEYS] {list(meta.keys())}")
                    log_info(ctx, msg=f"[RAW GPS] lat={lat} lon={lon}")


                gps = None

                if lat is not None and lon is not None:
                    try:
                        lat = float(str(lat).split()[0])
                        lon = float(str(lon).split()[0])
                    except Exception:
                        gps = None
                    else:
                        lat_ref_clean = clean_ref(lat_ref) if lat_ref else ""
                        lon_ref_clean = clean_ref(lon_ref) if lon_ref else ""

                        if lat_ref_clean == "S":
                            lat = -lat
                        if lon_ref_clean == "W":
                            lon = -lon

                        # ✅ ADD THIS BLOCK
                        if 50 < lat < 60 and lon > 0:
                            log_info(ctx, msg=f"[UK FIX] correcting lon {lon} → {-lon}")
                            lon = -lon

                        gps = [lat, lon]

                # ✅ Build record (INSIDE loop + try block)
                record = {
                    "path": path,
                    "datetime": extract_exif_datetime(path),
                    "camera_model": extract_camera_model(path),
                    "lens": extract_lens_model(path),
                    "gps": gps
                }

                records.append(record)

                # ✅ DEBUG — confirm record actually added
                print("✅ RECORD ADDED")

                count += 1

                if count % 250 == 0:
                    log_info(ctx, msg=f"[EXIF] Scanned {count} images...")

            except Exception as e:
                log_info(ctx, msg=f"[EXIF ERROR] {path} → {e}")

            # ✅ AFTER LOOP (CRITICAL)

            if paths and records:
                ctx.exif_records = records
                ctx.exif_cache[cache_key] = True

                print("✅ EXIF scan complete:", len(records))  # ✅ ADD THIS
                log_info(ctx, f"✅ EXIF scan complete: {len(records)} records")
            else:
                print("⚠️ No valid EXIF records found — not caching")

            # ✅ pause worker cycle
            time.sleep(SCAN_INTERVAL)
