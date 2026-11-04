# ============================================================================
# Role: Post‑Organize metadata mutation handler (see Stability Contract)
#
# File: write_gps.py
#
# Responsibilities:
#   - Apply GPS EXIF metadata to images outside the source card/folder
#   - Defer source files: v3.0 browses the card in place, so GPS assigned
#     in Mapping is written to the imported copies by /api/organize
#   - Provide clear logging and failure reporting
#
# Notes:
#   - Must never touch source (SD card) files
#   - Must be safe to re-run
# ============================================================================

import os
import subprocess
from flask import jsonify
from pathlib import Path

from photo_core.exif.reader import resolve_exiftool_cmd, NO_WINDOW


def _protected_roots(ctx) -> list[str]:
    """Source locations that must never be written to (the card / browsed folder)."""
    session = ctx.state.get("session") or {}
    roots = [
        ctx.state.get("current_sd_root"),
        ctx.state.get("current_active_folder"),
        session.get("source_folder"),
    ]
    return [os.path.normcase(os.path.abspath(r)) for r in roots if r]


def is_source_path(ctx, path) -> bool:
    p = os.path.normcase(os.path.abspath(str(path)))
    for root in _protected_roots(ctx):
        try:
            if os.path.commonpath([p, root]) == root:
                return True
        except ValueError:   # different drives
            continue
    return False


def write_gps_tags(path, lat, lon) -> subprocess.CompletedProcess:
    """
    Write GPS to one file with exiftool.

    EXIF stores latitude/longitude unsigned; the hemisphere lives in the
    Ref tags. Passing the signed value to the Ref tags lets exiftool set
    N/S and E/W — without them a west longitude is read back as east.
    """
    cmd = resolve_exiftool_cmd() or "exiftool"
    return subprocess.run(
        [
            cmd,
            "-overwrite_original",
            f"-GPSLatitude={abs(float(lat))}",
            f"-GPSLatitudeRef={lat}",
            f"-GPSLongitude={abs(float(lon))}",
            f"-GPSLongitudeRef={lon}",
            os.path.abspath(str(path)),   # never starts with "-"
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=NO_WINDOW,
        stdin=subprocess.DEVNULL,
    )


def write_gps_sidecar(raw_path, lat, lon) -> subprocess.CompletedProcess:
    """
    Put GPS in the RAW's XMP sidecar (<stem>.xmp, the name Lightroom and
    most raw editors read) rather than inside the RAW file. Updates an
    existing sidecar in place, otherwise creates one.
    XMP stores signed decimal coordinates, so no N/S/E/W ref tags.
    """
    cmd = resolve_exiftool_cmd() or "exiftool"
    raw_path = os.path.abspath(str(raw_path))      # never starts with "-"
    sidecar = os.path.splitext(raw_path)[0] + ".xmp"
    tags = [f"-XMP-exif:GPSLatitude={float(lat)}", f"-XMP-exif:GPSLongitude={float(lon)}"]

    if os.path.isfile(sidecar):
        args = [cmd, "-q", "-overwrite_original", *tags, sidecar]
    else:
        args = [cmd, "-q", "-o", sidecar, *tags, raw_path]

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=NO_WINDOW,
        stdin=subprocess.DEVNULL,
    )


def api_write_gps(ctx, payload):
    files = payload.get("files")
    lat = payload.get("lat")
    lon = payload.get("lon")

    # ✅ Validate input (prevents 400 cases)
    if not files or lat is None or lon is None:
        print("❌ Invalid payload:", payload)
        return jsonify({"success": False, "error": "Invalid input"}), 400

    updated = 0
    failed = []
    skipped = []
    deferred = []

    # ✅ INIT progress state
    ctx.write_progress = {
        "total": len(files),
        "done": 0,
        "active": True
    }

    print(f"📡 Starting GPS write for {len(files)} files")

    # ✅ acquire lock BEFORE writing
    with ctx.scan_lock:

        for original in files:
            try:
                target_path = Path(original)

                # v3.0 browses the card in place — never write to source.
                # The UI keeps the GPS in metadataMap and /api/organize
                # writes it into the imported copies.
                if is_source_path(ctx, target_path):
                    deferred.append(str(target_path))
                    continue

                if not target_path.exists():
                    print(f"⚠️ File not found: {target_path}")
                    failed.append(str(target_path))
                    continue

                print(f"✏️ Writing GPS → {target_path.name}")

                result = write_gps_tags(target_path, lat, lon)

                if result.returncode != 0:
                    print(f"❌ Exiftool failed on {target_path}")
                    print(result.stderr)
                    failed.append(str(target_path))
                    continue

                updated += 1

            except Exception as e:
                print("❌ EXIF write exception:", original, e)
                failed.append(str(original))

            finally:
                ctx.write_progress["done"] += 1

    print(f"✅ GPS write complete: {updated} updated, {len(deferred)} deferred to import, "
          f"{len(failed)} failed")
    ctx.write_progress["active"] = False

    return jsonify({
        "success": (updated > 0 or bool(deferred)) and not failed,
        "updated": updated,
        "deferred": len(deferred),
        "skipped": skipped,
        "failed": failed
    })
