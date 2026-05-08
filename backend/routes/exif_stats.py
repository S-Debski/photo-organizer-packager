# Role: Application module

# backend/routes/exif_stats.py
# HTTP API wrapper for EXIF statistics
# Delegates analysis to photo_core.mapping.exif_stats

import os
from flask import jsonify

from utils.fs_utils import iter_jpegs
from utils.logging_bus import log_info

from photo_core.mapping.exif_stats import compute_exif_stats


def api_exif_stats(ctx, path=None):
    root = (
            path
            or ctx.state.get("current_active_folder")
            or ctx.state.get("current_sd_root")
    )

    if not root or not os.path.isdir(root):
        return jsonify({
            "ready": False,
            "cameras": [],
            "lenses": []
        })

    cache_key = f"exif_stats::{os.path.abspath(root)}"
    cached = ctx.exif_cache.get(cache_key)

    # Return cached result if present
    if cached:
        return jsonify({
            "ready": True,
            **cached
        })

    log_info(ctx, f"EXIF Stats: scanning {root}")

    image_paths = list(iter_jpegs(root))
    from pathlib import Path

    all_files = list(Path(root).rglob("*"))

    image_paths = [
        str(p) for p in all_files
        if p.suffix.lower() in [".jpg", ".jpeg", ".raf"]
    ]

    # ✅ NEW: count types
    raw_count = sum(1 for p in image_paths if p.lower().endswith(".raf"))
    jpg_count = sum(1 for p in image_paths if p.lower().endswith((".jpg", ".jpeg")))

    stats = compute_exif_stats(image_paths)

    ctx.exif_cache[cache_key] = stats

    return jsonify({
        "ready": True,
        "raw_count": raw_count,
        "jpg_count": jpg_count,
        "total_images": len(image_paths),
        **stats
    })
