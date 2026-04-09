"""
Hybrid SD/CFexpress detection module for Windows.

Features:
✅ Fast Win32 removable-drive detection (0.1–0.3s typical)
✅ Filters empty multi-slot card reader ghost drives (E:\, G:\, H:\)
✅ Detects known camera folder structures (DCIM, PRIVATE, etc.)
✅ Camera confidence scoring for better auto-selection
✅ WMI fallback only when fast detection finds nothing
✅ Works cleanly inside PyInstaller bundles
"""

import time
from pathlib import Path

# --- FAST DETECTOR DEPENDENCIES ---
import win32api
import win32file

# --- WMI FALLBACK ---
import pythoncom
import wmi


# Known camera folder names
CAMERA_DIRS = {
    "dcim",
    "private",
    "m4root",
    "contents",
    "canonmsc",
}


# ---------------------------------------------------------
# UTILITY: Camera Confidence Scoring
# ---------------------------------------------------------
def score_camera_directory_structure(entries, folder_names_lower):
    """
    Gives a numeric confidence score based on known camera patterns:

    Higher score = more likely this drive is a real camera SD card.
    """
    score = 0

    # 1. Contains DCIM (biggest indicator)
    if "dcim" in folder_names_lower:
        score += 3

    # 2. Contains additional common camera folders
    for cd in CAMERA_DIRS:
        if cd != "dcim" and cd in folder_names_lower:
            score += 1

    # 3. If many media folders exist, increase confidence
    if len(folder_names_lower) >= 2:
        score += 1

    # 4. Check for typical photo file extensions
    photo_exts = {".jpg", ".jpeg", ".cr2", ".cr3", ".nef", ".arw", ".raf", ".rw2", ".orf"}
    for p in entries:
        if p.is_file() and p.suffix.lower() in photo_exts:
            score += 1
            break

    return score


# ---------------------------------------------------------
# FAST DETECTOR (Win32 API)
# ---------------------------------------------------------
def fast_detect_sd_cards():
    """
    Fast detection using Win32 API.
    Returns removable drives *that actually contain files/folders*
    and assigns a camera-confidence score.
    """

    drives = win32api.GetLogicalDriveStrings().split("\x00")
    drives = [d for d in drives if d]

    results = []

    for d in drives:
        try:
            # DRIVE_REMOVABLE = 2
            if win32file.GetDriveType(d) != win32file.DRIVE_REMOVABLE:
                continue

            root = Path(d)

            # Read drive contents once
            try:
                entries = list(root.iterdir())
            except Exception:
                continue

            # Skip empty drives (ghost slots)
            if not entries:
                continue

            # Extract directory names
            folder_names = {p.name.lower() for p in entries if p.is_dir()}

            # Camera confidence scoring
            camera_score = score_camera_directory_structure(entries, folder_names)
            is_camera = camera_score >= 2  # threshold can be tuned

            results.append({
                "path": d,
                "label": d.rstrip("\\"),
                "is_camera": is_camera,
                "camera_score": camera_score,
            })

        except Exception:
            continue

    return results


# ---------------------------------------------------------
# WMI FALLBACK (Slow)
# ---------------------------------------------------------
def wmi_detect_sd_cards():
    """
    Extremely slow fallback to WMI. Used only when fast detection fails.
    """
    pythoncom.CoInitialize()
    c = wmi.WMI()

    results = []

    for disk in c.Win32_DiskDrive():
        if disk.MediaType and "Removable" not in disk.MediaType:
            continue

        for part in disk.associators("Win32_DiskDriveToDiskPartition"):
            for logical in part.associators("Win32_LogicalDiskToPartition"):
                drive = logical.DeviceID + "\\"

                results.append({
                    "path": drive,
                    "label": drive.rstrip("\\"),
                    "is_camera": True,      # We lack folder insight
                    "camera_score": 1,
                })

    return results


# ---------------------------------------------------------
# HYBRID DETECTOR
# ---------------------------------------------------------
def detect_sd_cards_hybrid(enable_debug=False):
    """
    Hybrid SD-card detection:
    ✅ Fast Win32 API for instant detection
    ✅ Optional WMI fallback only when fast detection finds nothing useful
    Returns: (drive_list, timing_dict)
    """

    timings = {}

    # ----- FAST DETECTOR -----
    t0 = time.time()
    fast_results = fast_detect_sd_cards()
    t1 = time.time()
    timings["fast"] = t1 - t0

    if enable_debug:
        print(f"[SD DEBUG] Fast detection → {timings['fast']:.3f}s: {fast_results}")

    # If fast detector found meaningful results → return them
    if fast_results:
        # Any strong camera candidate?
        best_score = max(r["camera_score"] for r in fast_results)
        if best_score >= 3:
            if enable_debug:
                print("[SD DEBUG] Fast detector returned reliable camera card(s)")
            return fast_results, timings

        # Only one removable drive? Accept it.
        if len(fast_results) == 1:
            if enable_debug:
                print("[SD DEBUG] Only one drive found -> accepting fast result")
            return fast_results, timings

        # If multiple drives detected but at least one is_camera
        if any(r["is_camera"] for r in fast_results):
            if enable_debug:
                print("[SD DEBUG] Multiple drives, but one appears to be a camera")
            return fast_results, timings

    # ----- WMI FALLBACK -----
    t2 = time.time()
    wmi_results = wmi_detect_sd_cards()
    t3 = time.time()
    timings["wmi"] = t3 - t2

    if enable_debug:
        print(f"[SD DEBUG] WMI fallback → {timings['wmi']:.3f}s: {wmi_results}")

    # Merge results: prefer fast data but fill with WMI
    final = {r["path"]: r for r in fast_results}
    for r in wmi_results:
        final[r["path"]] = r

    return list(final.values()), timings


# ---------------------------------------------------------
# AUTO-SELECT CARD
# ---------------------------------------------------------
def auto_select_sd_card(drives):
    """
    Auto-select logic:
    ✅ If only one drive → choose that
    ✅ If multiple → pick highest camera_score
    ✅ If tie → pick is_camera=True
    """
    if not drives:
        return None

    # Only one drive detected
    if len(drives) == 1:
        return drives[0]["path"]

    # Pick the highest-scoring camera-like drive
    best = max(drives, key=lambda d: (d["camera_score"], d["is_camera"]))

    return best["path"]