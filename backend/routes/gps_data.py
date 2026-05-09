# =============================================================================
# File: backend/routes/gps_data.py
#
# Role:
#   API route for returning GPS coordinates derived from EXIF data
#
# Responsibilities:
#   - Access EXIF records produced by the background EXIF scanner worker
#   - Extract usable GPS points via the mapping layer
#   - Return GPS data as JSON for frontend (Leaflet map)
#
# Data Flow:
#   EXIF Scanner Worker
#       → ctx.exif_records
#       → extract_gps_points(records)
#       → JSON response to frontend
#
# Notes:
#   - Read-only: does not access filesystem directly
#   - Depends on worker having populated ctx.exif_records
#   - Uses mapping logic in photo_core/mapping/gps_data.py
#
# Used By:
#   - /api/gps-data endpoint
#   - Frontend mapping view (Step 5)
#
# =============================================================================

from flask import jsonify
from photo_core.mapping.gps_data import extract_gps_points


def api_gps_data(ctx):

    # ✅ CRITICAL FIX: use worker output
    records = getattr(ctx, "exif_records", [])

    print("📦 RECORD COUNT:", len(records))  # debug

    if not records:
        print("⚠️ No EXIF records available yet")
        return jsonify([])

    points = extract_gps_points(records)

    print("📍 POINTS RETURNED:", len(points))  # debug

    return jsonify(points)