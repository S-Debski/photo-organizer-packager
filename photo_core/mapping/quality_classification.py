# =============================================================================
# File: photo_core/mapping/quality_classification.py
#
# Role:
#   Application module (read-only mapping layer)
#
# Responsibilities:
#   - Extract EXIF GPS data using read_exif()
#   - Convert DMS / decimal formats into float coordinates
#   - Provide normalized GPS structure for mapping
#
# Notes:
#   - No filesystem writes
#   - Used by exif_scanner worker
# =============================================================================

from photo_core.exif.reader import read_exif

# =============================================================================
# Helper: Convert EXIF GPS to decimal
# =============================================================================
def dms_to_decimal(value):
    # ✅ Already numeric
    if isinstance(value, (int, float)):
        return float(value)

    try:
        value = str(value).strip()

        # ✅ Case 1: decimal string ("52.1072")
        if value.replace(".", "", 1).isdigit():
            return float(value)

        # ✅ Case 2: DMS format ("52 deg 6' 25.92\" N")
        parts = value.replace("deg", "").replace("'", "").replace('"', '').split()

        if len(parts) < 3:
            print("❌ Unexpected GPS format:", value)
            return None

        deg = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])

        decimal = deg + (minutes / 60) + (seconds / 3600)

        # ✅ Handle direction
        if parts[-1] in ("S", "W"):
            decimal = -decimal

        return decimal

    except Exception as e:
        print("❌ DMS conversion error:", e, "| value:", value)
        return None


# =============================================================================
# Extract GPS from EXIF
# =============================================================================
def extract_exif_gps(path):
    try:
        record = read_exif(path)

        # ✅ Try multiple EXIF sources
        lat = (
            record.get("EXIF:GPSLatitude")
            or record.get("Composite:GPSLatitude")
        )

        lon = (
            record.get("EXIF:GPSLongitude")
            or record.get("Composite:GPSLongitude")
        )

        if not lat or not lon:
            return None

        lat = dms_to_decimal(lat)
        lon = dms_to_decimal(lon)

        if lat is None or lon is None:
            return None

        return {
            "lat": lat,
            "lon": lon
        }

    except Exception as e:
        print("❌ GPS extraction error:", e)
        return None