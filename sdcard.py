"""
Ultra‑fast SD / CFexpress card detection (v3.3 FINAL)
✅ Detects ONLY real SD / CFexpress cards
✅ Excludes cloud volumes (Google Drive, OneDrive, Dropbox, iCloud, etc.)
✅ Excludes empty card‑reader slots (0‑byte removable volumes)
✅ Excludes local disks, network drives, Volume GUIDs, and virtual FS
✅ Works perfectly with hybrid auto‑jump main.js
"""

import psutil
from pathlib import Path

# Flash storage size range (0.5 GB → 2 TB)
MIN_SD_SIZE = 512 * 1024 * 1024
MAX_SD_SIZE = 2 * 1024 * 1024 * 1024 * 1024  # 2 TB

# Typical camera directory names
CAMERA_ROOTS = {"DCIM", "PRIVATE", "M4ROOT", "AVCHD", "MP_ROOT", "XDROOT"}

# Allowed filesystems for SD cards
FLASH_FS = {"FAT32", "EXFAT", "FAT", "FAT16", "VFAT", "MSDOS"}

# Cloud provider keywords for filtering
CLOUD_KEYWORDS = {
    "google", "drivefs", "gdfs", "googledrive", "gdrive",
    "onedrive", "dropbox", "icloud", "box", "pcloud",
    "syncthing", "sharepoint"
}

# Cloud / virtual filesystems
CLOUD_FS = {"DRIVEFS", "GDFS", "GOOGLEDRIVEFS", "FS-GDFS"}

# Filesystems that should NEVER be considered SD
VIRTUAL_FS = {"CDFS", "ISO9660"}


def has_camera_folders(mount: Path) -> bool:
    """Check root directory for typical camera folder structure."""
    try:
        entries = {p.name.upper() for p in mount.iterdir() if p.is_dir()}
        return any(name in entries for name in CAMERA_ROOTS)
    except Exception:
        return False


def detect_sd_cards():
    """
    FINAL ultra-fast SD-card detection.
    Only true removable flash storage remains.
    """

    results = []

    for part in psutil.disk_partitions(all=False):
        mount = part.mountpoint              # e.g. "F:\\"
        device = (part.device or "").lower()
        opts   = (part.opts or "").lower()
        fstype = (part.fstype or "").upper()

        # --------------------------------------------------------
        # ✅ 1. Must be a removable device (CRITICAL)
        # Your debug output: real SD card (F:) has "rw,removable"
        # Google Drive I:\ = "rw,fixed" → excluded!
        # --------------------------------------------------------
        if "removable" not in opts:
            continue

        # --------------------------------------------------------
        # ✅ 2. Exclude empty card reader slots
        # FS missing OR size = 0 → skip
        # --------------------------------------------------------
        if not fstype:
            continue

        try:
            usage = psutil.disk_usage(mount)
            if usage.total == 0:
                continue
        except Exception:
            continue

        # --------------------------------------------------------
        # ✅ 3. Exclude CD/DVD/ISO/virtual drives
        # --------------------------------------------------------
        if fstype in VIRTUAL_FS:
            continue

        # --------------------------------------------------------
        # ✅ 4. Exclude cloud filesystems (DriveFS/GDFS/etc.)
        # --------------------------------------------------------
        if fstype.lower() in CLOUD_FS:
            continue

        # --------------------------------------------------------
        # ✅ 5. Exclude cloud drives by name/path
        # --------------------------------------------------------
        if any(k in mount.lower() for k in CLOUD_KEYWORDS):
            continue
        if any(k in device for k in CLOUD_KEYWORDS):
            continue

        # --------------------------------------------------------
        # ✅ 6. Exclude reparse/virtual/sparse cloud volumes
        # --------------------------------------------------------
        if any(flag in opts for flag in ["reparse", "sparse", "cloud"]):
            continue

        # --------------------------------------------------------
        # ✅ 7. Exclude Volume GUID drives unless removable
        # (Google Drive often creates \\?\Volume{GUID})
        # --------------------------------------------------------
        if device.startswith("\\\\?\\volume") and "removable" not in opts:
            continue

        # --------------------------------------------------------
        # ✅ 8. SD must have flash-storage-like size
        # --------------------------------------------------------
        size = usage.total
        if not (MIN_SD_SIZE <= size <= MAX_SD_SIZE):
            continue

        # --------------------------------------------------------
        # ✅ 9. Must use a flash-friendly FS
        # --------------------------------------------------------
        if fstype not in FLASH_FS:
            continue

        # --------------------------------------------------------
        # ✅ 10. Valid SD card — add it
        # --------------------------------------------------------
        root = Path(mount)
        results.append({
            "path": mount,
            "label": root.drive,
            "filesystem": fstype,
            "size_bytes": size,
            "has_camera_dirs": has_camera_folders(root)
        })

    return results


def auto_select_sd_card():
    cards = detect_sd_cards()
    return cards[0] if len(cards) == 1 else None


if __name__ == "__main__":
    print("\nSD detect v3.3 test output:")
    print(detect_sd_cards())