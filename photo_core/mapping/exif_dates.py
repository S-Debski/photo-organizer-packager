# Mapping: EXIF date and camera metadata
# Read-only analysis
# No filesystem mutation
# Informational outputs only

from PIL import Image, ExifTags

TAGS = {v: k for k, v in ExifTags.TAGS.items()}
IMAGE_EXTS = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}

def _rational_to_float(x):
    try:
        return float(x[0]) / float(x[1]) if isinstance(x, tuple) else float(x)
    except Exception:
        return None

def extract_exif_datetime(path):
    """
    Returns a datetime string or None.
    Informational only.
    """
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                return None

            dt = (
                exif.get(TAGS.get("DateTimeOriginal")) or
                exif.get(TAGS.get("DateTimeDigitized")) or
                exif.get(TAGS.get("DateTime"))
            )
            return dt
    except Exception:
        return None
