# Role: Application module (see Stability Contract)

# workers/thumbnailer.py
# Background thumbnail generation worker

import os
import time

from utils.logging_bus import log_info
from utils.fs_utils import iter_jpegs

from photo_core.mapping.thumbnailing import generate_thumbnail

SCAN_INTERVAL = 5  # seconds


def thumbnail_worker(ctx):
    """
    Background thumbnail generator.

    Responsibilities:
    - Watches active folder
    - Generates thumbnails via Mapping
    - Stores thumbnails in ctx.thumb_cache
    - Never performs image analysis itself
    """
    log_info(ctx, "[THUMB] Thumbnail worker started")

    while not ctx.shutdown_event.is_set():
        active = ctx.state.get("current_active_folder")
        if not active or not os.path.isdir(active):
            time.sleep(SCAN_INTERVAL)
            continue

        for img_path in iter_jpegs(active):
            thumb_key = f"thumb::{img_path}"
            if thumb_key in ctx.thumb_cache:
                continue

            try:
                thumb_bytes = generate_thumbnail(img_path)
                ctx.thumb_cache[thumb_key] = thumb_bytes
            except Exception as e:
                log_info(ctx, f"[THUMB] Failed thumbnail for {img_path}: {e}")

        time.sleep(SCAN_INTERVAL)

    log_info(ctx, "[THUMB] Thumbnail worker stopped")
