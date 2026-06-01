# Role: Application module (see Stability Contract)

# workers/exif_scanner.py
# Background worker for EXIF scanning
# Orchestrates execution only – analysis delegated to Mapping

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
#  do not use - from photo_core.exif.reader import get_exif_gps as extract_exif_gps

SCAN_INTERVAL = 5  # seconds between idle checks


def exif_scanner_worker(ctx):
    """
    Background EXIF scanner worker.

    - Watches current active folder
    - Scans JPEGs
    - Extracts EXIF signals via Mapping
    - Populates ctx.exif_cache
    """
    log_info(ctx, "[EXIF] Scanner worker started")

    while not ctx.shutdown_event.is_set():
        active = ctx.state.get("current_active_folder")
        if not active or not os.path.isdir(active):
            time.sleep(SCAN_INTERVAL)
            continue

        cache_key = f"exif::{os.path.abspath(active)}"
        if cache_key in ctx.exif_cache:
            time.sleep(SCAN_INTERVAL)
            continue

        records = []
        count = 0
        log_info(ctx, f"[EXIF] Scanning JPEGs in {active}")

        for path in iter_jpegs(active):
            try:
                # ✅ Use tested GPS extractor directly
                meta = read_exif(path)

                lat = meta.get("Composite:GPSLatitude")
                lon = meta.get("Composite:GPSLongitude")

                if lat is not None and lon is not None:
                    gps = {
                        "lat": float(lat),
                        "lon": float(lon)
                    }
                else:
                    gps = None

                if coords:
                    lat, lon = coords
                    gps = {"lat": lat, "lon": lon}
                else:
                    gps = None

                log_info(ctx, msg=f"[GPS TEST] {path} → {gps}")


                if count == 0:
                    print("GPS TEST:", gps)

                record = {
                    "path": path,
                    "datetime": extract_exif_datetime(path),
                    "camera_model": extract_camera_model(path),
                    "lens": extract_lens_model(path),
                    "gps": gps
                }

                records.append(record)
                count += 1

                if count % 250 == 0:
                    log_info(ctx, msg=f"[EXIF] Scanned {count} images...")

            except Exception as e:
                log_info(ctx, msg=f"[EXIF] Failed EXIF for {path}: {e}")