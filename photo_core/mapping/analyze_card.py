# Mapping: card structure analysis
# Read-only analysis
# Informational outputs only

import os
from utils.fs_utils import iter_jpegs, iter_raws, list_candidate_folders
from photo_core.mapping.exif_dates import (
    extract_camera_model,
    extract_lens_model,
)

def analyze_card(sd_root):
    """
    Analyze folder structure and basic camera/lens signals for an SD card.

    Returns:
        {
            "folders": [
                {
                    "name": str,
                    "path": str,
                    "photo_count": int,
                    "camera_model": str,
                    "lens": str,
                    "raw_only": bool
                },
                ...
            ]
        }
    """
    folders = []

    for folder in list_candidate_folders(sd_root):

        # 1) SAMPLE JPEGs FIRST
        samples = list(iter_jpegs(folder))[:30]

        # 2) RAW fallback
        raw_only = False
        if not samples:
            raw_files = list(iter_raws(folder))
            if not raw_files:
                continue
            raw_only = True
            jpeg_count = 0
            raw_count = len(raw_files)
        else:
            jpeg_count = sum(1 for _ in iter_jpegs(folder))
            raw_count = sum(1 for _ in iter_raws(folder))

        # 3) Camera / lens extraction
        if raw_only:
            model = "RAW-only"
            lens = "Unknown Lens"
        else:
            model = "Unknown"
            lens = "Unknown Lens"

            for img in samples:
                model = extract_camera_model(img) or model
                lens = extract_lens_model(img) or lens
                if model != "Unknown" and lens != "Unknown Lens":
                    break

        folders.append({
            "name": os.path.basename(folder),
            "path": folder,
            "photo_count": jpeg_count + raw_count,
            "camera_model": model,
            "lens": lens,
            "raw_only": raw_only
        })

    return {"folders": folders}