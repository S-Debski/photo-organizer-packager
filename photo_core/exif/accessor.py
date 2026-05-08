# Role: Application module

# photo_core/exif/accessor.py
# ------------------------------------------------------------
# Unified Accessor for exif data
# ------------------------------------------------------------

from photo_core.exif.reader import read_exif


def get_exif_value(record, *keys):
    """
    Try multiple EXIF keys and return the first valid value.
    """
    for key in keys:
        val = record.get(key)
        if val:
            return val
    return None