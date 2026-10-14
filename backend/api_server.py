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
import time
import webbrowser
import os
import platform
from pathlib import Path


try:
    from tkinter import Tk, filedialog
except ImportError:
    Tk = None

from flask import Flask, request, jsonify, render_template

from photo_core.ctx.context import AppContext
from workers.exif_scanner import exif_scanner_worker

# Routes
from backend.routes.analyze_card import api_analyze_card
from backend.routes.set_active_folder import api_set_active_folder
from backend.routes.gps_data import api_gps_data
from backend.routes.thumbs import api_thumbs, api_thumb, api_photo_proxy, api_full_image
from backend.routes.write_gps import api_write_gps, write_gps_tags

from backend.services.sdcard import detect_sd_cards

# Session state (v3.0)
from photo_core.pre_import.session_state import (
    create_session,
    save_session,
    register_asset,
    set_asset_selected,
    get_selected_assets,
    mark_asset_copied,
    session_summary,
    set_asset_decision,
    get_decisions,
    find_latest_session,
    register_paths,
    RAW_EXTENSIONS,
    JPG_EXTENSIONS,
)
from utils.fs_utils import iter_images, IMAGE_EXTS_ALL

from workers.copy_worker import start_copy_worker

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

# No CORS: the UI is same-origin. CORS(app) let any website read local
# files through /api/photo-proxy while the app was running.

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
        if platform.system() == "Darwin":
            # Tk windows must be created on the main thread on macOS (this
            # runs on a Flask worker thread), so use the native picker.
            import subprocess
            proc = subprocess.run(
                ["osascript", "-e",
                 'POSIX path of (choose folder with prompt "Choose destination folder")'],
                capture_output=True, text=True,
            )
            path = proc.stdout.strip()
            return {"path": path.rstrip("/") or None}

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
        ALLOWED_EXTENSIONS = {*IMAGE_EXTS_ALL, ".png", ".tif", ".tiff", ".xmp"}

        # ------------------------------------------------------------------
        # Decide which files to copy.
        #   mode "kept": only the kept files the UI sent, plus same-stem
        #                partners/sidecars (RAW, JPG, .xmp) in the same folder
        #   mode "all":  every recognised file under source
        # Never fall back from "kept" to "all" — that imported rejects.
        # ------------------------------------------------------------------
        kept_paths = data.get("kept_paths") or []
        mode = data.get("mode") or ("kept" if kept_paths else "all")

        if mode == "kept":
            if not kept_paths:
                return {"success": False,
                        "error": "No photos are marked Keep. Cull first, or choose Import all."}
            candidates = _with_same_stem_siblings(kept_paths)
        else:
            candidates = [os.path.join(root, f)
                          for root, _, files in os.walk(source) for f in files]

        files = [p for p in candidates
                 if os.path.splitext(p)[1].lower() in ALLOWED_EXTENSIONS
                 and os.path.isfile(p)]

        # ------------------------------------------------------------------
        # Copy with progress (polled by the UI via /api/progress)
        # ------------------------------------------------------------------
        if ctx.progress.get("active"):
            return {"success": False, "error": "Another import is already running"}

        # GPS assigned in the Mapping step (source path → lat/lon). It is
        # written into the imported JPG copies only — never to the card.
        gps_by_source = {}
        for g in data.get("gps") or []:
            try:
                gps_by_source[os.path.normcase(os.path.normpath(g["path"]))] = (
                    float(g["lat"]), float(g["lon"]))
            except (KeyError, TypeError, ValueError):
                continue

        ctx.progress.update(stage="import", total=len(files), done=0,
                            active=True, message=f"Importing {len(files)} files…")
        copied, skipped, errors = [], [], []
        gps_written = 0
        session = ctx.state.get("session")

        try:
            for src_path in files:
                f = os.path.basename(src_path)
                dst_path = os.path.join(dest_dir, f)
                try:
                    if os.path.exists(dst_path):
                        skipped.append(f)
                    else:
                        shutil.copy2(src_path, dst_path)
                        copied.append(f)

                        gps = gps_by_source.get(os.path.normcase(os.path.normpath(src_path)))
                        if gps and os.path.splitext(f)[1].lower() in JPG_EXTENSIONS:
                            result = write_gps_tags(dst_path, *gps)
                            if result.returncode == 0:
                                gps_written += 1
                            else:
                                errors.append(f"{f}: GPS write failed — {result.stderr.strip()}")
                    if session:
                        _mark_session_copied(session, f, dst_path)
                except OSError as e:
                    errors.append(f"{f}: {e}")
                    logger.error(f"organize: copy failed {src_path} → {e}")
                ctx.progress["done"] += 1
        finally:
            ctx.progress.update(stage="idle", active=False,
                                message=f"Imported {len(copied)} files")

        if session:
            session.setdefault("imports", []).append({
                "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "mode": mode,
                "destination": dest_dir,
                "copied": len(copied),
                "skipped_existing": len(skipped),
                "errors": len(errors),
            })
            try:
                save_session(ctx.state["session_dir"], session)
            except Exception as e:
                logger.error(f"organize: session save failed — {e}")

        return {
            "success": not errors,
            "count": len(copied),
            "skipped": len(skipped),
            "gps_written": gps_written,
            "errors": errors[:20],
            "error": f"{len(errors)} file(s) failed to copy" if errors else None,
            "destination": dest_dir,
        }

    except Exception as e:
        logger.exception("organize failed")
        return {"success": False, "error": str(e)}


def _file_stem(name: str) -> str:
    """Stem up to the first dot, upper-cased: DSCF0001.RAF.xmp → DSCF0001."""
    return os.path.basename(name).split(".", 1)[0].upper()


def _with_same_stem_siblings(paths: list[str]) -> list[str]:
    """
    Expand kept files to include every file in the same folder sharing the
    stem — the RAW/JPG partner and sidecars such as .xmp.
    """
    wanted: dict[str, set[str]] = {}
    for p in paths:
        p = os.path.normpath(p)
        wanted.setdefault(os.path.dirname(p), set()).add(_file_stem(p))

    result = []
    for folder, stems in wanted.items():
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        result.extend(os.path.join(folder, n) for n in names if _file_stem(n) in stems)
    return sorted(set(result))


def _mark_session_copied(session: dict, filename: str, dst_path: str) -> None:
    """Record a copied RAW/JPG against its session asset (matched by stem)."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in RAW_EXTENSIONS:
        filetype = "raw"
    elif ext in JPG_EXTENSIONS:
        filetype = "jpg"
    else:
        return

    stem = _file_stem(filename)
    for asset_id in session.get("assets", {}):
        if asset_id.upper() == stem:
            mark_asset_copied(session, asset_id, filetype, dst_path)
            return

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
# Per-file EXIF summary (camera, lens, date) for the stats step
# -----------------------------------------------------------------------------
@app.route("/api/exif-records")
def exif_records():
    records = ctx.state.get("exif_records") or []
    return jsonify({
        "ready": bool(records),
        "records": [
            {k: r.get(k) for k in ("path", "camera_model", "lens", "datetime")}
            for r in records
        ],
    })

# -----------------------------------------------------------------------------
# Cached thumbnail / preview (size: grid | strip | preview)
# -----------------------------------------------------------------------------
@app.route("/api/thumb")
def thumb():
    return api_thumb(ctx, request.args.get("path"), request.args.get("size", "grid"))

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

        # Resume the latest session for this folder if one exists on disk,
        # so culling decisions survive an app restart.
        existing = None if data.get("new") else find_latest_session(
            ctx.sessions_root, source_folder)

        if existing:
            session_dir, session_data = existing
            logger.info(f"Session resumed: {session_data['session_id']}")
        else:
            session_dir, session_data = create_session(
                base_dir=ctx.sessions_root,
                source_folder=source_folder,
                session_name=session_name,
            )

        # Register every RAW/JPG pair now, so culling decisions made before
        # the EXIF scanner's next pass are never dropped as unknown assets.
        if os.path.isdir(source_folder):
            register_paths(session_data, iter_images(source_folder))
            save_session(session_dir, session_data)

        ctx.state["session"]     = session_data
        ctx.state["session_dir"] = session_dir

        logger.info(f"Session created: {session_data['session_id']} "
                    f"({len(session_data['assets'])} assets)")

        return jsonify({
            "success":     True,
            "resumed":     bool(existing),
            "session_id":  session_data["session_id"],
            "session_dir": session_dir,
            "decisions":   get_decisions(session_data),
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
    return jsonify({"active": True, **summary, "decisions": get_decisions(session)})


# -----------------------------------------------------------------------------
# POST /api/session/select
# -----------------------------------------------------------------------------
# Persist a keep/reject culling decision for one asset.
#
# Request JSON:
#   {
#       "asset_id": "DSCF0001",
#       "decision": "keep"        ← "keep" | "reject" | null (unculled)
#       (legacy: "selected": true/false)
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

        if not asset_id:
            return jsonify({"success": False, "error": "asset_id is required"}), 400

        if "decision" in data:
            # "keep" | "reject" | null (unculled)
            set_asset_decision(session, asset_id, data["decision"])
        else:
            set_asset_selected(session, asset_id, bool(data.get("selected", True)))
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
HOST = "127.0.0.1"
PORT = int(os.environ.get("FLASK_PORT", 5000))
APP_URL = f"http://{HOST}:{PORT}"


def open_ui():
    webbrowser.open_new(APP_URL)


def start_api_server(app_ctx, open_browser=True) -> threading.Thread:
    """
    Start the EXIF worker and Flask in background threads and return the
    Flask thread. The caller owns the main thread (tray icon on desktop
    builds — macOS requires UI on the main thread).
    """
    global ctx
    ctx = app_ctx

    # Start EXIF scanner worker
    threading.Thread(
        target=exif_scanner_worker,
        args=(ctx,),
        daemon=True,
    ).start()

    if open_browser:
        threading.Timer(1.0, open_ui).start()

    server = threading.Thread(
        target=lambda: app.run(host=HOST, port=PORT, debug=False,
                               use_reloader=False, threaded=True),
        daemon=True,
        name="flask",
    )
    server.start()
    return server


def run_api_server(app_ctx):
    """Blocking variant: run until the Flask thread exits."""
    start_api_server(app_ctx).join()