# Role: GPS data processing module (see Stability Contract)

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

def extract_gps_points(records):
    points = []

    for record in records:
        gps = record.get("gps")

        print("🔎 RECORD GPS:", gps)  # ✅ keep debug

        if not gps:
            continue

        lat = gps.get("lat")
        lon = gps.get("lon")

        # ✅ FIX: explicit None check (NOT truthy check)
        if lat is None or lon is None:
            continue

        points.append({
            "lat": lat,
            "lon": lon,
            "path": record.get("path")
        })

    print("✅ TOTAL GPS POINTS:", len(points))  # ✅ debug

    return points