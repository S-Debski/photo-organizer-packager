# workers/exif_scanner.py
import os
import time

from utils.fs_utils import iter_jpegs
from photo_core.mapping.exif_utils import extract_exif
from utils.logging_bus import log_info

SCAN_INTERVAL = 5  # seconds between idle checks
def resolve_lens_name(ex):
    """
    Try multiple EXIF fields to resolve a human-readable lens name.
    Falls back safely when data is missing or vendor-specific.
    """
    return (
        ex.get("LensModel")
        or ex.get("Lens")
        or ex.get("LensName")
        or ex.get("LensSpecification")
        or ex.get("LensID")
        or "Unknown Lens"
    )

def exif_scanner_worker(ctx):
    """
    Background EXIF scanner.

    Responsibilities:
    - Scans JPEG files in the active folder
    - Extracts EXIF once per folder
    - Builds:
        * per-image EXIF cache (incl. GPS)
        * camera usage stats
        * lens usage stats
    - Stores everything in ctx.exif_cache
    - Never rescans unless active folder changes
    - Never blocks the UI or Flask threads
    """

    log_info(ctx, "[EXIF] Scanner worker started")

    while not ctx.shutdown_event.is_set():

        active = ctx.state.get("current_active_folder")
        if not active or not os.path.isdir(active):
            time.sleep(SCAN_INTERVAL)
            continue

        folder = os.path.abspath(active)
        cache_key = f"exif_stats::{folder}"

        # ✅ If already cached, do nothing
        if cache_key in ctx.exif_cache:
            time.sleep(SCAN_INTERVAL)
            continue

        log_info(ctx, f"[EXIF] Scanning JPEGs in {folder}")

        cameras = {}
        lenses = {}
        items = []

        count = 0

        for img_path in iter_jpegs(folder):
            try:
                ex = extract_exif(img_path)

                cam = ex.get("model") or "Unknown Camera"
                lens = resolve_lens_name(ex)

                cameras[cam] = cameras.get(cam, 0) + 1
                lenses[lens] = lenses.get(lens, 0) + 1

                items.append({
                    "filename": os.path.basename(img_path),
                    "path": img_path,
                    "camera": cam,
                    "lens": lens,
                    "lat": ex.get("lat"),
                    "lon": ex.get("lon"),
                })

                count += 1
                if count % 100 == 0:
                    log_info(ctx, f"[EXIF] Scanned {count} images...")

            except Exception as e:
                log_info(ctx, f"[EXIF] Failed EXIF for {img_path}: {e}")

        # ✅ Store final cache atomically
        ctx.exif_cache[cache_key] = {
            "items": items,
            "cameras": [
                {"model": k, "count": v} for k, v in cameras.items()
            ],
            "lenses": [
                {"lens": k, "count": v} for k, v in lenses.items()
            ],
        }

        log_info(ctx, f"[EXIF] Completed: {count} JPEGs scanned")

        # Idle until something changes
        time.sleep(SCAN_INTERVAL)

    log_info(ctx, "[EXIF] Scanner worker stopped")