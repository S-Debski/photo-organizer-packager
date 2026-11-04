# Role: Active folder selection API route (see Stability Contract)

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


import os
import subprocess
import logging

from flask import jsonify

import backend.api_server as api_server

from backend.utils.logging_utils import backend_log

from utils.fs_utils import get_default_working_base, iter_jpegs

logger = logging.getLogger("set_active_folder")


# -----------------------------------------------------------------------------
# COPY OPERATION
# -----------------------------------------------------------------------------
def copy_to_working(src_folder, dst_folder):

    os.makedirs(dst_folder, exist_ok=True)

    cmd = [
        "robocopy",
        src_folder,
        dst_folder,
        "/E",
        "/R:0",
        "/W:0",
        "/NFL",
        "/NDL",
        "/NP",
        "/NJH",
        "/NJS",
        "/MT:16",
    ]

    print("RUNNING:", cmd)

    result = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("✅ ROBOCOPY FINISHED")

    return result


# -----------------------------------------------------------------------------
# MAIN ENTRY POINT
# -----------------------------------------------------------------------------
def api_set_active_folder(payload):
    """
    Initialise a new processing session.

    Pipeline (v3.0 hybrid ingest — source is browsed in place):
        1. Validate input folder
        2. Resolve base working directory (no per-click folder created)
        3. Compute file count from source
        4. Clear EXIF + thumbnail caches
        5. Set active folder to the source folder
        6. Release EXIF worker to scan it

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
        RoboCopy completes
        caches cleared
        current_active_folder → working_dir
        copy_complete = True → worker scans copied files

    Important:
        • Original source files are NEVER modified
        • All downstream processing uses working_dir
        • GPS metadata updates target copied files only

        Order matters:
            copy → cache clear → active folder switch → copy_complete = True
    """

    # -------------------------------------------------------------------------
    # ✅ STATE: mark pipeline not ready
    # -------------------------------------------------------------------------
    api_server.ctx.state["copy_complete"] = False

    folder = payload.get("folder")
    working_dir_input = payload.get("working_dir")

    backend_log(f"📂 Set active folder requested: {folder}")

    # -------------------------------------------------------------------------
    # ✅ Validate input
    # -------------------------------------------------------------------------
    if not folder or not os.path.isdir(folder):
        logger.error(f"Invalid folder: {folder}")

        return jsonify({"success": False, "error": "Invalid folder"}), 400

    # -------------------------------------------------------------------------
    # STEP 1 — resolve base working directory
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
    # STEP 2–4 — v3.0 hybrid ingest: browse the source in place.
    # Nothing is copied here (and no per-click working folder is created);
    # /api/organize copies the kept files after culling. copy_to_working()
    # is kept for a possible "copy whole card first" option.
    # -------------------------------------------------------------------------
    session_name = os.path.basename(folder.rstrip("\\/"))
    working_dir = base_dir

    print("✅ SOURCE FOLDER:", folder)

    # -------------------------------------------------------------------------
    # STEP 5 — compute file count (source JPEGs)
    # -------------------------------------------------------------------------
    working_files = list(iter_jpegs(folder))

    file_count = len(working_files)

    api_server.ctx.state["working_files"] = working_files
    # -------------------------------------------------------------------------
    # STEP 6 — clear caches
    # -------------------------------------------------------------------------
    api_server.ctx.exif_cache.clear()
    api_server.ctx.thumb_cache.clear()

    print("🧹 EXIF cache cleared → worker must rescan")

    # -------------------------------------------------------------------------
    # STEP 7 — switch pipeline to copied files
    # -------------------------------------------------------------------------

    print("✅ ACTIVE WORKING FOLDER:", working_dir)

    # -------------------------------------------------------------------------
    # STEP 8 — final context update
    # -------------------------------------------------------------------------
    api_server.ctx.working_dir = working_dir
    api_server.ctx.session_id = session_name

    # ✅ release EXIF worker
    api_server.ctx.state["copy_complete"] = True
    # Drop the previous folder's records so the map/stats don't show them
    # while the scanner reads this one (exif_ready goes false until then)
    if api_server.ctx.state.get("current_active_folder") != folder:
        api_server.ctx.state["exif_records"] = []
    api_server.ctx.state["current_active_folder"] = folder

    # -------------------------------------------------------------------------
    # RETURN
    # -------------------------------------------------------------------------
    return jsonify(
        {
            "success": True,
            "active_folder": working_dir,
            "working_dir": working_dir,
            "file_count": file_count,
        }
    )
