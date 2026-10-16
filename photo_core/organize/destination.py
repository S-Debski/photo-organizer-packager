# Role: Application module (see Stability Contract)

# photo_core/organize/destination.py
# -----------------------------------------------------------------------------
# Resolve and validate the import destination (Pre‑Import design 07/08/09).
#
#   <destination>/<template expanded with shoot title + shoot date>
#
# Shared by the preview endpoint and /api/organize so what the user sees
# in the preview is exactly what the import uses. Pure path logic: nothing
# here creates directories or touches files.
# -----------------------------------------------------------------------------
import os
import re
from datetime import date

from photo_core.pre_import.directory_templates import (
    resolve_directory_template,
    TemplateError,
)

# Design 09: chronological at every level, human-readable last segment
DEFAULT_TEMPLATE = "{YYYY}/{MM}/{DD} - {title}"

# Camera-generated DCF folder names ("100_FUJI", "100CANON", "100_2809",
# "101MSDCF") say nothing about the shoot, so they're not used as titles.
_CAMERA_FOLDER = re.compile(r"^\d{3}[A-Za-z0-9_]{0,5}$")


class DestinationError(ValueError):
    """The destination can't be used; nothing may be copied."""


def is_camera_folder_name(name: str) -> bool:
    return bool(_CAMERA_FOLDER.match(name or ""))


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def is_within(path: str, parent: str) -> bool:
    try:
        return os.path.commonpath([_norm(path), _norm(parent)]) == _norm(parent)
    except ValueError:  # different drives
        return False


def resolve_destination(
    *,
    destination: str,
    template: str | None,
    title: str,
    shoot_date: str | date | None,
    protected: list[str] = (),
) -> tuple[str, str]:
    """
    Return (absolute destination folder, relative sub-path).

    Raises DestinationError when the destination is missing, not a folder,
    or inside the card/source (protected paths), or the template is invalid.
    """
    destination = (destination or "").strip()
    if not destination:
        raise DestinationError("Choose a destination folder first.")
    if os.path.exists(destination) and not os.path.isdir(destination):
        raise DestinationError("The destination is a file, not a folder.")

    for root in protected:
        if root and is_within(destination, root):
            raise DestinationError("The destination can't be on the card or inside the folder being imported.")

    title = (title or "").strip()
    if not title:
        raise DestinationError("Enter a shoot title.")

    if isinstance(shoot_date, str) and shoot_date:
        try:
            shoot_date = date.fromisoformat(shoot_date)
        except ValueError:
            raise DestinationError(f"Shoot date isn't a valid date: {shoot_date}")
    shoot_date = shoot_date or date.today()

    try:
        relative = resolve_directory_template(
            template or DEFAULT_TEMPLATE, title=title, shoot_date=shoot_date)
    except TemplateError as e:
        raise DestinationError(f"Folder layout: {e}")

    full = os.path.normpath(os.path.join(destination, relative))

    # Belt and braces: the template validator already blocks "..", drives
    # and absolute paths, but the result must stay under the destination.
    if not is_within(full, destination):
        raise DestinationError("Folder layout points outside the destination.")

    return full, relative.replace("/", os.sep)


def check_writable(folder: str) -> None:
    """Destination root must exist (or be creatable) and accept writes."""
    probe_root = folder
    while probe_root and not os.path.exists(probe_root):
        parent = os.path.dirname(probe_root)
        if parent == probe_root:
            break
        probe_root = parent
    if not probe_root or not os.access(probe_root, os.W_OK):
        raise DestinationError(f"Can't write to {probe_root or folder}.")
