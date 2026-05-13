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

import time
from utils.fs_utils import iter_images
from photo_core.mapping.exif_dates import (
    extract_exif_datetime,
    extract_camera_model,
    extract_lens_model,
)
from photo_core.mapping.quality_classification import extract_exif_gps

SCAN_INTERVAL = 5  # seconds between idle checks


def exif_scanner_worker(ctx):
    print("✅ EXIF scanner worker started")

    last_scanned = None   # ✅ ADD HERE (outside loop)

    while not ctx.shutdown_event.is_set():

        folder = ctx.state.get("current_active_folder")

        # ✅ ADD THIS BLOCK HERE (before scanning starts)
        if not folder or folder == last_scanned:
            time.sleep(1)
            continue

        # ✅ build file list
        files = list(iter_images(folder))

        if not files:
            time.sleep(1)
            continue

        print(f"🔍 Starting EXIF scan for {len(files)} files")

        # ✅ init progress
        ctx.progress = {
            "stage": "scan",
            "total": len(files),
            "done": 0,
            "active": True,
            "message": "Scanning images..."
        }

        records = []

        for path in files:
            try:
                gps = extract_exif_gps(path)
                cam = extract_camera_model(path)
                lens = extract_lens_model(path)

                records.append({
                    "path": path,
                    "gps": gps,
                    "camera_model": cam,
                    "lens": lens
                })

            except Exception as e:
                print("❌ EXIF read error:", path, e)

            ctx.progress["done"] += 1

        ctx.exif_records = records

        ctx.progress["active"] = False
        ctx.progress["stage"] = "idle"

        print("✅ EXIF scan complete")

        # ✅ THIS IS CRITICAL — remembers the folder we just scanned
        last_scanned = folder

        time.sleep(SCAN_INTERVAL)
