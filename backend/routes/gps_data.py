# backend/routes/gps_data.py
# HTTP API wrapper for GPS data

from flask import jsonify
from photo_core.mapping.gps_data import classify_gps_quality


def api_gps_data(ctx):
    """
    Return GPS point quality for the currently active folder
    using cached EXIF data only.
    """
    active = ctx.state.get("current_active_folder")
    if not active:
        return jsonify({"ready": False, "points": []})

    exif_key = f"exif::{active}"
    exif_records = ctx.exif_cache.get(exif_key)
    if not exif_records:
        return jsonify({"ready": False, "points": []})

    points = []

    for record in exif_records:
        quality = classify_gps_quality(record)
        if quality != "none":
            points.append({
                "lat": record.get("GPSLatitude"),
                "lon": record.get("GPSLongitude"),
                "quality": quality,
            })

    return jsonify({
        "ready": True,
        "points": points,
    })