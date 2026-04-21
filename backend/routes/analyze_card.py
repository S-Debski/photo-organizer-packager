# backend/routes/analyze_card.py

import os
from utils.logging_bus import log_info
from photo_core.mapping.analyze_card import analyze_card

def api_analyze_card(ctx, payload):
    sd_root = payload.get("sd_card_path")

    if not sd_root or not os.path.isdir(sd_root):
        return {"success": False, "error": "Invalid sd_card_path"}, 400

    ctx.state["current_sd_root"] = sd_root
    ctx.state["current_active_folder"] = sd_root
    ctx.thumb_cache.clear()
    ctx.exif_cache.clear()

    log_info(ctx, f"Analyze start: {sd_root}")

    analysis = analyze_card(sd_root)

    log_info(ctx, f"Analyze complete: {len(analysis['folders'])} folders")

    return {
        "success": True,
        "analysis": analysis
    }