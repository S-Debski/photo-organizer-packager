"""
Core photo organization logic for SD card imports
"""

import os
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
import logging
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class PhotoOrganizer:
    """Handles photo copying, organization, and backup"""

    def __init__(self, pictures_base: Optional[str] = None, sd_card_name: Optional[str] = None):
        """
        Initialize PhotoOrganizer

        Args:
            pictures_base: Base Pictures directory. Uses ~/Pictures if None.
            sd_card_name: Name for SD card folder. If None, uses the path name.
        """
        if pictures_base:
            self.pictures_base = Path(pictures_base)
        else:
            self.pictures_base = Path.home() / "Pictures"

        self.pictures_base.mkdir(parents=True, exist_ok=True)

        # Use custom SD card name or default
        self.sd_card_folder_name = sd_card_name or None
        if self.sd_card_folder_name:
            self.sd_card_root = self.pictures_base / self.sd_card_folder_name
            self.sd_card_root.mkdir(parents=True, exist_ok=True)
        else:
            self.sd_card_root = None

    # ✅✅ REPLACED WITH PYINSTALLER‑SAFE VERSION — DO NOT MODIFY
    def list_sd_cards(self) -> List[str]:
        """Reliable removable drive detection for Windows + PyInstaller EXE."""
        removable_drives = []

        if os.name == "nt":
            import win32file

            bits = win32file.GetLogicalDrives()

            for i in range(26):
                mask = 1 << i
                if bits & mask:
                    drive = f"{chr(65+i)}:\\"
                    dtype = win32file.GetDriveType(drive)

                    # 2 = DRIVE_REMOVABLE
                    if dtype == win32file.DRIVE_REMOVABLE:
                        removable_drives.append(drive)

        else:
            # POSIX (macOS + Linux)
            try:
                if os.path.exists('/Volumes'):
                    for item in os.listdir('/Volumes'):
                        if item not in ['Macintosh HD', 'Macintosh HD - Data', '.', '..']:
                            full_path = os.path.join('/Volumes', item)
                            if os.path.isdir(full_path):
                                removable_drives.append(full_path)
            except Exception:
                pass

            try:
                if os.path.exists('/media'):
                    for user in os.listdir('/media'):
                        user_media = os.path.join('/media', user)
                        if os.path.isdir(user_media):
                            for mount in os.listdir(user_media):
                                mount_path = os.path.join(user_media, mount)
                                if os.path.isdir(mount_path):
                                    removable_drives.append(mount_path)
            except Exception:
                pass

            try:
                if os.path.exists('/mnt'):
                    for mount in os.listdir('/mnt'):
                        mount_path = os.path.join('/mnt', mount)
                        if os.path.isdir(mount_path):
                            removable_drives.append(mount_path)
            except Exception:
                pass

        logger.info(f"Found {len(removable_drives)} removable drives: {removable_drives}")
        return removable_drives
    # ✅✅ END FIXED FUNCTION

    def analyze_card(self, sd_card_path: str) -> dict:
        """
        Analyze SD card structure to find photo folders and detect cameras via EXIF.
        """
        card_path = Path(sd_card_path)
        if not card_path.exists():
            logger.error(f"SD card path does not exist: {sd_card_path}")
            return {'total_photos': 0, 'folders': []}

        system_folders = {
            '.fseventsd', '.trashes', '$recycle.bin', 'system volume information',
            'avf_info', 'mp_root', 'private', 'lost.dir', 'misc',
            '.ds_store', 'thumbs.db', '.thumbnails', 'recycler',
            'found.000', 'found.001', '.', '..', 'shared', 'new sd card'
        }

        folders = []
        total_photos = 0

        for folder in sorted(card_path.rglob('*')):
            if not folder.is_dir():
                continue

            name = folder.name.lower()
            if name in system_folders or folder.name.startswith('.'):
                continue

            photos = []
            try:
                for file in sorted(folder.iterdir()):
                    if file.is_file() and self._is_photo(file):
                        photos.append(str(file))
            except Exception:
                continue

            if photos:
                camera_model = self._detect_camera_from_photos(photos)

                folders.append({
                    'path': str(folder),
                    'name': folder.name,
                    'photo_count': len(photos),
                    'camera_model': camera_model,
                    'photos': photos
                })

                total_photos += len(photos)

        folders.sort(key=lambda x: x['name'])

        return {
            'total_photos': total_photos,
            'folders': folders
        }

    def _detect_camera_from_photos(self, photo_paths: List[str]) -> str:
        """Detect camera model from EXIF."""
        try:
            import piexif
            for path in photo_paths[:5]:
                try:
                    exif = piexif.load(path)
                    for ifd_name in ("0th", "Exif", "GPS", "1st"):
                        ifd = exif.get(ifd_name, {})
                        for tag in [piexif.ImageIFD.Model, piexif.ImageIFD.Make, 272, 271]:
                            val = ifd.get(tag)
                            if val:
                                s = val.decode() if isinstance(val, bytes) else str(val)
                                if s.strip().lower() != "unknown":
                                    return s.strip()
                except:
                    pass
        except ImportError:
            pass

        try:
            from PIL import Image, ExifTags
            TAGS = ExifTags.TAGS
            for p in photo_paths[:5]:
                try:
                    img = Image.open(p)
                    exif = img.getexif()
                    if not exif:
                        continue
                    data = {TAGS.get(k, k): v for k, v in exif.items()}
                    for key in ['Model', 'LensModel', 'Model Name']:
                        if key in data:
                            s = str(data[key]).strip()
                            if s.lower() != 'unknown':
                                return s
                    if 272 in exif:
                        s = str(exif[272]).strip()
                        if s.lower() != 'unknown':
                            return s
                except:
                    pass
        except ImportError:
            pass

        return "Unknown"

    def _is_photo(self, file_path: Path) -> bool:
        """Check if file is a photo"""
        photo_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp',
            '.tiff', '.tif', '.raw', '.cr2', '.nef',
            '.arw', '.dng', '.heic', '.heif', '.webp', '.svg'
        }
        return file_path.suffix.lower() in photo_extensions

    def find_photo_files(self, directory: str) -> List[str]:
        """Recursively find all photo files."""
        photo_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp',
            '.tiff', '.tif', '.raw', '.cr2', '.nef',
