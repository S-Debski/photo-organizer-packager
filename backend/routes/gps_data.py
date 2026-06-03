# =============================================================================
# File: backend/routes/gps_data.py
#
# Role:
#   API route for returning GPS coordinates for mapping (Step 5).
#
# Responsibilities:
#   - Access EXIF records produced by the background EXIF scanner
#   - Extract usable GPS points via mapping layer
#   - Merge manual GPS points provided by frontend
#   - Return unified GPS dataset for Leaflet map rendering
#
# Data Flow:
#   EXIF Scanner Worker
#       → ctx.exif_records
#       → extract_gps_points(records)
#       → EXIF GPS points
#
#   Frontend (manual mapping)
#       → metadataMap (lat/lon assigned via UI)
#       → POST /api/gps-data (manualGPS[])
#
#   API Route
#       → merge EXIF + manual GPS
#       → JSON response → frontend
#
# Input (POST JSON):
#   {
#       "folder": "F:\\DCIM\\...",
#       "manualGPS": [
#           {
#               "path": "...",
#               "lat": ...,
#               "lon": ...
#           }
#       ]
#   }
#
# Output (JSON):
#   [
#       {
#           "lat": float,
#           "lon": float,
#           "quality": "exif" | "manual",
#           "filename": "... (optional)"
#       }
#   ]
#
# Notes:
#   - EXIF GPS is read-only from worker cache
#   - Manual GPS is injected from frontend (not persisted yet)
#   - Silent while EXIF scan is in progress
#   - Mapping supports mixed precision (EXIF + manual)
#
# Used By:
#   - /api/gps-data endpoint
#   - Frontend mapping view (Step 5)
#
# =============================================================================
# =============================================================================
# File: backend/routes/gps_data.py
# =============================================================================

import logging
from flask import jsonify, request

from photo_core.mapping.gps_data import extract_gps_points

logger = logging.getLogger("gps")


def api_gps_data(ctx):

    data = request.json or {}
    manual = data.get("manualGPS", [])

    records = getattr(ctx, "exif_records", [])
    exif_ready = bool(records)

    logger.info(f"[API CTX ID] {id(ctx)}")
    logger.info(f"EXIF records count: {len(records)}")

    if not records:
        # EXIF still loading — normal during startup
        return jsonify({
            "points": [],
            "exif_ready": False
        })

    # ✅ ✅ Build GPS points
    points = []

    for r in records:
        gps = r.get("gps")

        if gps is None:
            continue

        try:
            lat, lon = gps
        except Exception:
            continue

        if lat is None or lon is None:
            continue

        points.append({
            "path": r.get("path"),
            "lat": lat,
            "lon": lon,
            "quality": "exif"
        })

    logger.info(f"✅ GPS combined: {len(points)} points")

    working_files = ctx.state.get("working_files", [])
    file_count = len(working_files)
    exif_count = len(ctx.exif_records)

    return jsonify({
        # existing data
        "points": points,
        "exif_ready": exif_ready,
        "current_active_folder": ctx.state.get("current_active_folder"),

        # ✅ NEW: pipeline status
        "copy_complete": ctx.state.get("copy_complete", False),
        "file_count": file_count,
        "exif_count": exif_count
    })
