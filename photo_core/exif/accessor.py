# Role: Application module (see Stability Contract)

# photo_core/exif/accessor.py
# ------------------------------------------------------------
# Unified Accessor for exif data
# ------------------------------------------------------------


from datetime import datetime


def get_exif_value(record, *keys):
    """
    Try multiple EXIF keys and return the first valid value.
    """
    for key in keys:
        val = record.get(key)
        if val:
            return val
    return None


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def has_gps(record):
    return get_gps(record) is not None


def get_datetime(record):
    raw = get_exif_value(
        record,
        "EXIF:DateTimeOriginal",
        "EXIF:CreateDate",
        "QuickTime:CreateDate",
        "File:FileModifyDate",
    )

    if not raw:
        return None

    raw = raw.strip()

    try:
        return datetime.strptime(raw[:19], "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def get_gps(record):
    lat = get_exif_value(record, "EXIF:GPSLatitude")
    lon = get_exif_value(record, "EXIF:GPSLongitude")

    if not lat or not lon:
        return None

    return {
        "lat": _safe_float(lat),
        "lon": _safe_float(lon),
        "alt": record.get("EXIF:GPSAltitude"),
        "source": "exif",
    }


def get_camera(record):
    make = record.get("EXIF:Make")
    model = record.get("EXIF:Model")

    if make and model:
        return f"{make} {model}"

    return model or make


def get_lens(record):
    return get_exif_value(
        record,
        "EXIF:LensModel",
        "EXIF:LensInfo",
    )


def get_iso(record):
    iso = record.get("EXIF:ISO")
    try:
        return int(iso) if iso else None
    except ValueError:
        return None


def normalize_exif(record):
    dt = get_datetime(record)

    return {
        "datetime": dt.isoformat() if dt else None,
        "gps": get_gps(record),
        "camera": get_camera(record),
        "lens": get_lens(record),
        "iso": get_iso(record),
    }
