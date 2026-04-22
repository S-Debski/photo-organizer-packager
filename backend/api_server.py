# backend/api_server.py

import threading
import webbrowser

from flask import (
    Flask,
    jsonify,
    request,
    render_template,
)
from flask_cors import CORS

import pythoncom

# ------------------------------------------------------------
# Version info (imported from app.py – single source of truth)
# ------------------------------------------------------------
from version import APP_NAME, APP_VERSION, APP_STAGE, APP_BUILD
from backend.services.sdcard import detect_sd_cards, auto_select_sd_card
from backend.routes.pre_import import (
    api_preview_directory,
    api_confirm_pre_import,
)
## Check Exiftool is available ##
from photo_core.exif.reader import exiftool_available

if not exiftool_available():
    print("ℹ️ ExifTool not found — advanced lens metadata disabled")
##

# ------------------------------------------------------------
# Backend context + workers
# ------------------------------------------------------------
from photo_core.ctx.context import AppContext

# Routes
from backend.routes.analyze_card import api_analyze_card
from backend.routes.set_active_folder import api_set_active_folder
from backend.routes.exif_stats import api_exif_stats
from backend.routes.thumbs import api_thumbs, api_photo_proxy, api_full_image
from backend.routes.gps_data import api_gps_data
from backend.routes.organize import api_organize, api_job_status, api_open_pictures
from backend.routes.pre_import import api_set_output_destination

# ------------------------------------------------------------
# Flask app (single instance)
# ------------------------------------------------------------
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

print("BASE_DIR =", BASE_DIR)
print("STATIC_DIR =", BASE_DIR / "ui" / "static")

print("auto_select_sd_card signature:", auto_select_sd_card.__code__.co_argcount)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "ui" / "static"),
    static_url_path="/static"
)

# Dev-friendly: disable aggressive caching
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

CORS(app)

# Context is injected at runtime
ctx: AppContext | None = None

from backend.routes.pre_import import api_update_session_metadata
# version data #
@app.route("/api/pre-import/session", methods=["POST"])
def pre_import_update_session():
    touch_activity()
    return api_update_session_metadata(ctx)

# ------------------------------------------------------------
# Helper: activity tracking (optional future use)
# ------------------------------------------------------------
def touch_activity():
    if ctx:
        ctx.state["last_activity"] = ctx.state.get("last_activity", 0) + 1


# ------------------------------------------------------------
# Index
# ------------------------------------------------------------
@app.route("/")
def index():
    touch_activity()
    return render_template("index.html")
# ------------------------------------------------------------
# Pre import routes
# ------------------------------------------------------------
@app.route("/api/pre-import/preview", methods=["POST"])
def pre_import_preview():
    touch_activity()
    return api_preview_directory(ctx)

@app.route("/api/pre-import/confirm", methods=["POST"])
def pre_import_confirm():
    touch_activity()
    return api_confirm_pre_import(ctx)

# Output routes
@app.route("/api/pre-import/output-destination", methods=["POST"])
def pre_import_set_output():
    touch_activity()
    return api_set_output_destination(ctx)

# ------------------------------------------------------------
# Version API
# ------------------------------------------------------------
@app.route("/api/version")
def api_version():
    return jsonify({
        "name": APP_NAME,
        "version": APP_VERSION,
        "stage": APP_STAGE,
        "build": APP_BUILD
    })


# ------------------------------------------------------------
# SD card detection
# ------------------------------------------------------------
@app.route("/api/sd-cards")
def api_sd_cards():
    pythoncom.CoInitialize()
    touch_activity()

    try:
        drives = detect_sd_cards()
        return jsonify({
            "success": True,
            "drives": drives,
            "auto_select": auto_select_sd_card(drives)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ------------------------------------------------------------
# Analyze card
# ------------------------------------------------------------
@app.route("/api/analyze-card", methods=["POST"])
def analyze_card():
    touch_activity()
    return api_analyze_card(ctx, request.json)


# ------------------------------------------------------------
# Active folder
# ------------------------------------------------------------
@app.route("/api/set-active-folder", methods=["POST"])
def set_active_folder():
    touch_activity()
    return api_set_active_folder(ctx, request.json)


# ------------------------------------------------------------
# EXIF statistics
# ------------------------------------------------------------
@app.route("/api/exif-stats")
def exif_stats():
    touch_activity()
    return api_exif_stats(ctx)


# ------------------------------------------------------------
# Thumbnails & images
# ------------------------------------------------------------
@app.route("/api/thumbs")
def thumbs():
    touch_activity()
    return api_thumbs(ctx)


@app.route("/api/photo-proxy")
def photo_proxy():
    path = request.args.get("path")

    # ✅ Use the module-level AppContext
    return api_photo_proxy(ctx, path)

@app.route("/api/full-image")
def full_image():
    touch_activity()
    path = request.args.get("path")
    return api_full_image(ctx, path)


# ------------------------------------------------------------
# GPS data
# ------------------------------------------------------------
@app.route("/api/gps-data")
def gps_data():
    touch_activity()
    return api_gps_data(ctx)


# ------------------------------------------------------------
# Organize / copy job
# ------------------------------------------------------------
@app.route("/api/organize", methods=["POST"])
def organize():
    touch_activity()
    return api_organize(ctx)


@app.route("/api/job-status")
def job_status():
    touch_activity()
    return api_job_status(ctx)


@app.route("/api/pictures-open")
def pictures_open():
    return api_open_pictures(ctx)


# ------------------------------------------------------------
# Log stream (disabled – Windows safe)
# ------------------------------------------------------------
@app.route("/api/log-stream")
def log_stream():
    return ("", 204)


# ------------------------------------------------------------
# After-request: disable caching
# ------------------------------------------------------------
@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


# ------------------------------------------------------------
# Server runner (called from app.py)
# ------------------------------------------------------------
def run_api_server(app_ctx: AppContext):
    global ctx
    ctx = app_ctx

    # Optional: auto-open browser
    def open_browser():
        webbrowser.open_new("http://127.0.0.1:5000")

    threading.Timer(1.0, open_browser).start()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )