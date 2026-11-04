# Role: Application module (see Stability Contract)

# utils/thumb_cache.py
# -----------------------------------------------------------------------------
# Disk-cached downscaled previews for the browser.
#
# The grid used to load every original straight off the card (often
# 10–25 MB per JPEG) and could not show RAW files at all. This renders a
# small JPEG once per (file, size) and serves it from the cache after that.
#
#   JPEG: PIL draft mode decodes at 1/2–1/8 scale (fast), then resizes.
#   RAW:  the camera's embedded preview, extracted with exiftool.
# -----------------------------------------------------------------------------
import io
import os
import hashlib
import subprocess
import threading

from PIL import Image, ImageOps

from photo_core.exif.reader import resolve_exiftool_cmd, read_exif, NO_WINDOW

JPEG_EXTS = (".jpg", ".jpeg")

# Limit concurrent decodes — the browser requests a whole grid at once
_DECODE_SLOTS = threading.BoundedSemaphore(4)

# EXIF Orientation → PIL transpose op (embedded RAW previews carry no EXIF,
# so the RAW file's own Orientation is applied explicitly)
_ORIENTATION = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


def fingerprint(path, size):
    st = os.stat(path)
    raw = f"{os.path.abspath(path)}|{size}|{st.st_size}|{int(st.st_mtime)}"
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def thumb_path(cache_dir, img_path, size):
    return os.path.join(cache_dir, "thumbs", f"{fingerprint(img_path, size)}.jpg")


def _raw_preview(path) -> Image.Image | None:
    """Largest embedded JPEG in a RAW file, oriented."""
    cmd = resolve_exiftool_cmd()
    if not cmd:
        return None
    for tag in ("-JpgFromRaw", "-PreviewImage", "-ThumbnailImage"):
        proc = subprocess.run(
            [cmd, "-b", tag, os.path.abspath(path)],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
            timeout=15,
        )
        if proc.returncode == 0 and len(proc.stdout) > 1000:
            im = Image.open(io.BytesIO(proc.stdout))
            orientation = read_exif(path).get("IFD0:Orientation")
            op = _ORIENTATION.get(orientation)
            return im.transpose(op) if op else im
    return None


def build_thumb(cache_dir, img_path, size=320) -> str | None:
    """
    Return the path of a cached JPEG no larger than size×size, building it
    if needed. None if no preview can be produced.
    """
    tp = thumb_path(cache_dir, img_path, size)
    if os.path.isfile(tp):
        return tp

    with _DECODE_SLOTS:
        if os.path.isfile(tp):  # built by another request while waiting
            return tp

        if img_path.lower().endswith(JPEG_EXTS):
            im = Image.open(img_path)
            im.draft("RGB", (size, size))
            im = ImageOps.exif_transpose(im)
        else:
            im = _raw_preview(img_path)
            if im is None:
                # TIFF-based RAWs (some DNG/NEF) can be decoded directly
                try:
                    im = ImageOps.exif_transpose(Image.open(img_path))
                    im.load()
                except Exception:
                    return None

        im = im.convert("RGB")
        im.thumbnail((size, size), Image.Resampling.LANCZOS)

        os.makedirs(os.path.dirname(tp), exist_ok=True)
        tmp = f"{tp}.{threading.get_ident()}.tmp"
        im.save(tmp, "JPEG", quality=82, optimize=True)
        os.replace(tmp, tp)
        return tp
