# Role: GPS helpers (not used by the route) (see Stability Contract)

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


def get_base_name(path):
    if not path:
        return None
    return os.path.splitext(os.path.basename(path))[0]


def extract_gps_points(records, mode="logical"):
    points = []
    gps_by_base = {}

    # ✅ STEP 1: build GPS from EXIF records
    for _i, r in enumerate(records):
        try:
            source = r.get("path")
            if not source:
                continue

            base = get_base_name(source)

            gps = r.get("gps")

            if not gps:
                continue

            try:
                lat, lon = gps  # ✅ already final, do NOT transform

            except Exception:
                continue

            gps_by_base[base] = (lat, lon)
            gps_by_base[base] = gps

        except Exception:
            continue

    # ✅ STEP 2: logical mode (1 point per image base)
    if mode == "logical":
        for base, gps in gps_by_base.items():
            lat, lon = gps

            points.append({"path": base, "lat": lat, "lon": lon, "quality": "exif"})

        return points

    # ✅ STEP 3: all files mode (preserve display paths)
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

                points.append(
                    {"path": display, "lat": lat, "lon": lon, "quality": "exif"}
                )

            except Exception:
                continue

    return points
