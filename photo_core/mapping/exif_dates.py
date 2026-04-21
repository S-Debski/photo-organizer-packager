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
def extract_camera_model(path):
    """
    Returns a camera model string, or None.
    Informational only.
    """
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                return None

            make = exif.get(TAGS.get("Make"))
            model = exif.get(TAGS.get("Model"))

            if make and model:
                return f"{str(make).strip()} {str(model).strip()}"

            return str(model).strip() if model else str(make).strip() if make else None
    except Exception:
        return None

def extract_lens_model(path):
    """
    Returns a human-readable lens name if available, otherwise None.
    Informational only.
    """
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            if not exif:
                return None

            # Try common EXIF fields in order of usefulness
            for tag in (
                "LensModel",
                "Lens",
                "LensSpecification",
                "LensID",
                "AuxLens",
            ):
                key = TAGS.get(tag)
                if key:
                    value = exif.get(key)
                    if value:
                        return str(value).strip()

            return None
    except Exception:
        return None
