# Role: Application module (see Stability Contract)

# backend/routes/set_active_folder.py
import os
from flask import jsonify

def api_set_active_folder(ctx, payload):
    folder = payload.get("folder")
    print("SET ACTIVE FOLDER:", folder)
    print("SET_ACTIVE_FOLDER CTX ID:", id(ctx))
    if not folder or not os.path.isdir(folder):
        return jsonify({"success": False, "error": "Invalid folder"}), 400

    # Update global active folder
    ctx.state["current_active_folder"] = folder

    # Clear cached thumbnails & EXIF for new context
    ctx.thumb_cache.clear()
    ctx.exif_cache.clear()

    return jsonify({"success": True, "active_folder": folder})