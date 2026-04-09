# backend/routes/analyze_card.py
import os
from flask import jsonify

from utils.fs_utils import iter_jpegs, iter_raws, list_candidate_folders
from utils.exif_utils import extract_exif
from utils.logging_bus import log_info


def api_analyze_card(ctx, payload):
    sd_root = payload.get("sd_card_path")
    if not sd_root or not os.path.isdir(sd_root):
        return jsonify({"success": False, "error": "Invalid sd_card_path"}), 400

    ctx.state["current_sd_root"] = sd_root
    ctx.state["current_active_folder"] = sd_root
    ctx.thumb_cache.clear()
    ctx.exif_cache.clear()

    folders = []

    log_info(ctx, f"Analyze start: {sd_root}")

    for folder in list_candidate_folders(sd_root):

        log_info(ctx, f"Scanning folder: {folder}")

        # 1) SAMPLE JPEGs FIRST
        samples = list(iter_jpegs(folder))[:30]

        # 2) RAW‑fallback if no JPEG available
        raw_only = False
        if not samples:
            raw_files = list(iter_raws(folder))
            if raw_files:
                raw_only = True
                jpeg_count = 0
                raw_count = len(raw_files)
            else:
                # Empty folder
                continue
        else:
            jpeg_count = sum(1 for _ in iter_jpegs(folder))
            raw_count = sum(1 for _ in iter_raws(folder))

        # 3) EXIF extraction (JPEGs only)
        if raw_only:
            model = "RAW-only"
            lens = "Unknown Lens"
        else:
            model = "Unknown"
            lens = "Unknown Lens"

            for img in samples:
                ex = extract_exif(img)
                if ex.get("model"):
                    model = ex["model"]
                if ex.get("lens"):
                    lens = ex["lens"]
                if model != "Unknown" and lens != "Unknown Lens":
                    break

        # 4) Build folder entry
        folders.append({
            "name": os.path.basename(folder),
            "path": folder,
            "photo_count": jpeg_count + raw_count,
            "camera_model": model,
            "lens": lens,
            "raw_only": raw_only
        })

    log_info(ctx, f"Analyze complete: {len(folders)} folders")

    return jsonify({"success": True, "analysis": {"folders": folders}})
