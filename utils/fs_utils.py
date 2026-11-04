# Role: File system utilities (see Stability Contract)

# ============================================================================
# File: utils/fs_utils.py
#
# Responsibilities:
#   - Iterate image files (RAW + JPG)
#   - Provide specialised iterators for UI and processing
# ============================================================================

import os

# ✅ Define extensions ONCE
IMAGE_EXTS_JPEG = (".jpg", ".jpeg")
IMAGE_EXTS_RAW = (
    ".raf",  # Fuji ✅
    ".cr2",
    ".cr3",
    ".crw",  # Canon ✅ (incl 5D classic era)
    ".nef",
    ".nrw",  # Nikon ✅ (future-safe)
    ".arw",
    ".sr2",
    ".srf",  # Sony ✅
    ".orf",  # Olympus ✅ (E-500)
    ".pef",  # Pentax ✅ (K10D)
    ".rw2",  # Panasonic ✅
    ".dng",  # Adobe ✅
)

IMAGE_EXTS_ALL = IMAGE_EXTS_JPEG + IMAGE_EXTS_RAW
DEBUG_COPY = False


# -----------------------------------------------------------------------------
# Working directory default
# -----------------------------------------------------------------------------
def get_default_working_base():
    return os.path.join(os.path.expanduser("~"), "PhotoOrganizer", "sessions")


# -----------------------------------------------------------------------------
# Core iterator (ALL images)
# -----------------------------------------------------------------------------
"""Yield ALL supported images (JPG + RAW)."""


def iter_images(folder):
    for root, _, files in os.walk(folder):
        for f in files:
            name = f.lower()

            if name.endswith(IMAGE_EXTS_ALL):

                yield os.path.join(root, f)


# -----------------------------------------------------------------------------
# JPEG iterator (UI / thumbnails)
# -----------------------------------------------------------------------------
def iter_jpegs(folder):
    """Yield JPEG preview files only."""
    for path in iter_images(folder):
        ext = os.path.splitext(path)[1].lower()

        if ext in IMAGE_EXTS_JPEG:
            yield path


# -----------------------------------------------------------------------------
# RAW iterator (advanced / fallback)
# -----------------------------------------------------------------------------
def iter_raws(folder):
    """Yield RAW source files only."""
    for path in iter_images(folder):
        ext = os.path.splitext(path)[1].lower()

        if ext in IMAGE_EXTS_RAW:
            yield path


# -----------------------------------------------------------------------------
# Cleanup utilities
# -----------------------------------------------------------------------------
def cleanup_card_metadata(root):
    """
    Remove OS-generated metadata files from camera cards.
    Explicit, user-initiated only.
    """
    removed = []

    for base, dirs, files in os.walk(root):
        for fn in files:
            if fn.startswith("._") or fn == ".DS_Store":
                path = os.path.join(base, fn)
                try:
                    os.remove(path)
                    removed.append(path)
                except Exception:
                    pass

        for d in (".Spotlight-V100", ".Trashes"):
            if d in dirs:
                try:
                    os.rmdir(os.path.join(base, d))
                    removed.append(os.path.join(base, d))
                except Exception:
                    pass

    return removed


# -----------------------------------------------------------------------------
# Folder discovery
# -----------------------------------------------------------------------------
def _has_images_direct(folder):
    """True if folder contains image files directly (not just in subfolders)."""
    for f in os.listdir(folder):
        if f.lower().endswith(IMAGE_EXTS_ALL):
            return True
    return False


def _has_image_subfolders(folder):
    """True if folder contains subdirectories that themselves contain images."""
    try:
        for name in os.listdir(folder):
            sub = os.path.join(folder, name)
            if os.path.isdir(sub) and _has_images_direct(sub):
                return True
    except PermissionError:
        pass
    return False


def list_candidate_folders(sd_root):
    """
    Yield folders containing images for analysis.

    Logic:
    1. Look inside DCIM (standard camera structure)
    2. For each DCIM subfolder:
       - If it contains images directly → yield it as-is
       - If it contains subfolders with images → yield those subfolders instead
         (handles cameras that group by location/event e.g. Medburn/, USB/)
    3. Collision detection: if two different parent folders both contain a
       subfolder with the same name (e.g. 929_FUJI/Medburn + 105_PANA/Medburn),
       prefix all affected names with their parent to keep them unique:
       "929_FUJI/Medburn" and "105_PANA/Medburn".
    4. If no DCIM, fall back to top-level folders of sd_root.
    """
    dcim = os.path.join(sd_root, "DCIM")

    # Collect all candidate (path, display_name) pairs first
    candidates = []  # list of (path, display_name)
    # Track which simple names appear more than once
    name_count = {}

    if os.path.isdir(dcim):
        for parent_name in sorted(os.listdir(dcim)):
            parent_path = os.path.join(dcim, parent_name)
            if not os.path.isdir(parent_path):
                continue

            if _has_images_direct(parent_path):
                display = parent_name
                candidates.append((parent_path, display, None))
                name_count[display] = name_count.get(display, 0) + 1

            elif _has_image_subfolders(parent_path):
                for subname in sorted(os.listdir(parent_path)):
                    sub = os.path.join(parent_path, subname)
                    if os.path.isdir(sub) and _has_images_direct(sub):
                        display = subname
                        candidates.append((sub, display, parent_name))
                        name_count[display] = name_count.get(display, 0) + 1

    else:
        # No DCIM (a plain folder, external drive or NAS share): the folder
        # itself if it holds photos directly, then its top-level folders
        if _has_images_direct(sd_root):
            display = os.path.basename(os.path.normpath(sd_root)) or sd_root
            candidates.append((sd_root, display, None))
            name_count[display] = name_count.get(display, 0) + 1

        for name in sorted(os.listdir(sd_root)):
            p = os.path.join(sd_root, name)
            if os.path.isdir(p):
                display = name
                candidates.append((p, display, None))
                name_count[display] = name_count.get(display, 0) + 1

    # Yield paths; disambiguate display names where collisions exist
    for path, display, parent in candidates:
        if name_count.get(display, 0) > 1 and parent:
            # Collision — prefix with parent folder name
            display = f"{parent}/{display}"
        yield path
