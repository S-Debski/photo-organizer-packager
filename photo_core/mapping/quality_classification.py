# Role: Application module

# Mapping: GPS and quality signals
# Read-only analysis
# No filesystem mutation

from PIL import Image, ExifTags

GPSTAGS = ExifTags.GPSTAGS

def _rational_to_float(x):
    try:
        return float(x[0]) / float(x[1]) if isinstance(x, tuple) else float(x)
    except Exception:
        return None

def _dms_to_deg(dms):
    deg = _rational_to_float(dms[0])
    minutes = _rational_to_float(dms[1])
    seconds = _rational_to_float(dms[2])
    if deg is None or minutes is None or seconds is None:
        return None
    return deg + (minutes / 60.0) + (seconds / 3600.0)

def extract_exif_gps(path):
    """
    Returns { lat, lon, alt } or None.
    Informational only.
    """
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                return None

            gps_info = exif.get(34853)  # GPSInfo
            if not gps_info:
                return None

            gps = {}
            for key, val in gps_info.items():
                name = GPSTAGS.get(key, key)
                gps[name] = val

            lat = _dms_to_deg(gps.get("GPSLatitude", []))
            lon = _dms_to_deg(gps.get("GPSLongitude", []))
            alt = _rational_to_float(gps.get("GPSAltitude"))

            return {"lat": lat, "lon": lon, "alt": alt}
    except Exception:
        return None

