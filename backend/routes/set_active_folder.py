# backend/routes/set_active_folder.py

# -----------------------------------------------------------------------------
# Photo Organizer – Active Folder Setup & Pipeline Bootstrap
# -----------------------------------------------------------------------------
#
# This module initialises a new session:
#   • prepares working directory
#   • copies source files (robocopy, fast)
#   • resets caches
#   • signals EXIF worker to begin processing
#
# -----------------------------------------------------------------------------


import backend.api_server as api_server   # ✅ shared global ctx

import os
import shutil
import time
from flask import jsonify

from utils.fs_utils import get_default_working_base
from backend.utils.logging_utils import backend_log

import logging
logger = logging.getLogger("set_active_folder")

import subprocess


# -----------------------------------------------------------------------------
# COPY OPERATION
# -----------------------------------------------------------------------------
def copy_to_working(src_folder, dst_folder):
    """
    Copy image contents from src_folder into dst_folder using robocopy.

    Behaviour:
        • Copies ALL subfolders (/E)
        • Does NOT duplicate root folder (hybrid structure)
        • Uses OS-level copy for performance
        • No per-file Python handling

    Returns:
        [] (empty list by design — EXIF worker handles scanning)

    Notes:
        • Fast (~instant for moderate datasets)
        • Does not rebuild file list
    """
    for root, _, files in os.walk(src_folder):
        for f in files[:20]:  # just first few files
            try:
                with open(os.path.join(root, f), 'rb') as fh:
                    fh.read(1024)  # read 1KB
            except:
                pass
        break  # only first folder

    os.makedirs(dst_folder, exist_ok=True)

    process = subprocess.Popen([
        "robocopy",
        src_folder,
        dst_folder,
        "/E",
        "/R:0",
        "/W:0",
        "/NFL",
        "/NDL",
        "/NP",
        "/MT:16"
    ])

    return process  # ✅ RETURN THE PROCESS


# -----------------------------------------------------------------------------
# MAIN ENTRY POINT
# -----------------------------------------------------------------------------
def api_set_active_folder(payload):
    """
    Initialise a new processing session.

    Pipeline:
        1. Validate input folder
        2. Resolve working directory (hybrid mode)
        3. Reset working directory
        4. Copy files into working directory
        5. Compute file count (UI only)
        6. Clear EXIF + thumbnail caches
        7. Set copy_complete → triggers EXIF worker
        8. Update global context

    Args:
        payload (dict):
            {
                "folder": str,       # source folder
                "working_dir": str   # optional override
            }

    Returns:
        JSON response with:
            success
            working_dir
            file_count

    ctx.state lifecycle:
        copy_complete = False → worker waits
        copy completes
        caches cleared
        copy_complete = True → worker starts EXIF scan

    Important:
        Order matters:
            cache clear → THEN copy_complete = True
    """

    # -------------------------------------------------------------------------
    # ✅ STATE: mark not ready (worker will wait)
    # -------------------------------------------------------------------------
    api_server.ctx.state["copy_complete"] = False

    folder = payload.get("folder")
    working_dir_input = payload.get("working_dir")

    backend_log(f"📂 Set active folder requested: {folder}")

    if not folder or not os.path.isdir(folder):
        logger.error(f"Invalid folder: {folder}")
        return jsonify({"success": False, "error": "Invalid folder"}), 400

    # -------------------------------------------------------------------------
    # STEP 1 — resolve base directory
    # -------------------------------------------------------------------------
    base_dir = working_dir_input or api_server.ctx.working_base_dir

    if base_dir:
        base_dir = os.path.abspath(base_dir)

        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception:
            base_dir = get_default_working_base()
            os.makedirs(base_dir, exist_ok=True)

    else:
        base_dir = get_default_working_base()
        os.makedirs(base_dir, exist_ok=True)

    # -------------------------------------------------------------------------
    # STEP 2 — resolve working directory (HYBRID)
    # -------------------------------------------------------------------------
    # ✅ FORCE hybrid structure (ignore incoming working_dir_input for now)
    working_dir = base_dir
    session_name = os.path.basename(folder.rstrip("\\/"))


    # -------------------------------------------------------------------------
    # ✅ STATE: expose active folder early
    # -------------------------------------------------------------------------
    api_server.ctx.state["current_active_folder"] = folder
    print("✅ ACTIVE SOURCE FOLDER:", folder)

    # -------------------------------------------------------------------------
    # STEP 3 — reset + copy
    # -------------------------------------------------------------------------
    backend_log("📦 Preparing working directory...")

    # Clean working directory (deterministic runs)
    # ✅ allow any file locks to clear
    time.sleep(0.5)

    def safe_rmtree(path, retries=5, delay=0.5):
        for i in range(retries):
            try:
                shutil.rmtree(path)
                return
            except (PermissionError, OSError) as e:
                print(f"⚠️ rmtree retry {i + 1}: {e}")
                time.sleep(delay)

        raise RuntimeError(f"Failed to remove working_dir after {retries} attempts")

    # Copy contents
    backend_log("📦 Copying files to working directory...")
    process = api_server.ctx.state["current_active_folder"] = folder

    # ✅ do NOT block — let copy run in background
    backend_log("✅ Copy started (background)")

    # -------------------------------------------------------------------------
    # STEP 4 — compute file count (UI ONLY)
    # -------------------------------------------------------------------------
    file_count = sum(len(files) for _, _, files in os.walk(working_dir))

    # ✅ STATE: not real file list — just count placeholder
    api_server.ctx.state["working_files"] = list(range(file_count))

    # -------------------------------------------------------------------------
    # STEP 5 — reset caches BEFORE releasing worker
    # -------------------------------------------------------------------------
    api_server.ctx.exif_cache.clear()
    api_server.ctx.exif_records = []
    api_server.ctx.thumb_cache.clear()

    print("🧹 EXIF cache cleared → worker must rescan")

    # -------------------------------------------------------------------------
    # STEP 6 — final context update
    # -------------------------------------------------------------------------
    api_server.ctx.working_dir = working_dir
    api_server.ctx.session_id = session_name

    # -------------------------------------------------------------------------
    # RETURN
    # -------------------------------------------------------------------------
    return jsonify({
        "success": True,
        "active_folder": working_dir,
        "working_dir": working_dir,
        "file_count": file_count
    })