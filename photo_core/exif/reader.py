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
import sys
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


# In a windowed (no-console) Windows build every exiftool.exe call would
# flash a console window without this.
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


@lru_cache(maxsize=1)
def resolve_exiftool_cmd() -> str | None:
    """
    Resolve exiftool executable path, in order:
      1. PHOTO_ORGANIZER_EXIFTOOL env var
      2. copy bundled with a frozen (PyInstaller) build: <bundle>/exiftool/
      3. PATH
      4. common install locations — macOS apps started from Finder do not
         inherit the shell PATH, so Homebrew's bin is not on it
    """
    explicit = os.environ.get("PHOTO_ORGANIZER_EXIFTOOL")
    if explicit and os.path.isfile(explicit):
        return explicit

    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        name = "exiftool.exe" if os.name == "nt" else "exiftool"
        bundled = os.path.join(bundle_root, "exiftool", name)
        if os.path.isfile(bundled):
            return bundled

    found = shutil.which("exiftool")
    if found:
        return found

    for candidate in ("/opt/homebrew/bin/exiftool", "/usr/local/bin/exiftool",
                      "/usr/bin/exiftool"):
        if os.path.isfile(candidate):
            return candidate

    return None


def exiftool_available() -> bool:
    return resolve_exiftool_cmd() is not None


# Records loaded by prefetch_exif(), keyed by normalised path. Starting
# exiftool costs ~150 ms on Windows, so one call per batch of files is far
# cheaper than one call per file.
_PREFETCHED: dict[str, dict] = {}
_PREFETCH_LIMIT = 20000
_BATCH_SIZE = 200


def _key(path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _stamp(path):
    """(size, mtime) — cards reuse names like DSCF0001, so path alone is not enough."""
    try:
        st = os.stat(path)
        return st.st_size, st.st_mtime
    except OSError:
        return None


def prefetch_exif(paths) -> int:
    """
    Read metadata for many files with as few exiftool runs as possible and
    keep it for read_exif(). Returns the number of records loaded.
    """
    cmd = resolve_exiftool_cmd()
    # Absolute paths: an argument-file line starting with "-" would be an option
    todo = [os.path.abspath(str(p)) for p in paths
            if _PREFETCHED.get(_key(p), (None,))[0] != _stamp(p)]
    if not cmd or not todo:
        return 0

    if len(_PREFETCHED) + len(todo) > _PREFETCH_LIMIT:
        _PREFETCHED.clear()

    loaded = 0
    for i in range(0, len(todo), _BATCH_SIZE):
        batch = todo[i:i + _BATCH_SIZE]
        try:
            # File names go through stdin (-@ -) to avoid Windows'
            # command-line length limit.
            proc = subprocess.run(
                [cmd, "-charset", "filename=utf8", "-json", "-n", "-G1", "-a",
                 "-s", "-@", "-"],
                input="\n".join(batch),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=NO_WINDOW,
                timeout=30 + len(batch),
            )
            records = json.loads(proc.stdout) if proc.stdout else []
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.warning(f"exiftool batch failed ({e}); falling back per file")
            continue

        for rec in records:
            src = rec.get("SourceFile")
            if src:
                _PREFETCHED[_key(src)] = (_stamp(src), rec)
                loaded += 1

    return loaded


def read_exif(path: str | Path) -> dict:
    """
    Read full metadata via exiftool (uses prefetch_exif() results first).
    """
    stamp = _stamp(path)
    hit = _PREFETCHED.get(_key(path))
    if hit is not None and hit[0] == stamp:
        return hit[1]
    return _read_exif_single(str(path), stamp)


@lru_cache(maxsize=2048)
def _read_exif_single(path: str, stamp=None) -> dict:
    # `stamp` is only part of the cache key
    cmd = resolve_exiftool_cmd()
    if not cmd:
        return {}

    try:
        proc = subprocess.run(
            [cmd, "-json", "-n", "-G1", "-a", "-s", os.path.abspath(path)],
            capture_output=True,
            text=True,
            # exiftool emits UTF-8 JSON; the Windows default (cp1252) fails to
            # decode some MakerNote bytes, which silently returned {} here.
            encoding="utf-8",
            errors="replace",
            creationflags=NO_WINDOW,
            # A windowed build has no valid stdin handle; inheriting it
            # raises "The handle is invalid" on Windows.
            stdin=subprocess.DEVNULL,
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
