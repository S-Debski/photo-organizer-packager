# Role: Application module (see Stability Contract)

# =============================================================================
# File: backend/routes/thumbs.py
# Role: Return thumbnail image paths for selected folder
# =============================================================================

import os
from flask import jsonify, send_file
from urllib.parse import unquote

def api_thumbs(ctx, payload):

    folder = payload.get("folder") if payload else None

    # ✅ fallback to active folder if not supplied
    if not folder:
        folder = ctx.state.get("current_active_folder")

    if not folder:
        print("⚠️ No folder available for thumbnails")
        return []

from utils.fs_utils import iter_jpegs  # ✅ add at top if not already

def api_thumbs(ctx, payload):

        folder = payload.get("folder") if payload else None

        if not folder:
            folder = ctx.state.get("current_active_folder")

        if not folder:
            print("⚠️ No folder available for thumbnails")
            return []

        if not os.path.isdir(folder):
            print("⚠️ Invalid folder:", folder)
            return []

        # ✅ FAST path: direct file scan (NO EXIF)
        files = []

        for path in iter_jpegs(folder):
            files.append(path)

        print("📸 FAST thumbnails:", len(files))

        return files[:100]
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
        thumb = img_path  # ✅ just return original image for now
        if not os.path.isfile(thumb):
            return jsonify({
                "success": False,
                "error": "Thumbnail generation failed",
                "path": img_path
            }), 500

        return send_file(
            thumb,
            mimetype="image/jpeg",
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
