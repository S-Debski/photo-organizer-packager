# Role: Lens metadata resolver (see Stability Contract)

# photo_core/exif/lens.py
# ------------------------------------------------------------
# Lens resolution logic
# ------------------------------------------------------------

from photo_core.exif.reader import read_exif
from photo_core.exif.accessor import get_exif_value


def extract_lens_model(path) -> str | None:
    """
    Resolve a human-readable lens name.
    Works for Fuji, Panasonic, Olympus, Sony, Canon, Nikon.
    """
    record = read_exif(path)
    if not record:
        return None

    lens = get_exif_value(
        record,
        "ExifIFD:LensModel",
        "LensModel",
        "Composite:LensID",
        "LensID",
        "Lens",
        "XMP:Lens",
        "LensType",
        "MakerNotes:Lens",
    )

    return str(lens).strip() if lens else None
