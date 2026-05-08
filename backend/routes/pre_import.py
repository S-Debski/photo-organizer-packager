# Role: Application module

# backend/routes/pre_import.py
from flask import jsonify, request
from pathlib import Path

from photo_core.pre_import.pre_import_flow import (
    preview_destination,
    PreImportError,
)

def api_preview_directory(ctx):
    """
    Preview the resolved destination directory.
    Safe to call repeatedly. Does not mutate ctx.
    """
    payload = request.json or {}
    template = payload.get("template")

    if not template:
        return jsonify({
            "success": False,
            "error": "Template is required",
        }), 400

    if not template:
        return jsonify({
            "success": False,
            "error": "Template is required",
        }), 400

    if not ctx.output_dir:
        return jsonify({
            "success": False,
            "error": "Output destination not selected yet.",
        }), 409

    if not ctx.session or not ctx.session.title or not ctx.session.shoot_date:
        return jsonify({
            "success": False,
            "error": "Session metadata not ready. Run Analyze Card first."
        }), 409

    try:
        title = ctx.state.get("title")
        shoot_date = ctx.state.get("shoot_date")

        if not title or not shoot_date:
            return jsonify({
                "success": False,
                "error": "Session metadata not ready. Run Analyze Card first."
            }), 409

        preview = preview_destination(
            output_root=Path(ctx.output_dir),
            template=template,
            title=title,
            shoot_date=shoot_date,
        )
    except PreImportError as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 400

    return jsonify({
        "success": True,
        "preview": str(preview),
    })

def api_set_output_destination(ctx):
    """
    Set the root output directory for Pre‑Import.
    """
    payload = request.json or {}
    path = payload.get("output_root")

    if not path:
        return jsonify({
            "success": False,
            "error": "output_root is required",
        }), 400

    # Normalise & store
    ctx.output_dir = str(Path(path))

    return jsonify({
        "success": True,
        "output_root": ctx.output_dir,
    })

def api_confirm_pre_import(ctx):
    payload = request.json or {}

    resolved = payload.get("resolved_destination")
    input_files = payload.get("input_files")

    if not resolved or input_files is None:
        return jsonify({
            "success": False,
            "error": "resolved_destination and input_files are required",
        }), 400

    # ✅ v2.8: confirmation only (no freezing yet)
    return jsonify({"success": True})

from datetime import date

def api_update_session_metadata(ctx):
    payload = request.json or {}

    title = payload.get("title")
    shoot_date = payload.get("shoot_date")

    if title is not None:
        ctx.state["title"] = title.strip()

    if shoot_date is not None:
        ctx.state["shoot_date"] = date.fromisoformat(shoot_date)

    return jsonify({
        "success": True,
        "title": ctx.state.get("title"),
        "shoot_date": ctx.state.get("shoot_date").isoformat()
    })