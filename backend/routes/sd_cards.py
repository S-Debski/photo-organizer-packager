# backend/routes/sd_cards.py
import os
import string
from flask import jsonify

def _win_drive_candidates():
    # C:\ .. Z:\
    for letter in string.ascii_uppercase:
        yield f"{letter}:\\"

def _has_dcim(drive):
    return os.path.isdir(os.path.join(drive, "DCIM"))

def api_sd_cards(ctx):
    drives = []
    auto_select = None

    # Try psutil first
    try:
        import psutil
        parts = psutil.disk_partitions(all=False)
        for p in parts:
            mp = p.mountpoint
            # Heuristic for removable: many SD cards have DCIM
            label = os.path.basename(mp.rstrip("\\/"))
            drives.append({"path": mp, "label": label})
        # Choose one with DCIM if found
        for d in drives:
            if _has_dcim(d["path"]):
                auto_select = d
                break

    except Exception:
        # Fallback: probe drive letters + DCIM
        for d in _win_drive_candidates():
            if os.path.isdir(d):
                label = "Drive"
                drives.append({"path": d, "label": label})
                if _has_dcim(d) and auto_select is None:
                    auto_select = {"path": d, "label": label}

    return jsonify({"success": True, "drives": drives, "auto_select": auto_select})