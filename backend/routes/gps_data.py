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


from flask import jsonify
from photo_core.mapping.gps_data import extract_gps_points
from flask import jsonify, request

# ✅ Optional debug toggle (leave False for normal use)
DEBUG = False


def api_gps_data(ctx):
    """
    Return GPS points derived from EXIF data + manual mapping.
    """

    # ✅ Read request body (new)
    data = request.json or {}
    manual = data.get("manualGPS", [])

    # ✅ Existing EXIF logic
    records = getattr(ctx, "exif_records", [])

    if not records:
        if DEBUG:
            print("⏳ GPS request: no EXIF records yet")
        exif_points = []
    else:
        exif_points = extract_gps_points(records)

    # ✅ Convert EXIF to standard format
    points = [
        {
            "lat": p.get("lat"),
            "lon": p.get("lon"),
            "quality": p.get("quality", "exif")
        }
        for p in exif_points
    ]

    # ✅ NEW: merge manual GPS
    for m in manual:
        if m.get("lat") and m.get("lon"):
            points.append({
                "lat": m.get("lat"),
                "lon": m.get("lon"),
                "quality": "manual",
                "filename": m.get("path")
            })

    # ✅ Logging
    if not points:
        print("⚠️ No GPS data found")
    else:
        print(f"✅ GPS combined: {len(points)} points")

    return jsonify(points)