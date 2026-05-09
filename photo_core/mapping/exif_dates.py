# Role: Application module (see Stability Contract)

# Mapping: EXIF date and camera metadata
# Uses ExifTool via read_exif (single source of truth)

from photo_core.exif.reader import read_exif
from photo_core.exif.accessor import get_exif_value
from photo_core.exif.lens import extract_lens_model


def extract_exif_datetime(path):
    """
    Returns a datetime string or None.
    Informational only.
    """
    record = read_exif(path)
    if not record:
        return None

    return get_exif_value(
        record,
        "ExifIFD:DateTimeOriginal",
        "DateTimeOriginal",
        "CreateDate",
        "IFD0:ModifyDate"
    )


def extract_camera_model(path):
    """
    Returns a camera model string, or None.
    Informational only.
    """
    record = read_exif(path)
    if not record:
        return None

    make = get_exif_value(record, "IFD0:Make", "Make")
    model = get_exif_value(record, "IFD0:Model", "Model")

    if make and model:
        return f"{str(make).strip()} {str(model).strip()}"

    return (model or make) if (model or make) else None
