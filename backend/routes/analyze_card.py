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
    sd_root = payload.get("sd_card_path")

    if not sd_root or not os.path.isdir(sd_root):
        return {"success": False, "error": "Invalid sd_card_path"}, 400

    # Required state updates
    ctx.state["current_sd_root"] = sd_root
    # ❌ REMOVE this line entirely
    # ctx.state["current_active_folder"] = sd_root    # TEMP: hardcoded test location (Butley Village Hall)
    ctx.state["folder_location"] = (52.1072, 1.4575)

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
