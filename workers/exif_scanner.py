# Role: Application module (see Stability Contract)

# workers/exif_scanner.py
# Background EXIF scanner worker
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
from photo_core.mapping.quality_classification import extract_exif_gps

SCAN_INTERVAL = 5  # seconds between idle checks
progress_state = {
    "total": 0,
    "processed": 0,
    "active": False
}

def exif_scanner_worker(ctx):
    """
    Background EXIF scanner.

    Responsibilities:
    - Watches current active folder
    - Scans JPEGs
    - Extracts EXIF signals via Mapping
    - Populates ctx.exif_cache
    - Never interprets EXIF
    """

    log_info(ctx, "[EXIF] Scanner worker started")

    while not ctx.shutdown_event.is_set():
        active = ctx.state.get("current_active_folder")
        if not active:
            time.sleep(SCAN_INTERVAL)
            continue

        # DEBUG ONLY
        # print("ACTIVE FOLDER IN WORKER:", active)

        if not active or not os.path.isdir(active):
            time.sleep(SCAN_INTERVAL)
            continue

        cache_key = f"exif::{os.path.abspath(active)}"
        if cache_key in ctx.exif_cache:
            time.sleep(SCAN_INTERVAL)
            progress_state["active"] = False
            continue

        log_info(ctx, f"[EXIF] Scanning JPEGs in {active}")

        records = []
        count = 0

        files = ctx.state.get("working_files")

        if not files:
            files = list(iter_jpegs(active))  # ✅ fallback (safe)
            
        progress_state["total"] = len(files)
        progress_state["processed"] = 0
        progress_state["active"] = True

        for i, path in enumerate(files):
            try:
                gps = extract_exif_gps(path)
                # ✅ DEBUG
                if False:  # DEBUG
                    print("📍 GPS RAW:", gps)
                    if gps:
                        print("✅ GPS FOUND:", gps)
                    else:
                        print("❌ NO GPS:", path)

                records.append({
                    "path": path,
                    "datetime": extract_exif_datetime(path),
                    "camera_model": extract_camera_model(path),
                    "lens": extract_lens_model(path),
                    "gps": extract_exif_gps(path),
                })
                count += 1
                progress_state["processed"] = i + 1
                if count % 250 == 0:
                    log_info(ctx, f"[EXIF] Scanned {count} images...")
            except Exception as e:
                log_info(ctx, f"[EXIF] Failed EXIF for {path}: {e}")

        ctx.exif_cache[cache_key] = records
        ctx.exif_records = records
        log_info(ctx, f"[EXIF] Completed: {count} JPEGs scanned")
        progress_state["active"] = False

        time.sleep(SCAN_INTERVAL)

    log_info(ctx, "[EXIF] Scanner worker stopped")
