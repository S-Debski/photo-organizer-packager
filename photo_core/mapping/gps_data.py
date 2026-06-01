# =============================================================================
# File: photo_core/mapping/gps_data.py
#
# Role:
# GPS mapping layer – converts EXIF records into usable map points.
#
# Responsibilities:
# - Extract GPS coordinates from original image files (via reader.get_exif_gps)
# - Support multiple output modes:
#     • "logical" → one GPS point per logical image (JPG/RAW pair collapsed)
#     • "all"     → GPS applied to all files (RAW + JPG + duplicates)
# - Handle pairing by grouping files using base filename
# - Preserve frontend-friendly paths for rendering
#
# Data Flow:
# EXIF Scanner → ctx.exif_records
#              → extract_gps_points(records, mode)
#              → list of GPS point dicts
#
# Output Format:
# [
#     {
#         "path": "...",
#         "lat": float,
#         "lon": float,
#         "quality": "exif"
#     }
# ]
#
# Notes:
# - Uses original file paths (SourceFile) for reliable EXIF access
# - Avoids repeated EXIF reads by caching GPS per base filename
# - Designed for use by backend/routes/gps_data.py
# =============================================================================
import os


def classify_gps_quality(record):
    gps = record.get("gps")

    if not gps:
        return "none"

    lat = gps.get("lat")
    lon = gps.get("lon")

    if lat is None or lon is None:
        return "none"

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return "coarse"

    if gps.get("alt") is None:
        return "basic"

    return "precise"


# =============================================================================
# File: photo_core/mapping/gps_data.py
# Extract usable GPS points for mapping
# =============================================================================

from photo_core.exif.reader import get_exif_gps
import os


def get_base_name(path):
    if not path:
        return None
    return os.path.splitext(os.path.basename(path))[0]


def extract_gps_points(records, mode="logical"):
    points = []

    gps_by_base = {}

    # ✅ STEP 1: build GPS using ORIGINAL files and EXIFTOOL data (NOT PIL)
    for i, r in enumerate(records):
        try:
            # ✅ DEBUG — only print for first record
            if i == 0:
                print("DEBUG KEYS:", list(r.keys()))

            source = r.get("path")

            if not source:
                continue

            base = get_base_name(source)

            gps_data = r.get("gps") or {}

            lat = gps_data.get("lat")
            lon = gps_data.get("lon")

            if i < 5:
                print("API GPS:", gps_data)

                if lat is not None and lon is not None:
                    gps = (float(lat), float(lon))
                else:
                    gps = None

                if gps is not None:
                    gps_by_base[base] = gps

        except Exception:
            continue

    # ✅ STEP 2: logical mode (1 point per image)
    if mode == "logical":
        for base, gps in gps_by_base.items():
            lat, lon = gps

            points.append({
                "path": base,
                "lat": lat,
                "lon": lon,
                "quality": "exif"
            })

        return points

    # ✅ STEP 3: all files mode
    if mode == "all":
        for r in records:
            try:
                source = r.get("SourceFile")
                display = r.get("path") or source

                base = get_base_name(source)

                gps = gps_by_base.get(base)

                if not gps:
                    continue

                lat, lon = gps

                points.append({
                    "path": display,
                    "lat": lat,
                    "lon": lon,
                    "quality": "exif"
                })

            except Exception:
                continue

    return points
