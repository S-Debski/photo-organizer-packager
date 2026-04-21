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

    stats = compute_exif_stats(image_paths)

    ctx.exif_cache[cache_key] = stats

    return jsonify({
        "ready": True,
        **stats
    })