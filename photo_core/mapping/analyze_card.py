# Role: SD card analysis engine (see Stability Contract)

# Mapping: card structure analysis
# Read-only analysis
# Informational outputs only

import os
from utils.fs_utils import iter_jpegs, iter_raws, list_candidate_folders
from photo_core.exif.reader import prefetch_exif
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

    dcim_root = os.path.join(sd_root, "DCIM")

    for folder in list_candidate_folders(sd_root):

        # Walk the folder once (it was walked five times per folder before)
        raw_files = list(iter_raws(folder))
        jpeg_files = list(iter_jpegs(folder))
        jpeg_count = len(jpeg_files)
        raw_count = len(raw_files)

        if not raw_files and not jpeg_files:
            continue

        # 1) Samples for camera/lens: RAW first, else JPEG
        samples = raw_files[:30] or jpeg_files[:30]
        raw_only = False

        # One batched exiftool run instead of one per sample
        prefetch_exif(samples)

        # 3) Camera / lens extraction
        if raw_only:
            model = "RAW-only"
            lens = None
        else:
            model = None
            lens = None

            for img in samples:
                model = extract_camera_model(img) or model
                lens = extract_lens_model(img) or lens

                # ✅ Stop early only if BOTH found
                if model and lens:
                    break

            # ✅ Fallback AFTER loop
            model = model or "Camera not resolved - no camera EXIF"
            lens = lens or "Unknown Lens"

        # JPEG preferred for the folder's sample thumbnail
        sample = jpeg_files[0] if jpeg_files else (raw_files[0] if raw_files else None)

        # Build display name relative to DCIM to handle collisions:
        # DCIM/929_FUJI/Medburn → "929_FUJI/Medburn"
        # DCIM/105_PANA         → "105_PANA"
        rel = os.path.relpath(folder, dcim_root) if os.path.isdir(dcim_root) else os.path.basename(folder)
        display_name = rel.replace(os.sep, "/")

        folders.append({
            "name": display_name,
            "path": folder,
            "photo_count": jpeg_count + raw_count,
            "jpeg_count": jpeg_count,
            "raw_count": raw_count,
            "camera_model": model,
            "lens": lens,
            "raw_only": raw_only,
            "sample": sample,  # ✅ ALWAYS a single string or None
        })

    # Outside the loop: a card with no image folders must report zeros,
    # not raise UnboundLocalError.
    total_raw = sum(f["raw_count"] for f in folders)
    total_jpg = sum(f["jpeg_count"] for f in folders)
    total_images = sum(f["photo_count"] for f in folders)

    return {
        "folders": folders,
        "counts": {
            "total": total_images,
            "raw": total_raw,
            "jpg": total_jpg
        }
    }
