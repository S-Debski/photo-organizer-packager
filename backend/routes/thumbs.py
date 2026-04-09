# backend/routes/thumbs.py
import os
from flask import jsonify, send_file

from utils.fs_utils import iter_jpegs
from utils.thumb_cache import build_thumb
from utils.logging_bus import log_info


def api_thumbs(ctx, path=None):
    root = (
        path
        or ctx.state.get("current_active_folder")
        or ctx.state.get("current_sd_root")
    )

    if not root or not os.path.isdir(root):
        return jsonify([])

    # cache the jpeg list for faster UI
    cache_key = f"thumb_list::{os.path.abspath(root)}"
    cached = ctx.thumb_cache.get(cache_key)
    if cached:
        return jsonify(cached)

    images = list(iter_jpegs(root))
    ctx.thumb_cache[cache_key] = images

    log_info(ctx, f"Thumbnail list: {len(images)} images")
    return jsonify(images)


def api_photo_proxy(ctx, img_path):
    if not os.path.isfile(img_path):
        return jsonify({"success": False, "error": "Not found"}), 404

    thumb = build_thumb(ctx.cache_dir, img_path)
    return send_file(thumb, mimetype="image/jpeg", max_age=3600)


def api_full_image(ctx, img_path):
    if not os.path.isfile(img_path):
        return jsonify({"success": False, "error": "Not found"}), 404

    return send_file(img_path, mimetype="image/jpeg", conditional=True)