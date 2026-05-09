# Role: Application module (see Stability Contract)

"""
PhotoOrganizer – v2.7 FINAL
Working version with:
✅ analyze_card
✅ RAW + JPEG EXIF
✅ create_camera_folder (missing in your version)
✅ copy_photos
✅ skip lists
"""

import os
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS

# RAW support
try:
    import rawpy
except ImportError:
    rawpy = None


# Folders to skip
SKIP_FOLDERS = {
    'venv','env','__pycache__',
    'lib','site-packages',
    'debug','dist','build','pip'
}


# ---------------------------------------------------------------------
# EXIF helpers
# ---------------------------------------------------------------------
def get_camera_model(path: str) -> str:
    if not path or not os.path.exists(path):
        return "Unknown"

    # JPG/TIFF EXIF
    try:
        img = Image.open(path)
        exif = img._getexif()
        if exif:
            for tag, value in exif.items():
                if TAGS.get(tag) == "Model":
                    return str(value)
    except:
        pass

    # RAW EXIF fallback
    if rawpy:
        try:
            with rawpy.imread(path) as raw:
                if raw.metadata.camera_model:
                    return raw.metadata.camera_model
        except:
            pass

    return "Unknown"


def get_lens_model(path: str) -> str:
    if not path or not os.path.exists(path):
        return "Unknown"

    try:
        img = Image.open(path)
        exif = img._getexif()
        if exif:
            for tag, value in exif.items():
                if TAGS.get(tag) in ("LensModel","Lens","LensSpecification"):
                    return str(value)
    except:
        pass

    if rawpy:
        try:
            with rawpy.imread(path) as raw:
                if raw.metadata.lens:
                    return raw.metadata.lens
                if raw.metadata.lens_model:
                    return raw.metadata.lens_model
        except:
            pass

    return "Unknown"


# ---------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------
class PhotoOrganizer:
    def __init__(self, sd_card_name=None):
        self.sd_card_name = sd_card_name
        self.pictures_base = Path.home() / "Pictures" / "Organized"
        self.pictures_base.mkdir(parents=True, exist_ok=True)
        self.sd_card_root = None

    def _is_photo(self, path: Path) -> bool:
        return path.suffix.lower() in {
            ".jpg",".jpeg",".png",".arw",".nef",".cr2",".cr3",".raf",".rw2",".orf"
        }

    def find_photo_files(self, folder: str):
        root = Path(folder)
        results = []
        for p in root.rglob("*"):
            if p.is_file() and self._is_photo(p):
                results.append(str(p))
        return results

    # -----------------------------------------------------------------
    # Analyze card
    # -----------------------------------------------------------------
    def analyze_card(self, sd_root: str):
        root = Path(sd_root)
        self.sd_card_root = root

        if not root.exists():
            raise FileNotFoundError(f"SD card path does not exist: {sd_root}")

        results = []
        total = 0

        for folder in root.rglob("*"):
            if not folder.is_dir():
                continue
            if folder.name.lower() in SKIP_FOLDERS:
                continue
            if folder.name.startswith('.'):
                continue

            photos = self.find_photo_files(str(folder))
            if not photos:
                continue

            first = photos[0]
            cam = get_camera_model(first)
            lens = get_lens_model(first)

            results.append({
                "name": folder.name,
                "path": str(folder),
                "photo_count": len(photos),
                "photos": photos,
                "camera_model": cam,
                "lens": lens
            })

            total += len(photos)

        return {
            "success": True,
            "folders": results,
            "total_photos": total
        }

    # -----------------------------------------------------------------
    # ✅ THIS WAS MISSING IN YOUR VERSION
    # -----------------------------------------------------------------
    def create_camera_folder(self, camera_name: str, event_name: str=None):
        safe_cam = camera_name.replace(" ", "_") if camera_name else "Unknown"

        if event_name:
            safe_evt = event_name.replace(" ", "_")
            dest = self.pictures_base / safe_cam / safe_evt
        else:
            dest = self.pictures_base / safe_cam

        dest.mkdir(parents=True, exist_ok=True)
        return dest

    # -----------------------------------------------------------------
    # Copy Photos
    # -----------------------------------------------------------------
    def copy_photos(self, src_folder: str, dest_folder: Path, progress_callback=None):
        errors = []
        copied = 0

        photos = self.find_photo_files(src_folder)
        total = len(photos)

        for idx, src in enumerate(photos, start=1):
            try:
                dest = dest_folder / Path(src).name

                if dest.exists():
                    dest.unlink()

                with open(src, "rb") as f_src, open(dest, "wb") as f_dst:
                    f_dst.write(f_src.read())

                copied += 1

            except Exception as e:
                errors.append(f"{src}: {e}")

            if progress_callback:
                progress_callback(idx, total)

        return copied, errors
