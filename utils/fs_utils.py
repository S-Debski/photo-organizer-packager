# ============================================================================
# Role: File system utilities (see Stability Contract)
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
    ".raf",                 # Fuji ✅
    ".cr2", ".cr3", ".crw", # Canon ✅ (incl 5D classic era)
    ".nef", ".nrw",         # Nikon ✅ (future-safe)
    ".arw", ".sr2", ".srf", # Sony ✅
    ".orf",                 # Olympus ✅ (E-500)
    ".pef",                 # Pentax ✅ (K10D)
    ".rw2",                 # Panasonic ✅
    ".dng"                  # Adobe ✅
)

IMAGE_EXTS_ALL = IMAGE_EXTS_JPEG + IMAGE_EXTS_RAW
DEBUG_COPY = False

# -----------------------------------------------------------------------------
# Working directory default
# -----------------------------------------------------------------------------
def get_default_working_base():
    return os.path.join(
        os.path.expanduser("~"),
        "PhotoOrganizer",
        "sessions"
    )


# -----------------------------------------------------------------------------
# Core iterator (ALL images)
# -----------------------------------------------------------------------------
    """Yield ALL supported images (JPG + RAW)."""
def iter_images(folder):
    for root, _, files in os.walk(folder):
        for f in files:
            name = f.lower()

            if name.endswith((".jpg", ".jpeg", ".raf")):
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
def list_candidate_folders(sd_root):
    """
    Prefer camera folders inside DCIM.
    If no DCIM, fallback to top-level folders.
    """
    dcim = os.path.join(sd_root, "DCIM")

    if os.path.isdir(dcim):
        for name in os.listdir(dcim):
            p = os.path.join(dcim, name)
            if os.path.isdir(p):
                yield p
        return

    for name in os.listdir(sd_root):
        p = os.path.join(sd_root, name)
        if os.path.isdir(p):
            yield p