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

# ✅ Optional debug toggle (leave False for normal use)
DEBUG = False


def api_gps_data(ctx):
    """
    Return GPS points derived from EXIF data.

    Behaviour:
    - Silent while EXIF worker is still running
    - Returns [] until data is ready
    - Logs a single meaningful message when GPS data is available
    """

    # ✅ Use worker output
    records = getattr(ctx, "exif_records", [])

    # ✅ Silent while waiting (no log spam during polling)
    if not records:
        if DEBUG:
            print("⏳ GPS request: no EXIF records yet")
        return jsonify([])

    # ✅ Extract GPS points
    points = extract_gps_points(records)

    # ✅ Optional debug detail
    if DEBUG:
        print(f"📦 RECORD COUNT: {len(records)}")
        print(f"📍 POINTS RETURNED: {len(points)}")

    # ✅ Clean, meaningful runtime log (always shown)
    if not points:
        print("⚠️ No GPS data found")
    else:
        print(f"✅ GPS extraction complete: {len(points)} points")

    return jsonify(points)