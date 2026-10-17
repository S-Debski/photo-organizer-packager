# Role: SD card analysis engine (see Stability Contract)

# backend/routes/analyze_card.py

import os
from datetime import date

from utils.logging_bus import log_info
from photo_core.mapping.analyze_card import analyze_card


def derive_title_from_card(sd_root: str) -> str:
    """
    Derive a session title from a camera card structure.

    Preference:
    1. First folder directly under DCIM that contains images
    2. Fallback to drive / root name
    """
    dcim = os.path.join(sd_root, "DCIM")

    if os.path.isdir(dcim):
        for entry in sorted(os.listdir(dcim)):
            candidate = os.path.join(dcim, entry)
            if not os.path.isdir(candidate):
                continue

            for name in os.listdir(candidate):
                if name.lower().endswith((
                    ".jpg", ".jpeg", ".png",
                    ".arw", ".cr2", ".nef"
                )):
                    return entry

    # Fallback: drive / root name
    root = sd_root.rstrip("\\/")
    return os.path.basename(root) or root.rstrip(":")


def api_analyze_card(ctx, payload):
    sd_root = (payload.get("sd_card_path") or "").strip()

    # A bare drive ("F:") means the drive root; "F:" + "DCIM" would
    # otherwise resolve relative to the drive's current directory.
    if len(sd_root) == 2 and sd_root[1] == ":":
        sd_root += os.sep

    if not sd_root or not os.path.isdir(sd_root):
        return {"success": False, "error": "That card or folder isn't available."}, 400

    # Required state updates
    ctx.state["current_sd_root"] = sd_root

    # ✅ Session metadata for Pre‑Import
    ctx.state["title"] = derive_title_from_card(sd_root)
    ctx.state["shoot_date"] = date.today()

    # Clear dependent caches
    ctx.thumb_cache.clear()
    ctx.exif_cache.clear()

    log_info(ctx, f"Analyze start: {sd_root}")

    analysis = analyze_card(sd_root)

    log_info(ctx, f"Analyze complete: {len(analysis['folders'])} folders")

    return {
        "success": True,
        "analysis": analysis,
        "session": {
            "title": ctx.state["title"],
            "shoot_date": ctx.state["shoot_date"].isoformat()
        }
    }
