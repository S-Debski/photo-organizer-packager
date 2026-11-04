# Role: GPS data API route (see Stability Contract)

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
#       → ctx.state.get("exif_records", [])
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

logger = logging.getLogger("gps")


def api_gps_data(ctx):

    data = request.json or {}
    data.get("manualGPS", [])

    records = ctx.state.get("exif_records", [])
    exif_ready = bool(records)

    active = ctx.state.get("current_active_folder")

    if ctx.state.get("current_active_folder") and records:
        logger.info(f"[API CTX ID] {id(ctx)}")

    # ✅ ✅ ✅ Clean logging (only when data changes)
    last_count = ctx.state.get("_last_exif_count")
    current_count = len(records)

    if active and current_count != last_count and current_count > 0:
        logger.info(f"✅ EXIF records: {current_count}")
        logger.info(f"✅ GPS combined: {current_count} points")

        ctx.state["_last_exif_count"] = current_count

    # ✅ No EXIF data yet → normal startup / before analyse
    if not records:
        return jsonify({"points": [], "exif_ready": False})

    # ✅ ✅ ✅ Build GPS points
    points = []

    for r in records:
        gps = r.get("gps")

        if not gps or len(gps) < 2:
            continue

        lat, lon = gps

        if lat is None or lon is None:
            continue

        points.append(
            {"path": r.get("path"), "lat": lat, "lon": lon, "quality": "exif"}
        )

    # ✅ pipeline info (used by frontend)
    working_files = ctx.state.get("working_files", [])
    file_count = len(working_files)
    exif_count = len(records)

    return jsonify(
        {
            "points": points,
            "exif_ready": exif_ready,
            "current_active_folder": active,
            # ✅ pipeline status
            "copy_complete": ctx.state.get("copy_complete", False),
            "file_count": file_count,
            "exif_count": exif_count,
        }
    )
