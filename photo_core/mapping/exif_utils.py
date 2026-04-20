# utils/exif_utils.py
from PIL import Image, ExifTags

TAGS = {v: k for k, v in ExifTags.TAGS.items()}
GPSTAGS = ExifTags.GPSTAGS

IMAGE_EXTS = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}  # png rarely has exif but harmless

def _rational_to_float(x):
    # x may be (num, den) tuple or PIL Rational
    try:
        return float(x[0]) / float(x[1]) if isinstance(x, tuple) else float(x)
    except Exception:
        return None

def _dms_to_deg(dms):
    # dms like [(deg_num,deg_den),(min_num,min_den),(sec_num,sec_den)] or PIL rationals
    deg = _rational_to_float(dms[0])
    minutes = _rational_to_float(dms[1])
    seconds = _rational_to_float(dms[2])
    if deg is None or minutes is None or seconds is None:
        return None
    return deg + (minutes / 60.0) + (seconds / 3600.0)

def extract_exif(path):
    """
    Returns dict: {
      make, model, lens, datetime, gps: {lat, lon, alt}
    }
    """
    out = {"make": None, "model": None, "lens": None, "datetime": None, "gps": None}
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                return out

            make = exif.get(TAGS.get("Make"))
            model = exif.get(TAGS.get("Model"))
            lens = exif.get(TAGS.get("LensModel")) or exif.get(TAGS.get("LensMake"))
            dt = exif.get(TAGS.get("DateTimeOriginal")) or exif.get(TAGS.get("DateTime"))

            out["make"] = make.strip() if isinstance(make, str) else make
            out["model"] = model.strip() if isinstance(model, str) else model
            out["lens"] = lens.strip() if isinstance(lens, str) else lens
            out["datetime"] = dt

            gps_info = exif.get(TAGS.get("GPSInfo"))
            if gps_info:
                gps = {}
                # gps_info keys are numeric: map to names
                for k, v in gps_info.items():
                    name = GPSTAGS.get(k, k)
                    gps[name] = v

                lat = None
                lon = None
                alt = None

                if "GPSLatitude" in gps and "GPSLatitudeRef" in gps:
                    lat = _dms_to_deg(gps["GPSLatitude"])
                    if lat is not None and gps["GPSLatitudeRef"] in ("S", "s"):
                        lat = -lat

                if "GPSLongitude" in gps and "GPSLongitudeRef" in gps:
                    lon = _dms_to_deg(gps["GPSLongitude"])
                    if lon is not None and gps["GPSLongitudeRef"] in ("W", "w"):
                        lon = -lon

                if "GPSAltitude" in gps:
                    alt = _rational_to_float(gps["GPSAltitude"])

                if lat is not None and lon is not None:
                    out["gps"] = {"lat": lat, "lon": lon, "alt": alt}

    except Exception:
        # keep silent; caller can log if needed
        return out

    return out