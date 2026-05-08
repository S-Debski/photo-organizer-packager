# Role: Application module

# backend/routes/gps_data.py
# HTTP API wrapper for GPS data

from flask import jsonify
import os

from utils.fs_utils import iter_jpegs

# ✅ IMPORTANT: use the real EXIF reader your project uses
from photo_core.exif.reader import read_exif

def api_gps_data(ctx, path=None):
    """
    Return GPS point data for the selected folder.

    Uses raw EXIF records (not aggregated stats).
    Falls back to loading EXIF if cache is missing.
    """

    # ✅ Folder fallback location
    folder_location = ctx.state.get("folder_location")

    # --------------------------------------------------
    # Resolve root folder
    # --------------------------------------------------
    root = (
        path
        or ctx.state.get("current_active_folder")
        or ctx.state.get("current_sd_root")
    )

    if not root or not os.path.isdir(root):
        return jsonify({"ready": False, "points": []})

    # --------------------------------------------------
    # RAW EXIF cache (separate from stats cache)
    # --------------------------------------------------
    exif_key = f"exif_raw::{os.path.abspath(root)}"
    exif_records = ctx.exif_cache.get(exif_key)

    # --------------------------------------------------
    # Fallback: load EXIF if not cached
    # --------------------------------------------------
    if not exif_records:
        from pathlib import Path

        # ✅ Build RAW and JPEG lists separately
        raw_files = [
            str(p) for p in Path(root).rglob("*")
            if p.suffix.lower() == ".raf"
        ]

        jpeg_files = [
            str(p) for p in Path(root).rglob("*")
            if p.suffix.lower() in [".jpg", ".jpeg"]
        ]

        # ✅ Prefer RAW, fallback to JPEG
        image_paths = raw_files if raw_files else jpeg_files

        print(f"🔍 Loading EXIF for {len(image_paths)} files (RAW preferred)")

        exif_records = []
        for p in image_paths:
            rec = read_exif(p)
            if rec:
                exif_records.append(rec)

        # ✅ Cache raw EXIF
        ctx.exif_cache[exif_key] = exif_records

    # --------------------------------------------------
    # Extract GPS points
    # --------------------------------------------------
    points = []

    for i, record in enumerate(exif_records):

        # ✅ Only print once (no break!)
        if i == 0:
            print("RECORD KEYS:", list(record.keys()))
            print("GPS KEYS:", [k for k in record.keys() if "GPS" in k])

        lat = (
                record.get("GPSLatitude")
                or record.get("Composite:GPSLatitude")
        )

        lon = (
                record.get("GPSLongitude")
                or record.get("Composite:GPSLongitude")
        )

        # ✅ Optional: show first few GPS values only
        if i < 3:
            print("GPS RAW:", lat, lon)

        # ✅ Append valid points
        if lat is None or lon is None:
            # ✅ fallback to folder location
            if folder_location:
                lat, lon = folder_location

        if lat is not None and lon is not None:
            points.append({
                "lat": lat,
                "lon": lon,
                "quality": "fallback" if folder_location else "unknown"
            })
            points.append({
                "lat": lat,
                "lon": lon,
                "quality": "unknown"
            })

    # --------------------------------------------------
    # Return result
    # --------------------------------------------------
    return jsonify({
        "ready": True,
        "points": points,
        "gps_count": len(points),
        "total_images": len(exif_records)
    })
