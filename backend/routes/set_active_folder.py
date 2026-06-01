# Role: Application module (see Stability Contract)

# backend/routes/set_active_folder.py
import backend.api_server as api_server   # ✅ shared global ctx

import os
import shutil
import time
from flask import jsonify

from utils.fs_utils import get_default_working_base

import logging
logger = logging.getLogger("set_active_folder")
from backend.utils.logging_utils import backend_log

def copy_to_working(src_folder, dst_folder):
    copied_files = []

    for root, _, files in os.walk(src_folder):
        for f in files:
            from utils.fs_utils import IMAGE_EXTS_ALL
            if f.lower().endswith(IMAGE_EXTS_ALL):
                src_path = os.path.join(root, f)

                # ✅ preserve subfolder structure
                rel_path = os.path.relpath(root, src_folder)
                target_dir = os.path.join(dst_folder, rel_path)
                os.makedirs(target_dir, exist_ok=True)

                dst_path = os.path.join(target_dir, f)

                # ✅ Skip if source and destination are the same
                if os.path.abspath(src_path) == os.path.abspath(dst_path):
                    continue

                # ✅ Skip if same file
                if os.path.abspath(src_path) == os.path.abspath(dst_path):
                    continue

                # ✅ Skip if file already exists
                if os.path.exists(dst_path):
                    continue

                # ✅ Retry copy (handles Windows locks)
                for attempt in range(3):
                    try:
                        shutil.copy2(src_path, dst_path)
                        copied_files.append(dst_path)  # ✅ ONLY on success
                        break
                    except PermissionError:
                        time.sleep(0.2)

                else:
                    print(f"[COPY FAILED] {src_path}")

    return copied_files

def api_set_active_folder(payload):
    # ✅ mark copy as not complete yet
    api_server.ctx.state["copy_complete"] = False
    folder = payload.get("folder")
    working_dir_input = payload.get("working_dir")

    backend_log(f"📂 Set active folder requested: {folder}")

    if not folder or not os.path.isdir(folder):
        logger.error(f"Invalid folder: {folder}")
        return jsonify({"success": False, "error": "Invalid folder"}), 400

    # ✅ STEP 1 — determine working base (user or default)
    base_dir = working_dir_input or api_server.ctx.working_base_dir

    if base_dir:
        base_dir = os.path.abspath(base_dir)

        try:
            os.makedirs(base_dir, exist_ok=True)
            logger.info(f"Ensured base working dir: {base_dir}")

        except Exception as e:
            logger.error(f"Failed to create base dir: {base_dir} → {e}")

            base_dir = get_default_working_base()
            os.makedirs(base_dir, exist_ok=True)

            logger.warning(f"Fallback to default base: {base_dir}")
    else:
        base_dir = get_default_working_base()
        os.makedirs(base_dir, exist_ok=True)

    api_server.ctx

    # ✅ STEP 2 — resolve working directory

    if working_dir_input:
        working_dir = os.path.abspath(working_dir_input.rstrip("\\/"))
        session_name = os.path.basename(working_dir)
    else:
        session_name = os.path.basename(folder.rstrip("\\/"))
        working_dir = os.path.join(base_dir, session_name)

    # ✅ 🔥 ADD IT RIGHT HERE
    api_server.ctx.state["current_active_folder"] = working_dir
    print("✅ ACTIVE FOLDER SET:", api_server.ctx.state["current_active_folder"])

    # ✅ STEP 3 — copy files
    backend_log("📦 Preparing working directory...")

    # ✅ STEP 3 — copy files (skip if already populated)
    backend_log("📦 Preparing working directory...")

    already_populated = False

    if os.path.exists(working_dir):
        if any(os.scandir(working_dir)):  # ✅ folder not empty
            already_populated = True

    if already_populated:
        backend_log("⚡ Using existing working data (skipping copy)")
        logger.info("Working directory already populated — skipping copy")

        # ✅ rebuild file list
        working_files = []
        for root, _, files in os.walk(working_dir):
            for name in files:
                working_files.append(os.path.join(root, name))

    else:
        backend_log("📦 Copying files to working directory...")
        working_files = copy_to_working(folder, working_dir)
        print("✅ Copy complete:", len(working_files))

        api_server.ctx.state["copy_complete"] = True

        logger.info(f"Copied {len(working_files)} files")
        backend_log(f"✅ Copied {len(working_files)} files")

    # ✅ STEP 4 — update context
    api_server.ctx.state["current_active_folder"] = working_dir
    print("✅ ACTIVE FOLDER SET:", api_server.ctx.state["current_active_folder"])

    api_server.ctx.state["working_files"] = working_files

    api_server.ctx.working_dir = working_dir
    api_server.ctx.session_id = session_name

    # ✅ STEP 5 — clear caches (FORCE worker rescan)

    api_server.ctx.exif_cache.clear()  # ✅ clear ALL cached folders

    api_server.ctx.exif_records = []
    api_server.ctx.thumb_cache.clear()

    print("🧹 EXIF cache fully cleared → worker must rescan")

    # ✅ RETURN MUST BE LAST
    return jsonify({
        "success": True,
        "active_folder": working_dir,
        "working_dir": working_dir,
        "file_count": len(working_files)
    })
