# utils/thumb_cache.py
import os
import hashlib
from PIL import Image

THUMB_SIZE = (256, 256)

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def fingerprint(path):
    st = os.stat(path)
    raw = f"{path}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()

def thumb_path(cache_dir, img_path):
    key = fingerprint(img_path)
    return os.path.join(cache_dir, "thumbs", f"{key}.jpg")

def build_thumb(cache_dir, img_path):
    tp = thumb_path(cache_dir, img_path)
    if os.path.isfile(tp):
        return tp

    ensure_dir(os.path.dirname(tp))
    with Image.open(img_path) as im:
        im = im.convert("RGB")
        im.thumbnail(THUMB_SIZE)
        im.save(tp, "JPEG", quality=82, optimize=True)

    return tp
