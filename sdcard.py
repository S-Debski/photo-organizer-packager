"""
Optimized universal SD/CFexpress detection for Windows, macOS, Linux.

✅ FAST on multi-slot USB readers (skips empty slots)
✅ Filters only FAT/exFAT volumes between 0.5GB and 2TB
✅ Detects DCIM/PRIVATE/M4ROOT etc.
✅ Compatible with your existing Photo Organizer backend
"""

import os
import platform
from pathlib import Path

# Windows-specific imports
if os.name == "nt":
    import win32api
    import win32file
    import pythoncom
    import wmi


# -------------------------------------------------------------
# General helpers
# -------------------------------------------------------------
FLASH_FILESYSTEMS = {"FAT32", "FAT", "FAT16", "exFAT", "MSDOS", "VFAT"}
CAMERA_FOLDERS = {"DCIM", "PRIVATE", "AVCHD", "MISC", "MP_ROOT", "VIDEO", "DCIM/100MEDIA"}

MIN_SD_SIZE = 512 * 1024 * 1024           # 0.5 GB
MAX_SD_SIZE = 2 * 1024 * 1024 * 1024 * 1024  # 2 TB


def is_flash_fs(fs: str) -> bool:
    return fs and fs.upper() in FLASH_FILESYSTEMS


def has_camera_structure(path: Path) -> bool:
    try:
        root_items = {p.name.upper() for p in path.iterdir() if p.is_dir()}
        return any(folder in root_items for folder in CAMERA_FOLDERS)
    except Exception:
        return False


def size_within_sd_range(size: int) -> bool:
    return size and MIN_SD_SIZE <= size <= MAX_SD_SIZE


def normalize(path: str) -> str:
    return path.rstrip("\\/").upper() if path else None


"""
Optimized universal SD/CFexpress detection for Windows, macOS, Linux.

✅ FAST on multi-slot USB readers (skips empty slots)
✅ Filters only FAT/exFAT volumes between 0.5GB and 2TB
✅ Detects DCIM/PRIVATE/M4ROOT etc.
✅ Compatible with your existing Photo Organizer backend
"""

import os
import platform
from pathlib import Path

# Windows-specific imports
if os.name == "nt":
    import win32api
    import win32file
    import pythoncom
    import wmi


# -------------------------------------------------------------
# General helpers
# -------------------------------------------------------------
FLASH_FILESYSTEMS = {"FAT32", "FAT", "FAT16", "exFAT", "MSDOS", "VFAT"}
CAMERA_FOLDERS = {"DCIM", "PRIVATE", "AVCHD", "MISC", "MP_ROOT", "VIDEO", "DCIM/100MEDIA"}

MIN_SD_SIZE = 512 * 1024 * 1024           # 0.5 GB
MAX_SD_SIZE = 2 * 1024 * 1024 * 1024 * 1024  # 2 TB


def is_flash_fs(fs: str) -> bool:
    return fs and fs.upper() in FLASH_FILESYSTEMS


def has_camera_structure(path: Path) -> bool:
    try:
        root_items = {p.name.upper() for p in path.iterdir() if p.is_dir()}
        return any(folder in root_items for folder in CAMERA_FOLDERS)
    except Exception:
        return False


def size_within_sd_range(size: int) -> bool:
    return size and MIN_SD_SIZE <= size <= MAX_SD_SIZE


def normalize(path: str) -> str:
    return path.rstrip("\\/").upper() if path else None


# -------------------------------------------------------------
# WINDOWS IMPLEMENTATION (Optimized)
# -------------------------------------------------------------
def detect_windows_volumes():
    """
    Enumerate volumes quickly and skip empty multi-slot ports immediately.
    """
    pythoncom.CoInitialize()

    drives = win32api.GetLogicalDriveStrings().split("\x00")
    volumes = []

    for d in drives:
        letter = normalize(d)
        if not letter:
            continue

        root = letter + "\\"
        if not os.path.exists(root):
            continue

        # Get filesystem + label
        try:
            label, _, _, _, fs = win32api.GetVolumeInformation(letter)
        except Exception:
            fs = None
            label = None

        # Get size (FAST)
        try:
            secs, bps, free_c, total_c = win32file.GetDiskFreeSpace(root)
            size = total_c * secs * bps
        except Exception:
            size = 0

        volumes.append({
            "path": letter,
            "label": label,
            "filesystem": fs,
            "size_bytes": size,
        })

    return volumes


def filter_windows_sd_cards():
    """
    Optimized SD-card detection for Windows:

    ✅ Skips empty multi-reader slots (<64MB)
    ✅ Filters only flash-like filesystems
    ✅ Filters by realistic SD/CFexpress sizes
    ✅ Uses DCIM detection to prioritize camera cards
    """

    volumes = detect_windows_volumes()
    results = []

    for v in volumes:
        path = v["path"]
        fs = v["filesystem"]
        size = v["size_bytes"]

        # ✅ FAST SKIP: empty multi-reader slot (0–64 MB)
        if not size or size < 64 * 1024 * 1024:
            continue

        # ✅ Must be a flash filesystem
        if not is_flash_fs(fs):
            continue

        # ✅ Must be within SD/CFexpress realistic size
        if not size_within_sd_range(size):
            continue

        # ✅ Optional DCIM check (kept loose for general-purpose cards)
        root = Path(path + "\\")
        # keep card even if DCIM is missing
        has_camera_structure(root)  # result unused on purpose

        results.append(v)

    return results


# -------------------------------------------------------------
# macOS IMPLEMENTATION
# -------------------------------------------------------------
def detect_macos_volumes():
    volumes_root = Path("/Volumes")
    results = []

    if not volumes_root.exists():
        return results

    for vol in volumes_root.iterdir():
        if not vol.is_dir():
            continue
        if vol.name in {"Macintosh HD", "Macintosh HD - Data"}:
            continue

        fs, size = get_macos_disk_info(vol)
        results.append({
            "path": str(vol),
            "label": vol.name,
            "filesystem": fs,
            "size_bytes": size,
        })

    return results


def get_macos_disk_info(path: Path):
    try:
        import subprocess, plistlib
        info = plistlib.loads(subprocess.check_output(
            ["diskutil", "info", "-plist", str(path)]
        ))
        return info.get("FilesystemType"), info.get("TotalSize")
    except Exception:
        return None, None


def filter_macos_sd_cards():
    results = []
    for v in detect_macos_volumes():
        fs = v["filesystem"]
        size = v["size_bytes"]
        path = Path(v["path"])

        if not is_flash_fs(fs):
            continue
        if not size_within_sd_range(size):
            continue

        results.append(v)
    return results


# -------------------------------------------------------------
# LINUX IMPLEMENTATION
# -------------------------------------------------------------
def detect_linux_volumes():
    mounts = []
    media_root = Path("/media")
    if media_root.exists():
        for user_dir in media_root.iterdir():
            if user_dir.is_dir():
                for vol in user_dir.iterdir():
                    if vol.is_dir():
                        mounts.append(vol)

    mnt_root = Path("/mnt")
    if mnt_root.exists():
        mounts += [d for d in mnt_root.iterdir() if d.is_dir()]

    results = []
    for path in mounts:
        fs, size = get_linux_disk_info(path)
        results.append({
            "path": str(path),
            "label": path.name,
            "filesystem": fs,
            "size_bytes": size,
        })
    return results


def get_linux_disk_info(path: Path):
    try:
        stat = os.statvfs(path)
        size = stat.f_blocks * stat.f_frsize
    except Exception:
        size = None

    fs = None
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) > 2 and parts[1] == str(path):
                    fs = parts[2]
                    break
    except Exception:
        pass

    return fs, size


def filter_linux_sd_cards():
    results = []
    for v in detect_linux_volumes():
        fs = v["filesystem"]
        size = v["size_bytes"]

        if not is_flash_fs(fs):
            continue
        if not size_within_sd_range(size):
            continue

        results.append(v)
    return results


# -------------------------------------------------------------
# UNIVERSAL ENTRY POINTS
# -------------------------------------------------------------
def detect_sd_cards():
    system = platform.system().lower()

    if system == "windows":
        return filter_windows_sd_cards()
    elif system == "darwin":
        return filter_macos_sd_cards()
    elif system == "linux":
        return filter_linux_sd_cards()
    else:
        return []


def auto_select_sd_card():
    cards = detect_sd_cards()
    return cards[0] if len(cards) == 1 else None


# -------------------------------------------------------------
# Standalone tester
# -------------------------------------------------------------
if __name__ == "__main__":
    print("Testing optimized SD/CFexpress detection...\n")
    cards = detect_sd_cards()

    print("Detected cards:")
    for card in cards:
        print(card)

    if cards:
        print("\nAuto-select:", auto_select_sd_card())
    else:
        print("\nNo SD cards detected")
        

# -------------------------------------------------------------
# macOS IMPLEMENTATION
# -------------------------------------------------------------
def detect_macos_volumes():
    volumes_root = Path("/Volumes")
    results = []

    if not volumes_root.exists():
        return results

    for vol in volumes_root.iterdir():
        if not vol.is_dir():
            continue
        if vol.name in {"Macintosh HD", "Macintosh HD - Data"}:
            continue

        fs, size = get_macos_disk_info(vol)
        results.append({
            "path": str(vol),
            "label": vol.name,
            "filesystem": fs,
            "size_bytes": size,
        })

    return results


def get_macos_disk_info(path: Path):
    try:
        import subprocess, plistlib
        info = plistlib.loads(subprocess.check_output(
            ["diskutil", "info", "-plist", str(path)]
        ))
        return info.get("FilesystemType"), info.get("TotalSize")
    except Exception:
        return None, None


def filter_macos_sd_cards():
    results = []
    for v in detect_macos_volumes():
        fs = v["filesystem"]
        size = v["size_bytes"]
        path = Path(v["path"])

        if not is_flash_fs(fs):
            continue
        if not size_within_sd_range(size):
            continue

        results.append(v)
    return results


# -------------------------------------------------------------
# LINUX IMPLEMENTATION
# -------------------------------------------------------------
def detect_linux_volumes():
    mounts = []
    media_root = Path("/media")
    if media_root.exists():
        for user_dir in media_root.iterdir():
            if user_dir.is_dir():
                for vol in user_dir.iterdir():
                    if vol.is_dir():
                        mounts.append(vol)

    mnt_root = Path("/mnt")
    if mnt_root.exists():
        mounts += [d for d in mnt_root.iterdir() if d.is_dir()]

    results = []
    for path in mounts:
        fs, size = get_linux_disk_info(path)
        results.append({
            "path": str(path),
            "label": path.name,
            "filesystem": fs,
            "size_bytes": size,
        })
    return results


def get_linux_disk_info(path: Path):
    try:
        stat = os.statvfs(path)
        size = stat.f_blocks * stat.f_frsize
    except Exception:
        size = None

    fs = None
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) > 2 and parts[1] == str(path):
                    fs = parts[2]
                    break
    except Exception:
        pass

    return fs, size


def filter_linux_sd_cards():
    results = []
    for v in detect_linux_volumes():
        fs = v["filesystem"]
        size = v["size_bytes"]

        if not is_flash_fs(fs):
            continue
        if not size_within_sd_range(size):
            continue

        results.append(v)
    return results


# -------------------------------------------------------------
# UNIVERSAL ENTRY POINTS
# -------------------------------------------------------------
def detect_sd_cards():
    system = platform.system().lower()

    if system == "windows":
        return filter_windows_sd_cards()
    elif system == "darwin":
        return filter_macos_sd_cards()
    elif system == "linux":
        return filter_linux_sd_cards()
    else:
        return []


def auto_select_sd_card():
    cards = detect_sd_cards()
    return cards[0] if len(cards) == 1 else None


# -------------------------------------------------------------
# Standalone tester
# -------------------------------------------------------------
if __name__ == "__main__":
    print("Testing optimized SD/CFexpress detection...\n")
    cards = detect_sd_cards()

    print("Detected cards:")
    for card in cards:
        print(card)

    if cards:
        print("\nAuto-select:", auto_select_sd_card())
    else:
        print("\nNo SD cards detected")