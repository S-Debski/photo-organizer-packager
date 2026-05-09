# Role: Application module (see Stability Contract)

# backend/routes/organize.py
import os
import shutil
import subprocess
from flask import jsonify

from utils.fs_utils import iter_jpegs, iter_raws
from utils.logging_bus import log_info


def api_organize(ctx):
    """
    Start an organize/import job.
    RAW + JPEG supported.
    """
    src = ctx.state.get("current_active_folder")
    if not src or not os.path.isdir(src):
        return jsonify({"success": False, "error": "No active folder"}), 400

    pictures = ctx.output_dir

    if not pictures:
        return jsonify({
            "success": False,
            "error": "Output directory is not configured"
        }), 400

    os.makedirs(pictures, exist_ok=True)

    # Initialize job state
    ctx.state["organize_job"] = {
        "total": 0,
        "done": 0,
        "errors": 0,
        "running": True
    }

    job = ctx.state["organize_job"]

    # Collect files (JPEG first, then RAW)
    jpeg_files = list(iter_jpegs(src))
    raw_files = list(iter_raws(src))
    files = jpeg_files + raw_files

    job["total"] = len(files)

    log_info(ctx, f"Organizing {job['total']} files from {src}")

    for f in files:
        try:
            dst = os.path.join(pictures, os.path.basename(f))
            shutil.copy2(f, dst)
        except Exception as e:
            job["errors"] += 1
            log_info(ctx, f"Copy error: {e}")

        job["done"] += 1

    job["running"] = False
    log_info(ctx, "Organize complete.")

    return jsonify({"success": True})


def api_job_status(ctx):
    """
    Return progress info for the ongoing job.
    """
    job = ctx.state.get("organize_job")
    if not job:
        return jsonify({"running": False, "done": 0, "total": 0})

    return jsonify(job)


def api_open_pictures(ctx):
    """
    Open the output folder in Windows Explorer.
    """
    folder = ctx.output_dir

    if not folder:
        return jsonify({
            "success": False,
            "error": "Output directory not configured"
        }), 400

    try:
        os.makedirs(folder, exist_ok=True)
        subprocess.Popen(['explorer', os.path.abspath(folder)])
    except Exception as e:
        log_info(ctx, f"Open Pictures error: {e}")
        return jsonify({"success": False}), 500

    return jsonify({"success": True})
