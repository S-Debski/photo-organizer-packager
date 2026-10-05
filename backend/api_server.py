# Role: Backend service / IPC boundary (see Stability Contract)

# =============================================================================
# File: backend/api_server.py
#
# Role:
#   Main Flask API server for Photo Organizer
#
# Responsibilities:
#   - Define API endpoints
#   - Route requests to backend modules
#   - Maintain shared application context (ctx)
#   - Start background worker threads
#
# Architecture:
#   Frontend (index.html + main.js)
#       → Flask routes (this file)
#       → Worker (exif_scanner)
#       → Mapping layer (photo_core)
# =============================================================================

from version import APP_VERSION, APP_NAME
ctx = None   # ✅ shared global context
import threading
import webbrowser
import os
import platform
from pathlib import Path


try:
    from tkinter import Tk, filedialog
except ImportError:
    Tk = None

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from photo_core.ctx.context import AppContext
from workers.exif_scanner import exif_scanner_worker

# Routes
from backend.routes.analyze_card import api_analyze_card
from backend.routes.set_active_folder import api_set_active_folder
from backend.routes.gps_data import api_gps_data
from backend.routes.thumbs import api_thumbs, api_photo_proxy, api_full_image
from backend.routes.write_gps import api_write_gps

from backend.services.sdcard import detect_sd_cards, auto_select_sd_card

# Session state (v3.0)
from photo_core.pre_import.session_state import (
    create_session,
    load_session,
    save_session,
    register_asset,
    set_asset_selected,
    get_selected_assets,
    mark_asset_copied,
    session_summary,
)

from workers.copy_worker import start_copy_worker

import pythoncom
import logging

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logger = logging.getLogger("api_server")

# -----------------------------------------------------------------------------
# Paths (CRITICAL — DO NOT REMOVE)
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]

print("BASE_DIR =", BASE_DIR)
print("TEMPLATES =", BASE_DIR / "templates")
print("STATIC =", BASE_DIR / "ui" / "static")

# -----------------------------------------------------------------------------
# Flask app
# -----------------------------------------------------------------------------
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "ui" / "static"),
    static_url_path="/static"
)

app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

CORS(app)

# Shared application context
ctx: AppContext | None = None


# -----------------------------------------------------------------------------
# Activity tracking
# -----------------------------------------------------------------------------
def touch_activity():
    if ctx:
        ctx.state["last_activity"] = ctx.state.get("last_activity", 0) + 1


# -----------------------------------------------------------------------------
# Index route
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    touch_activity()
    from version import APP_VERSION, APP_NAME

    ...

    return render_template(
        'index.html',
        version=APP_VERSION,
        app_name=APP_NAME
    )

# -----------------------------------------------------------------------------
# Filter cloud drives etc
# -----------------------------------------------------------------------------
def filter_drives(drives):
    filtered = []
    for d in drives:
        if d.get("is_virtual"):
            continue
        filtered.append(d)
    return filtered

# -----------------------------------------------------------------------------
# SD card detection
# -----------------------------------------------------------------------------
@app.route("/api/sd-cards", methods=["GET"])
def api_sd_cards():
    try:
        include_virtual = request.args.get("includeVirtual") == "true"
        drives = detect_sd_cards()
        if not include_virtual:
            drives = filter_drives(drives)
        return jsonify({"success": True, "drives": drives})
    except Exception as e:
        print("SD detection error:", e)
        return jsonify({"success": False, "error": str(e), "drives": []})

# -----------------------------------------------------------------------------
# Analyze SD card
# -----------------------------------------------------------------------------
@app.route("/api/analyze-card", methods=["POST"])
def analyze_card():
    touch_activity()
    return api_analyze_card(ctx, request.json)

# -----------------------------------------------------------------------------
# Working Dir Browser
# -----------------------------------------------------------------------------
@app.route("/api/select-folder", methods=["GET"])
def select_folder():
    try:
        if Tk is None:
            return {"path": None, "error": "tkinter not available"}

        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        path = filedialog.askdirectory()
        root.destroy()

        if not path:
            return {"path": None}

        return {"path": path}

    except Exception as e:
        print("Folder picker error:", e)
        return {"path": None, "error": str(e)}

# -----------------------------------------------------------------------------
# Set active folder
# -----------------------------------------------------------------------------
@app.route("/api/set-active-folder", methods=["POST"])
def set_active_folder():
    touch_activity()
    return api_set_active_folder(request.json)

# =============================================================================
# /api/organize
#
# Copies selected photo files from source → destination.
#
# Destination subfolder structure:
#   <destination>/<camera_folder> - <drive_label>/
#       e.g.  testit/929_FUJI - Medburn/
#             testit/USB/
#
# camera_folder: first DCIM subfolder containing images (from ctx.state["title"])
# drive_label:   volume label of the source drive (from ctx.state["current_sd_root"])
#
# Only recognised photo file types are copied — video/system files skipped.
# =============================================================================
@app.route("/api/organize", methods=["POST"])
def api_organize():
    try:
        data = request.json
        source      = data.get("source")
        destination = data.get("destination")

        import shutil

        # ------------------------------------------------------------------
        # Build destination subfolder name from the source path.
        # source is now the specific folder tab path (e.g. G:\DCIM\929_FUJI\USB)
        # ------------------------------------------------------------------
        sd_root   = ctx.state.get("current_sd_root", "")
        dcim_path = os.path.join(sd_root, "DCIM") if sd_root else ""

        # Get drive label for suffix
        drive_label = ""
        if sd_root:
            try:
                import win32api
                vol_path = sd_root.rstrip("\\/ ") + "\\"
                drive_label = win32api.GetVolumeInformation(vol_path)[0] or ""
            except Exception:
                drive_label = os.path.basename(sd_root.rstrip("\\/ ")) or ""

        # Build camera folder name relative to DCIM
        # e.g. G:\DCIM\929_FUJI\USB -> "929_FUJI - USB"
        source_norm = os.path.normpath(source)
        if dcim_path and source_norm.lower().startswith(dcim_path.lower()):
            rel = os.path.relpath(source_norm, dcim_path)
            camera_folder = rel.replace(os.sep, " - ")
        else:
            camera_folder = os.path.basename(source_norm)

        if camera_folder and drive_label:
            subfolder = f"{camera_folder} - {drive_label}"
        elif camera_folder:
            subfolder = camera_folder
        else:
            subfolder = "Imported"

        dest_dir = os.path.join(destination, subfolder)
        dest_dir = os.path.normpath(dest_dir)   # consistent backslashes on Windows
        os.makedirs(dest_dir, exist_ok=True)

        logger.info(f"Organize → {dest_dir}")

        # ------------------------------------------------------------------
        # Only copy recognised photo file types
        # Skips: .MTS .CPI .MPL .BIN (AVCHD/camera system files)
        # ------------------------------------------------------------------
        ALLOWED_EXTENSIONS = {
            ".jpg", ".jpeg",
            ".raf", ".raw", ".cr2", ".cr3",
            ".nef", ".arw", ".dng", ".orf", ".rw2",
            ".png", ".tif", ".tiff",
            ".xmp",
        }

        copied = []
        session = ctx.state.get("session")

        if session:
            # ── Session-driven copy: only selected (kept) assets ──────────────
            from photo_core.pre_import.session_state import get_selected_assets
            selected = get_selected_assets(session)

            if selected:
                for asset_id, asset in selected.items():
                    for key in ("raw_source", "jpg_source"):
                        src_path = asset.get(key)
                        if not src_path:
                            continue
                        src_path = os.path.normpath(src_path)
                        if not os.path.isfile(src_path):
                            continue
                        ext = os.path.splitext(src_path)[1].lower()
                        if ext not in ALLOWED_EXTENSIONS:
                            continue
                        dst_path = os.path.join(dest_dir, os.path.basename(src_path))
                        if os.path.exists(dst_path):
                            continue
                        shutil.copy2(src_path, dst_path)
                        copied.append(os.path.basename(src_path))

                    # ── RAW fallback: session raw_source may be null if scanner
                    # ran before session was created. Derive RAW path from JPG. ──
                    if not asset.get("raw_source") and asset.get("jpg_source"):
                        jpg_norm = os.path.normpath(asset["jpg_source"])
                        stem = os.path.splitext(jpg_norm)[0]
                        for raw_ext in (".raf", ".raw", ".cr2", ".cr3", ".nef",
                                        ".arw", ".dng", ".orf", ".rw2"):
                            candidate = stem + raw_ext
                            if os.path.isfile(candidate):
                                dst_path = os.path.join(dest_dir, os.path.basename(candidate))
                                if not os.path.exists(dst_path):
                                    shutil.copy2(candidate, dst_path)
                                    copied.append(os.path.basename(candidate))
                                    logger.debug(f"RAW fallback copy: {candidate}")
                                break
            else:
                # No assets selected — fall through to full walk
                logger.info("organize: session active but no selected assets — importing all")
                for root, _, files in os.walk(source):
                    for f in files:
                        if os.path.splitext(f)[1].lower() not in ALLOWED_EXTENSIONS:
                            continue
                        src_path = os.path.join(root, f)
                        dst_path = os.path.join(dest_dir, f)
                        if os.path.exists(dst_path):
                            continue
                        shutil.copy2(src_path, dst_path)
                        copied.append(f)

        else:
            # ── No session: use kept_paths if sent, else full walk ────────────
            kept_paths = data.get("kept_paths")

            if kept_paths:
                for src_path in kept_paths:
                    src_path = os.path.normpath(src_path)
                    if not os.path.isfile(src_path):
                        continue
                    f = os.path.basename(src_path)
                    if os.path.splitext(f)[1].lower() not in ALLOWED_EXTENSIONS:
                        continue
                    dst_path = os.path.join(dest_dir, f)
                    if os.path.exists(dst_path):
                        continue
                    shutil.copy2(src_path, dst_path)
                    copied.append(f)
            else:
                for root, _, files in os.walk(source):
                    for f in files:
                        if os.path.splitext(f)[1].lower() not in ALLOWED_EXTENSIONS:
                            continue
                        src_path = os.path.join(root, f)
                        dst_path = os.path.join(dest_dir, f)
                        if os.path.exists(dst_path):
                            continue
                        shutil.copy2(src_path, dst_path)
                        copied.append(f)

        return {"success": True, "count": len(copied), "destination": dest_dir}

    except Exception as e:
        logger.exception("organize failed")
        return {"success": False, "error": str(e)}

# -----------------------------------------------------------------------------
# Thumbnails
# -----------------------------------------------------------------------------
@app.route("/api/thumbs", methods=["POST"])
def thumbs():
    if not ctx.state.get("copy_complete"):
        return jsonify([])
    return api_thumbs(ctx, request.json)

# -----------------------------------------------------------------------------
# Progress (read)
# -----------------------------------------------------------------------------
@app.route("/api/progress")
def api_progress():
    touch_activity()
    return jsonify(getattr(ctx, "progress", {
        "stage": "idle",
        "total": 0,
        "done": 0,
        "active": False,
        "message": ""
    }))

# -----------------------------------------------------------------------------
# Write progress
# -----------------------------------------------------------------------------
@app.route("/api/write-progress")
def get_write_progress():
    return jsonify(getattr(ctx, "write_progress", {
        "total": 0,
        "done": 0,
        "active": False
    }))

# -----------------------------------------------------------------------------
# Photo proxy
# -----------------------------------------------------------------------------
@app.route("/api/photo-proxy")
def photo_proxy():
    touch_activity()
    path = request.args.get("path")
    return api_photo_proxy(ctx, path)

# -----------------------------------------------------------------------------
# Full image
# -----------------------------------------------------------------------------
@app.route("/api/full-image")
def full_image():
    touch_activity()
    path = request.args.get("path")
    return api_full_image(ctx, path)

# -----------------------------------------------------------------------------
# GPS data
# -----------------------------------------------------------------------------
@app.route("/api/gps-data", methods=["POST"])
def gps_data():
    touch_activity()
    return api_gps_data(ctx)

# -----------------------------------------------------------------------------
# Write GPS
# -----------------------------------------------------------------------------
@app.route("/api/write-gps", methods=["POST"])
def write_gps():
    return api_write_gps(ctx, request.json)

# -----------------------------------------------------------------------------
# Working directory setter
# -----------------------------------------------------------------------------
@app.route("/api/set-working-dir", methods=["POST"])
def set_working_dir():
    data = request.json
    path = data.get("path")

    if not os.path.isdir(path):
        return jsonify({"error": "Invalid path"}), 400

    ctx.working_base_dir = path
    return jsonify({"success": True})


# =============================================================================
# SESSION ENDPOINTS (v3.0)
# =============================================================================

# -----------------------------------------------------------------------------
# POST /api/session/create
# -----------------------------------------------------------------------------
# Creates a new ingest session for the given source folder.
#
# Request JSON:
#   {
#       "source_folder": "/path/to/SD/DCIM",
#       "session_name":  "Wedding_2024"        ← optional, defaults to timestamp
#   }
#
# Response JSON:
#   {
#       "success":      true,
#       "session_id":   "Wedding_2024_20240615_143012",
#       "session_dir":  "/path/to/sessions/Wedding_2024_20240615_143012"
#   }
# -----------------------------------------------------------------------------
@app.route("/api/session/create", methods=["POST"])
def api_session_create():
    try:
        data = request.json or {}
        source_folder = data.get("source_folder") or ctx.state.get("current_sd_root")
        session_name  = data.get("session_name", "Session")

        if not source_folder:
            return jsonify({"success": False, "error": "source_folder is required"}), 400

        session_dir, session_data = create_session(
            base_dir=ctx.sessions_root,
            source_folder=source_folder,
            session_name=session_name,
        )

        ctx.state["session"]     = session_data
        ctx.state["session_dir"] = session_dir

        logger.info(f"Session created: {session_data['session_id']}")

        return jsonify({
            "success":     True,
            "session_id":  session_data["session_id"],
            "session_dir": session_dir,
        })

    except Exception as e:
        logger.exception("session/create failed")
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500


# -----------------------------------------------------------------------------
# GET /api/session/status
# -----------------------------------------------------------------------------
# Returns a lightweight summary of the active session for UI display.
#
# Response JSON:
#   {
#       "active":          true,
#       "session_id":      "Wedding_2024_20240615_143012",
#       "source_folder":   "/path/to/DCIM",
#       "total_assets":    142,
#       "selected":        87,
#       "rejected":        55,
#       "copied_complete": 0
#   }
# -----------------------------------------------------------------------------
@app.route("/api/session/status", methods=["GET"])
def api_session_status():
    session = ctx.state.get("session")

    if not session:
        return jsonify({"active": False})

    summary = session_summary(session)
    return jsonify({"active": True, **summary})


# -----------------------------------------------------------------------------
# POST /api/session/select
# -----------------------------------------------------------------------------
# Persist a keep/reject culling decision for one asset.
#
# Request JSON:
#   {
#       "asset_id": "DSCF0001",
#       "selected": true          ← true = keep, false = reject
#   }
#
# Response JSON:
#   { "success": true }
# -----------------------------------------------------------------------------
@app.route("/api/session/select", methods=["POST"])
def api_session_select():
    try:
        session     = ctx.state.get("session")
        session_dir = ctx.state.get("session_dir")

        if not session:
            return jsonify({"success": False, "error": "No active session"}), 400

        data      = request.json or {}
        asset_id  = data.get("asset_id")
        selected  = bool(data.get("selected", True))

        if not asset_id:
            return jsonify({"success": False, "error": "asset_id is required"}), 400

        set_asset_selected(session, asset_id, selected)
        save_session(session_dir, session)   # persist every cull — cheap + resumable

        return jsonify({"success": True})

    except Exception as e:
        logger.exception("session/select failed")
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# POST /api/session/register-asset
# -----------------------------------------------------------------------------
# Register a RAW/JPG pair discovered during scan.
# Called by the scan pipeline — not typically called from the frontend directly.
#
# Request JSON:
#   {
#       "asset_id":   "DSCF0001",
#       "raw_source": "/SD/DCIM/DSCF0001.RAF",   ← null if no RAW
#       "jpg_source": "/SD/DCIM/DSCF0001.JPG"    ← null if no JPG
#   }
# -----------------------------------------------------------------------------
@app.route("/api/session/register-asset", methods=["POST"])
def api_session_register_asset():
    try:
        session     = ctx.state.get("session")
        session_dir = ctx.state.get("session_dir")

        if not session:
            return jsonify({"success": False, "error": "No active session"}), 400

        data       = request.json or {}
        asset_id   = data.get("asset_id")
        raw_source = data.get("raw_source")
        jpg_source = data.get("jpg_source")

        if not asset_id:
            return jsonify({"success": False, "error": "asset_id is required"}), 400

        register_asset(session, asset_id, raw_source=raw_source, jpg_source=jpg_source)
        # Note: save is intentionally NOT called per-asset during bulk scan.
        # The scan pipeline calls save_session() once at end of scan pass.

        return jsonify({"success": True})

    except Exception as e:
        logger.exception("session/register-asset failed")
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# GET /api/session/selected
# -----------------------------------------------------------------------------
# Return all keeper assets. Used before kicking off the copy worker.
#
# Response JSON:
#   {
#       "success": true,
#       "assets": {
#           "DSCF0001": { "raw_source": "...", "jpg_source": "...", ... },
#           ...
#       }
#   }
# -----------------------------------------------------------------------------
@app.route("/api/session/selected", methods=["GET"])
def api_session_selected():
    session = ctx.state.get("session")

    if not session:
        return jsonify({"success": False, "error": "No active session"}), 400

    keepers = get_selected_assets(session)
    return jsonify({"success": True, "assets": keepers})


# -----------------------------------------------------------------------------
# POST /api/session/close
# -----------------------------------------------------------------------------
# Clears the active session from runtime state.
# Does NOT delete the session folder on disk (preserves manifest for recovery).
# -----------------------------------------------------------------------------
@app.route("/api/session/close", methods=["POST"])
def api_session_close():
    ctx.state["session"]     = None
    ctx.state["session_dir"] = None
    logger.info("Session closed")
    return jsonify({"success": True})



# -----------------------------------------------------------------------------
# POST /api/session/copy
# -----------------------------------------------------------------------------
# Starts the async copy worker for the active session.
# Copies only selected (keeper) assets from source → session/RAW + session/JPG
#
# Response JSON:
#   { "success": true,  "message": "Copy started — 42 assets queued" }
#   { "success": false, "error":   "No active session" }
# -----------------------------------------------------------------------------
@app.route("/api/session/copy", methods=["POST"])
def api_session_copy():
    try:
        started = start_copy_worker(ctx)

        if not started:
            # Distinguish between common failure reasons for better UI feedback
            session = ctx.state.get("session")
            if not session:
                return jsonify({"success": False, "error": "No active session"}), 400
            if ctx.progress.get("active"):
                return jsonify({"success": False, "error": "Operation already in progress"}), 409

            from photo_core.pre_import.session_state import get_selected_assets
            keepers = get_selected_assets(session)
            if not keepers:
                return jsonify({"success": False, "error": "No assets selected — cull your photos first"}), 400

            return jsonify({"success": False, "error": "Copy could not start"}), 500

        from photo_core.pre_import.session_state import get_selected_assets
        keepers = get_selected_assets(ctx.state["session"])
        return jsonify({
            "success": True,
            "message": f"Copy started — {len(keepers)} assets queued"
        })

    except Exception as e:
        logger.exception("session/copy failed")
        return jsonify({"success": False, "error": str(e)}), 500




# -----------------------------------------------------------------------------
# Pictures folder opener (default output dir)
# -----------------------------------------------------------------------------
@app.route("/api/pictures-open")
def api_pictures_open():
    return _open_folder_in_explorer(ctx.output_dir)


# -----------------------------------------------------------------------------
# POST /api/open-folder
# -----------------------------------------------------------------------------
# Opens any specific folder in the OS file explorer.
# Used by "Open destination folder" after import to open the exact subfolder.
#
# Request JSON:
#   { "path": "C:/Temp/testit/929_FUJI - Medburn" }
# -----------------------------------------------------------------------------
@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    data = request.json or {}
    path = data.get("path", "").strip()

    if not path:
        return jsonify({"success": False, "error": "No path provided"}), 400
    if not os.path.isdir(path):
        return jsonify({"success": False, "error": f"Directory not found: {path}"}), 404

    return _open_folder_in_explorer(path)


def _open_folder_in_explorer(path: str):
    """Open a folder in the OS native file explorer."""
    import subprocess
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return jsonify({"success": True, "path": path})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# =============================================================================
# Server runner
# =============================================================================
def run_api_server(app_ctx):
    global ctx
    ctx = app_ctx

    # Start EXIF scanner worker
    threading.Thread(
        target=exif_scanner_worker,
        args=(ctx,),
        daemon=True,
    ).start()

    # Open browser once
    threading.Timer(
        1.0,
        lambda: webbrowser.open_new("http://127.0.0.1:5000")
    ).start()

    # Run Flask
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )