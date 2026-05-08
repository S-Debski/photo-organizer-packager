# Role: Application module

from photo_core.exif.reader import read_exif
from photo_core.exif.accessor import get_exif_value


def extract_camera_model(path) -> str | None:
    record = read_exif(path)
    if not record:
        return None

    make = get_exif_value(record, "IFD0:Make", "Make")
    model = get_exif_value(record, "IFD0:Model", "Model")

    if make and model:
        return f"{make.strip()} {model.strip()}"

    return (model or make) if (model or make) else None
