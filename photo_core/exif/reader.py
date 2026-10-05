# Role: EXIF extraction interface (see Stability Contract)

# photo_core/exif/reader.py
# ------------------------------------------------------------
# ExifTool wrapper with caching
#
# - Uses exiftool (industry standard)
# - Reads EXIF + XMP + MakerNotes
# - Cached for performance
# - OS-agnostic
# ------------------------------------------------------------

# =============================================================================## Role: EXIF extraction interface
# photo_core/exif/reader.py
# =============================================================================

import subprocess
import json
import shutil
import os
import logging

from functools import lru_cache
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

logger = logging.getLogger(__name__)


# =============================================================================
# ✅ GPS EXTRACTOR (clean + safe)
# =============================================================================

def get_exif_gps(path):
    try:
        img = Image.open(path)
        exif = img._getexif()

        if not exif:
            logger.debug(f"No EXIF: {path}")
            return None

        # ✅ Extract GPS block
        gps_info = {}
        for tag, value in exif.items():
            name = TAGS.get(tag)
            if name == "GPSInfo":
                for t in value:
                    sub_name = GPSTAGS.get(t)
                    gps_info[sub_name] = value[t]

        if not gps_info:
            logger.debug(f"No GPS info: {path}")
            return None

        if "GPSLatitude" not in gps_info or "GPSLongitude" not in gps_info:
            logger.debug(f"Missing GPS coords: {path}")
            return None

        # ✅ Convert EXIF → decimal
        def convert(coord):
            def to_float(x):
                try:
                    return float(x)
                except Exception:
                    return x[0] / x[1]

            d = to_float(coord[0])
            m = to_float(coord[1])
            s = to_float(coord[2])
            return d + (m / 60.0) + (s / 3600.0)

        # ✅ Clean EXIF refs
        def clean_ref(ref):
            if isinstance(ref, bytes):
                ref = ref.decode("utf-8", errors="ignore")
            if isinstance(ref, (list, tuple)):
                ref = ref[0]
            return str(ref).strip().upper()

        lat = convert(gps_info["GPSLatitude"])
        lat_ref = clean_ref(gps_info.get("GPSLatitudeRef", ""))

        lon = convert(gps_info["GPSLongitude"])
        lon_ref = clean_ref(gps_info.get("GPSLongitudeRef", ""))

        if lat_ref == "S":
            lat = -lat
        if lon_ref == "W":
            lon = -lon

        # ✅ UK sanity correction
        if 50 < lat < 60 and lon > 0:
            logger.warning(f"Correcting longitude for {path}: {lon} → {-lon}")
            lon = -lon

        logger.debug(f"GPS [{path}] → lat={lat}, lon={lon}")

        return lat, lon

    except Exception as e:
        logger.error(f"EXIF read error: {path} → {e}")
        return None


# =============================================================================
# ✅ EXIFTOOL SUPPORT
# =============================================================================

class ExifToolError(RuntimeError):
    pass


def resolve_exiftool_cmd() -> str | None:
    """
    Resolve exiftool executable path.
    """
    explicit = os.environ.get("PHOTO_ORGANIZER_EXIFTOOL")
    if explicit and os.path.isfile(explicit):
        return explicit

    return shutil.which("exiftool")


def exiftool_available() -> bool:
    return resolve_exiftool_cmd() is not None


@lru_cache(maxsize=2048)
def read_exif(path: str | Path) -> dict:
    """
    Read full metadata via exiftool
    """
    cmd = resolve_exiftool_cmd()
    if not cmd:
        return {}

    path = str(path)

    try:
        proc = subprocess.run(
            [cmd, "-json", "-n", "-G1", "-a", "-s", path],
            capture_output=True,
            text=True,
            # exiftool emits UTF-8 JSON; the Windows default (cp1252) fails to
            # decode some MakerNote bytes, which silently returned {} here.
            encoding="utf-8",
            errors="replace",
            timeout=5
        )
    except FileNotFoundError:
        return {}

    if proc.returncode != 0 or not proc.stdout:
        return {}

    try:
        data = json.loads(proc.stdout)
        return data[0] if data else {}
    except json.JSONDecodeError:
        return {}
