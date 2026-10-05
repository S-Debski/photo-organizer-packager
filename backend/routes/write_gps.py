# ============================================================================
# Role: Post‑Organize metadata mutation handler (see Stability Contract)
#
# File: write_gps.py
#
# Responsibilities:
#   - Apply GPS EXIF metadata to images
#   - Operate ONLY on working directory files
#   - Skip unsupported formats (e.g. RAW files)
#   - Provide clear logging and failure reporting
#
# Notes:
#   - Called AFTER working directory is populated
#   - Must never touch source (SD card) files
#   - Must be safe to re-run
# ============================================================================

import subprocess
from flask import jsonify
from pathlib import Path

def api_write_gps(ctx, payload):
    files = payload.get("files")
    lat = payload.get("lat")
    lon = payload.get("lon")

    # ✅ Validate input (prevents 400 cases)
    if not files or lat is None or lon is None:
        print("❌ Invalid payload:", payload)
        return jsonify({"success": False, "error": "Invalid input"}), 400

    # ✅ Get working directory from context
    working_dir = getattr(ctx, "working_dir", None)

    if not working_dir:
        print("❌ No working directory set in ctx")
        return jsonify({"success": False, "error": "No working directory set"}), 400

    working_dir = Path(working_dir)

    updated = 0
    failed = []
    skipped = []

    # ✅ INIT progress state
    ctx.write_progress = {
        "total": len(files),
        "done": 0,
        "active": True
    }

    print(f"📡 Starting GPS write for {len(files)} files")
    print(f"📁 Working directory: {working_dir}")

    # ✅ acquire lock BEFORE writing
    with ctx.scan_lock:

        for original in files:
            try:
                target_path = Path(original)

                if not target_path.exists():
                    print(f"⚠️ File not found: {target_path}")
                    failed.append(str(target_path))
                    continue

                print(f"✏️ Writing GPS → {target_path.name}")

                result = subprocess.run([
                    "exiftool",
                    "-overwrite_original",
                    f"-GPSLatitude={lat}",
                    f"-GPSLongitude={lon}",
                    str(target_path)
                ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )

                if result.returncode != 0:
                    print(f"❌ Exiftool failed on {target_path}")
                    print(result.stderr)
                    failed.append(str(target_path))
                    continue

                updated += 1

            except Exception as e:
                print("❌ EXIF write exception:", original, e)
                failed.append(str(original))

            ctx.write_progress["done"] += 1

    print(f"✅ GPS write complete: {updated} updated, {len(skipped)} skipped, {len(failed)} failed")
    ctx.write_progress["active"] = False

    return jsonify({
        "success": updated > 0,
        "updated": updated,
        "skipped": skipped,
        "failed": failed
    })