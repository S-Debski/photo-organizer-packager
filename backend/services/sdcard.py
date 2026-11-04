# Role: Application module (see Stability Contract)

# backend/services/sdcard.py
# ------------------------------------------------------------
# Universal SD / CFexpress detection (Windows, macOS, Linux)
#
# Design goals:
# - Correct detection of real camera cards
# - Exclude cloud / virtual drives by default
# - Stable across filesystem types (exFAT, FAT32, etc.)
# - One authoritative backend decision
# ------------------------------------------------------------

import os
import platform
from pathlib import Path

# ------------------------------------------------------------
# Universal SD / CFexpress detection (Windows, macOS, Linux)
# ------------------------------------------------------------


# Windows-specific imports
if os.name == "nt":
    import win32api
    import win32file

    try:
        import pythoncom
    except ImportError:
        pythoncom = None


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
CAMERA_FOLDERS = {
    "DCIM",
    "PRIVATE",
    "AVCHD",
    "MISC",
    "MP_ROOT",
    "VIDEO",
    "100MEDIA",
}

MIN_SD_SIZE = 512 * 1024 * 1024  # 0.5 GB
MAX_SD_SIZE = 2 * 1024 * 1024 * 1024 * 1024  # 2 TB

# Debug section
DEBUG = False  # 🔁 flip to True when debugging drive detection


# ------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------
def has_camera_structure(root: Path) -> bool:
    """
    True if the root contains a typical camera folder.
    Empty cards are allowed.
    """
    try:
        entries = {p.name.upper() for p in root.iterdir() if p.is_dir()}
        if not entries:
            return True
        return any(name in entries for name in CAMERA_FOLDERS)
    except Exception:
        return False


def size_within_sd_range(size: int) -> bool:
    return size and MIN_SD_SIZE <= size <= MAX_SD_SIZE


# ------------------------------------------------------------
# WINDOWS IMPLEMENTATION
# ------------------------------------------------------------
def detect_windows_volumes():
    """
    Enumerate all Windows logical drives with size + filesystem + label.
    """
    if pythoncom:
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

    drives = win32api.GetLogicalDriveStrings().split("\x00")
    volumes = []

    for d in drives:
        if not d:
            continue

        try:
            label, _, _, _, fs = win32api.GetVolumeInformation(d)
        except Exception:
            label, fs = None, None

        try:
            sectors, bytes_per_sector, _, total_clusters = win32file.GetDiskFreeSpace(d)
            size = sectors * bytes_per_sector * total_clusters
        except Exception:
            size = 0

        volumes.append(
            {
                "path": d.rstrip("\\"),
                "label": label,
                "filesystem": fs,
                "size_bytes": size,
            }
        )

    return volumes


def is_cloud_or_virtual_drive_windows(v: dict) -> bool:
    """
    Identify cloud / virtual drives such as Google Drive, OneDrive, etc.
    """
    label = (v.get("label") or "").lower()
    fs = (v.get("filesystem") or "").upper()
    size = v.get("size_bytes", 0)

    cloud_keywords = [
        "google drive",
        "google-drive",
        "drivefs",
        "onedrive",
        "dropbox",
        "icloud",
    ]

    if any(k in label for k in cloud_keywords):
        return True

    # Very large NTFS volumes are almost always internal or virtual
    if fs == "NTFS" and size > 500 * 1024**3:
        return True

    return False


def filter_windows_sd_cards(include_fixed: bool = False):
    """
    Windows SD / CFexpress detection (Windows-correct).

    Rules:
    - Do NOT rely on DRIVE_REMOVABLE (unreliable on Windows)
    - Exclude empty reader slots (size == 0)
    - Exclude cloud / virtual drives by default
    - Exclude large NTFS system disks
    - Accept FAT32 / exFAT volumes within SD size range
    - Camera folder structure is a soft signal
    """

    results = []

    for v in detect_windows_volumes():
        path = v["path"] + "\\"
        size = v["size_bytes"]
        fs = v["filesystem"]

        if DEBUG:
            print("🔍 WINDOWS VOLUME:", path, "FS:", fs, "SIZE:", size)

        # Exclude empty slots and nonsense
        if not size_within_sd_range(size):
            if DEBUG:
                print("  ⛔ excluded: size range")
            continue

        # Must be mounted media
        if fs is None:
            if DEBUG:
                print("  ⛔ excluded: no filesystem")
            continue

        # Exclude cloud / virtual drives (unless explicitly enabled) or
        # ✅ Flag cloud / virtual drives, but don't exclude yet
        if is_cloud_or_virtual_drive_windows(v):
            v["is_virtual"] = True
            if DEBUG:
                print("  ⚠ marked as virtual drive")
        else:
            v["is_virtual"] = False

        # Camera structure is optional (empty cards allowed)
        if not has_camera_structure(Path(path)):
            if DEBUG:
                print("  ⚠ no camera structure (allowed)")

        if DEBUG:
            print("  ✅ accepted")

        results.append(v)
    print(f"✅ Detected {len(results)} usable drive(s)")

    return results


# ------------------------------------------------------------
# macOS IMPLEMENTATION
# ------------------------------------------------------------
def detect_macos_volumes():
    volumes_root = Path("/Volumes")
    results = []

    if not volumes_root.exists():
        return results

    for vol in volumes_root.iterdir():
        if not vol.is_dir():
            continue
        if vol.name.startswith("Macintosh"):
            continue

        fs, size, internal = get_macos_disk_info(vol)
        results.append(
            {
                "path": str(vol),
                "label": vol.name,
                "filesystem": fs,
                "size_bytes": size,
                "internal": internal,
            }
        )

    return results


def get_macos_disk_info(path: Path):
    """(filesystem, total bytes, internal?) from diskutil; Nones if unknown."""
    try:
        import subprocess
        import plistlib

        info = plistlib.loads(
            subprocess.check_output(["diskutil", "info", "-plist", str(path)])
        )
        return info.get("FilesystemType"), info.get("TotalSize"), info.get("Internal")
    except Exception:
        return None, None, None


def filter_macos_sd_cards():
    results = []

    for v in detect_macos_volumes():
        path = Path(v["path"])
        size = v["size_bytes"]

        if not size_within_sd_range(size):
            continue
        if not has_camera_structure(path):
            continue

        results.append(v)

    return results


# ------------------------------------------------------------
# LINUX IMPLEMENTATION
# ------------------------------------------------------------
def detect_linux_volumes():
    mounts = []
    for base in (Path("/media"), Path("/mnt")):
        if base.exists():
            mounts += [p for p in base.rglob("*") if p.is_dir()]

    results = []

    for path in mounts:
        fs, size = get_linux_disk_info(path)
        results.append(
            {
                "path": str(path),
                "label": path.name,
                "filesystem": fs,
                "size_bytes": size,
            }
        )

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
        path = Path(v["path"])
        size = v["size_bytes"]

        if not size_within_sd_range(size):
            continue
        if not has_camera_structure(path):
            continue

        results.append(v)

    return results


# ------------------------------------------------------------
# ALL SOURCES (cards + local/USB disks + network drives)
# ------------------------------------------------------------
_MAC_NETWORK_FS = {"smbfs", "afpfs", "nfs", "webdav", "cifs"}
_CARD_FS = {"FAT", "FAT32", "EXFAT", "MSDOS"}


# STORAGE_BUS_TYPE values that mean "plugged in from outside"
_EXTERNAL_BUSES = {4, 7, 12, 13}  # 1394, USB, SD, MMC
_IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400


def _windows_bus_type(drive: str) -> int | None:
    """
    Bus the volume's disk is attached through (STORAGE_BUS_TYPE), e.g.
    7 = USB, 11 = SATA, 17 = NVMe. Windows reports USB hard disks as
    DRIVE_FIXED like internal disks, so this is what tells them apart.
    Needs no admin rights. None if it can't be read (e.g. network drives).
    """
    import struct

    letter = drive.rstrip("\\")[:2]
    try:
        handle = win32file.CreateFile(
            "\\\\.\\" + letter,
            0,
            win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )
    except Exception:
        return None
    try:
        # STORAGE_PROPERTY_QUERY: StorageDeviceProperty, PropertyStandardQuery
        out = win32file.DeviceIoControl(
            handle, _IOCTL_STORAGE_QUERY_PROPERTY, struct.pack("<III", 0, 0, 0), 1024
        )
        return struct.unpack_from("<I", out, 28)[0]  # STORAGE_DEVICE_DESCRIPTOR.BusType
    except Exception:
        return None
    finally:
        handle.Close()


def _windows_total_bytes(drive: str) -> int:
    """GetDiskFreeSpaceEx works for network shares; GetDiskFreeSpace overflows."""
    try:
        _, total, _ = win32api.GetDiskFreeSpaceEx(drive)
        return int(total)
    except Exception:
        return 0


def list_all_sources():
    """
    Every mounted volume a user might import from, each tagged with
    kind = "card" | "external" | "disk" | "network":
      card     — camera card (FAT/exFAT, card-sized)
      external — USB / FireWire / SD-bus drive that isn't a card
      disk     — internal disk of this computer
      network  — mapped network share
    Empty reader slots and optical drives are left out.
    """
    system = platform.system()
    out = []

    if system == "Windows":
        cards = {
            c["path"].rstrip("\\").upper()
            for c in filter_windows_sd_cards()
            if not c.get("is_virtual")
        }
        for d in win32api.GetLogicalDriveStrings().split("\x00"):
            if not d:
                continue
            dtype = win32file.GetDriveType(d)
            if dtype not in (
                win32file.DRIVE_REMOVABLE,
                win32file.DRIVE_FIXED,
                win32file.DRIVE_REMOTE,
            ):
                continue
            try:
                label, _, _, _, fs = win32api.GetVolumeInformation(d)
            except Exception:
                continue  # empty slot / disconnected share
            path = d.rstrip("\\")
            if dtype == win32file.DRIVE_REMOTE:
                kind = "network"
            elif path.upper() in cards:
                kind = "card"
            elif (
                dtype == win32file.DRIVE_REMOVABLE
                or _windows_bus_type(d) in _EXTERNAL_BUSES
            ):
                kind = "external"
            else:
                kind = "disk"
            out.append(
                {
                    "path": path,
                    "label": label,
                    "filesystem": fs,
                    "size_bytes": _windows_total_bytes(d),
                    "kind": kind,
                }
            )

    elif system == "Darwin":
        for v in detect_macos_volumes():
            fs = (v.get("filesystem") or "").lower()
            if fs in _MAC_NETWORK_FS:
                kind = "network"
            elif fs.upper() in _CARD_FS and size_within_sd_range(
                v.get("size_bytes") or 0
            ):
                kind = "card"
            elif v.get("internal") is False:
                kind = "external"
            else:
                kind = "disk"
            out.append({**v, "kind": kind})

    else:
        for v in detect_sd_cards():
            out.append({**v, "kind": "disk"})

    order = {"card": 0, "external": 1, "disk": 2, "network": 3}
    return sorted(out, key=lambda v: (order[v["kind"]], v["path"]))


# ------------------------------------------------------------
# UNIVERSAL ENTRY POINTS
# ------------------------------------------------------------
def detect_sd_cards(include_fixed: bool = False):
    system = platform.system().lower()

    if system == "windows":
        return filter_windows_sd_cards(include_fixed=include_fixed)
    elif system == "darwin":
        return filter_macos_sd_cards()
    elif system == "linux":
        return filter_linux_sd_cards()
    else:
        return []


def auto_select_sd_card(cards):
    """
    Auto-select if exactly one SD card is detected.
    """
    return cards[0] if len(cards) == 1 else None
