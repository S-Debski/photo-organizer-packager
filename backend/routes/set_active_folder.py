# Role: Application module (see Stability Contract)

# backend/routes/set_active_folder.py

import os
import shutil
from datetime import datetime
from flask import jsonify

from utils.fs_utils import get_default_working_base


def copy_to_working(src_folder, dst_folder):
    copied_files = []

    for root, _, files in os.walk(src_folder):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg")):
                src_path = os.path.join(root, f)

                # ✅ preserve subfolder structure
                rel_path = os.path.relpath(root, src_folder)
                target_dir = os.path.join(dst_folder, rel_path)
                os.makedirs(target_dir, exist_ok=True)

                dst_path = os.path.join(target_dir, f)

                shutil.copy2(src_path, dst_path)
                copied_files.append(dst_path)

    return copied_files


def api_set_active_folder(ctx, payload):
    folder = payload.get("folder")

    print("SET ACTIVE FOLDER:", folder)
    print("SET_ACTIVE_FOLDER CTX ID:", id(ctx))

    if not folder or not os.path.isdir(folder):
        return jsonify({"success": False, "error": "Invalid folder"}), 400

    # ✅ STEP 1 — determine working base (user or default)
    base_dir = payload.get("working_dir") or ctx.working_base_dir

    if base_dir:
        base_dir = os.path.abspath(base_dir)

        try:
            print(f"📁 Ensuring base working dir: {base_dir}")
            os.makedirs(base_dir, exist_ok=True)

        except Exception as e:
            print(f"❌ Failed to create working base: {base_dir}")
            print("ERROR:", e)

            base_dir = get_default_working_base()
            os.makedirs(base_dir, exist_ok=True)

            print(f"⚠️ Falling back to default: {base_dir}")

    else:
        base_dir = get_default_working_base()
        os.makedirs(base_dir, exist_ok=True)

    # ✅ Store it for future use
    ctx.working_base_dir = base_dir

    # ✅ STEP 2 — create session directory
    session_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    working_dir = os.path.join(base_dir, session_name)

    os.makedirs(working_dir, exist_ok=True)

    print("📁 Working directory:", working_dir)

    # ✅ STEP 3 — copy files into working directory
    print("📦 Copying files to working directory...")
    working_files = copy_to_working(folder, working_dir)
    print(f"✅ Copied {len(working_files)} files")

    # ✅ STEP 4 — update context
    ctx.state["current_active_folder"] = working_dir
    ctx.state["working_files"] = working_files

    ctx.working_dir = working_dir
    ctx.session_id = session_name

    # ✅ STEP 5 — clear caches
    ctx.exif_cache.clear()
    ctx.exif_records = []
    ctx.thumb_cache.clear()

    return jsonify({
        "success": True,
        "active_folder": working_dir,
        "working_dir": working_dir,
        "file_count": len(working_files)
    })