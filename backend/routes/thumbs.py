# Role: Application module (see Stability Contract)

# =============================================================================
# File: backend/routes/thumbs.py
#
# Role:
#   Return thumbnail image paths for selected folder
#
# Responsibilities:
#   - Scan folder for supported image files
#   - Return list of image paths for frontend
#   - Provide proxy + full image endpoints
#
# Notes:
#   - FAST path: no EXIF scanning
#   - Now supports RAW + JPG pairing
# =============================================================================

import os
from flask import jsonify, send_file
from urllib.parse import unquote

from utils.fs_utils import iter_images
from utils.thumb_cache import build_thumb


# =============================================================================
# THUMBNAILS API
# =============================================================================
def api_thumbs(ctx, payload):

    folder = payload.get("folder") if payload else None

    # ✅ fallback to active folder if not supplied
    if not folder:
        folder = ctx.state.get("current_active_folder")

    if not folder:
        print("⚠️ No folder available for thumbnails")
        return []

    if not os.path.isdir(folder):
        print("⚠️ Invalid folder:", folder)
        return []

    # Every JPEG and RAW type (was .jpg/.jpeg/.raf only, capped at 100 —
    # larger cards were silently truncated for culling)
    files = sorted(iter_images(folder))

    print(f"📸 Thumbnails (JPG + RAW): {len(files)}")

    return files


# =============================================================================
# CACHED THUMBNAIL / PREVIEW
# =============================================================================
THUMB_SIZES = {"grid": 320, "strip": 160, "preview": 1600}


def api_thumb(ctx, img_path, size_name):
    """Downscaled JPEG (JPG or RAW source), cached on disk."""
    if not img_path:
        return jsonify({"success": False, "error": "No path"}), 400

    img_path = os.path.normpath(unquote(img_path))
    if not os.path.isfile(img_path):
        return jsonify({"success": False, "error": "File not found"}), 404

    size = THUMB_SIZES.get(size_name, THUMB_SIZES["grid"])
    try:
        tp = build_thumb(ctx.cache_dir, img_path, size)
    except Exception as e:
        print(f"Thumbnail failed for {img_path}: {e}")
        tp = None

    if not tp:
        return jsonify({"success": False, "error": "No preview available"}), 415

    # Cache key includes size+mtime, so the browser can keep it a long time
    return send_file(tp, mimetype="image/jpeg", max_age=86400)


# =============================================================================
# PHOTO PROXY (thumbnails / images)
# =============================================================================
def api_photo_proxy(ctx, img_path):
    if not img_path:
        return jsonify({"success": False, "error": "No path"}), 400

    img_path = os.path.normpath(unquote(img_path))

    if not os.path.isfile(img_path):
        return jsonify({
            "success": False,
            "error": "File not found",
            "path": img_path
        }), 404

    try:
        # ✅ Currently returning original image
        return send_file(
            img_path,
            mimetype="image/jpeg",  # safe default for JPG
            max_age=3600
        )

    except Exception as e:
        print(f"Photo proxy error: {e}")
        return jsonify({
            "success": False,
            "error": "Photo proxy failed",
            "details": str(e),
            "path": img_path
        }), 500


# =============================================================================
# FULL IMAGE (preview modal)
# =============================================================================
def api_full_image(ctx, img_path):
    if not img_path:
        return jsonify({"success": False, "error": "No path"}), 400

    img_path = os.path.normpath(img_path)

    if not os.path.isfile(img_path):
        return jsonify({
            "success": False,
            "error": "File not found",
            "path": img_path
        }), 404

    try:
        return send_file(
            img_path,
            mimetype="image/jpeg",
            conditional=True
        )
    except Exception as e:
        print(f"Full image error: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to load image",
            "details": str(e),
            "path": img_path
        }), 500