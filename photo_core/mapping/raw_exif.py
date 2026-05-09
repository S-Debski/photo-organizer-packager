# Role: Application module (see Stability Contract)

# utils/raw_exif.py
# Future RAW EXIF support via exiv2 or libraw

import subprocess
import json

def extract_raw_exif(path):
    """
    Future-ready exiv2/libraw EXIF extraction.
    Safe stub for now.
    """
    try:
        # Example future call:
        #
        # result = subprocess.run(
        #     ["exiv2", "-Pkt", path],
        #     capture_output=True,
        #     text=True
        # )
        #
        # parse result.stdout into camera/lens metadata
        #
        pass
    except Exception:
        pass

    return {
        "make": None,
        "model": None,
        "lens": None,
        "datetime": None,
        "gps": None
    }
