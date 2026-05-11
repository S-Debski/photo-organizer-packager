# Role: Application module (see Stability Contract)
# utils/fs_utils.py
import os

# JPEG for EXIF + thumbnails (fast & safe)
IMAGE_EXTS_JPEG = {".jpg", ".jpeg"}

# RAW formats for fallback
IMAGE_EXTS_RAW = {
    ".cr2", ".cr3", ".nef", ".arw", ".raf",
    ".orf", ".rw2", ".dng"
}

def get_default_working_base():
    return os.path.join(
        os.path.expanduser("~"),
        "PhotoOrganizer",
        "sessions"
    )


def iter_jpegs(root):
    """Yield JPEGs only — these go to EXIF + preview."""
    for base, _, files in os.walk(root):
        for fn in files:

            # ✅ Ignore macOS AppleDouble metadata files
            if fn.startswith("._"):
                continue

            if os.path.splitext(fn)[1].lower() in IMAGE_EXTS_JPEG:
                yield os.path.join(base, fn)



def iter_raws(root):
    """Yield RAW files — fallback when no JPEGs exist."""
    for base, _, files in os.walk(root):
        for fn in files:

            # ✅ Ignore macOS AppleDouble metadata files
            if fn.startswith("._"):
                continue

            if os.path.splitext(fn)[1].lower() in IMAGE_EXTS_RAW:
                yield os.path.join(base, fn)

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

        # macOS metadata dirs
        for d in (".Spotlight-V100", ".Trashes"):
            if d in dirs:
                try:
                    os.rmdir(os.path.join(base, d))
                    removed.append(os.path.join(base, d))
                except Exception:
                    pass

    return removed

def list_candidate_folders(sd_root):
    """
    Prefer camera folders inside DCIM.
    If no DCIM, fallback to top-level folders.
    """
    dcim = os.path.join(sd_root, "DCIM")
    if os.path.isdir(dcim):
        # Camera standard: DCIM/100xxxx, 101xxxx, etc.
        for name in os.listdir(dcim):
            p = os.path.join(dcim, name)
            if os.path.isdir(p):
                yield p
        return

    # Fall back to root-level folders
    for name in os.listdir(sd_root):
        p = os.path.join(sd_root, name)
        if os.path.isdir(p):
            yield p

    def iter_images(root):
        """
        Backward‑compatible alias for modules still expecting iter_images().
        JPEG‑only for performance and safety.
        """
        yield from iter_jpegs(root)
