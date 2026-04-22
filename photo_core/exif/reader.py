# photo_core/exif/reader.py
# ------------------------------------------------------------
# ExifTool wrapper with caching
#
# - Uses exiftool (industry standard)
# - Reads EXIF + XMP + MakerNotes
# - Cached for performance
# - OS-agnostic
# ------------------------------------------------------------

import subprocess
import json
import shutil
import os
from functools import lru_cache
from pathlib import Path


class ExifToolError(RuntimeError):
    pass


def resolve_exiftool_cmd() -> str | None:
    """
    Resolve exiftool executable path.

    Priority:
    1) PHOTO_ORGANIZER_EXIFTOOL environment variable
    2) PATH lookup ("exiftool")
    """
    explicit = os.environ.get("PHOTO_ORGANIZER_EXIFTOOL")
    if explicit and os.path.isfile(explicit):
        return explicit

    return shutil.which("exiftool")


def exiftool_available() -> bool:
    """
    Return True if exiftool can be resolved.
    """
    return resolve_exiftool_cmd() is not None


@lru_cache(maxsize=2048)
def read_exif(path: str | Path) -> dict:
    """
    Read full metadata for a file using exiftool.
    Cached to avoid repeated subprocess calls.

    Returns:
        dict of tags (ExifTool JSON format)
    """
    cmd = resolve_exiftool_cmd()
    if not cmd:
        # Graceful degradation: no MakerNotes / XMP
        return {}

    path = str(path)

    try:
        proc = subprocess.run(
            [cmd, "-json", path],
            capture_output=True,
            text=True,
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
