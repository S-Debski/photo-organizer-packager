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

    # ✅ ✅ INCLUDE BOTH JPG AND RAW
    SUPPORTED_EXTS = (".jpg", ".jpeg", ".raf")

    files = []

    for root, _, filenames in os.walk(folder):
        for f in filenames:
            if f.lower().endswith(SUPPORTED_EXTS):
                full_path = os.path.join(root, f)
                files.append(full_path)

    print(f"📸 FAST thumbnails (JPG + RAW): {len(files)}")

    return files[:100]  # limit for UI performance


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