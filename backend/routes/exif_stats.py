# backend/routes/exif_stats.py
import os
from flask import jsonify

from utils.fs_utils import iter_jpegs
from utils.exif_utils import extract_exif
from utils.logging_bus import log_info


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

    # ✅ If already computed, signal READY
    if cached:
        return jsonify({
            "ready": True,
            **cached
        })

    camera_counter = {}
    lens_counter = {}
    count = 0

    for img in iter_jpegs(root):
        ex = extract_exif(img)
        cam = ex.get("model") or "Unknown"
        lens = ex.get("lens") or "Unknown Lens"

        camera_counter[cam] = camera_counter.get(cam, 0) + 1
        lens_counter[lens] = lens_counter.get(lens, 0) + 1

        count += 1
        if count % 250 == 0:
            log_info(ctx, f"EXIF Stats: scanned {count} images…")

    payload = {
        "cameras": [{"model": k, "count": v} for k, v in camera_counter.items()],
        "lenses": [{"lens": k, "count": v} for k, v in lens_counter.items()],
    }

    ctx.exif_cache[cache_key] = payload

    # ✅ Signal READY on first completion
    return jsonify({
        "ready": True,
        **payload
    })