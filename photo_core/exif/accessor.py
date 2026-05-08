# photo_core/exif/lens.py
# ------------------------------------------------------------
# Lens resolution logic
# ------------------------------------------------------------

from photo_core.exif.reader import read_exif


def extract_lens_model(path) -> str | None:
    """
    Resolve a human-readable lens name.
    Works for Fuji, Panasonic, Olympus, Sony, Canon, Nikon.
    """
    exif = read_exif(path)
    if not exif:
        return None

    return (
            exif.get("LensModel")
            or exif.get("ExifIFD:LensModel")  # ✅ THIS is the key you're missing
            or exif.get("Composite:LensID")
            or exif.get("LensID")
            or exif.get("Lens")
            or exif.get("XMP:Lens")
            or exif.get("LensType")
            or exif.get("MakerNotes:Lens")
    )