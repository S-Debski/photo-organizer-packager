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

import threading
import webbrowser
import os
from pathlib import Path

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

import pythoncom
import logging

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.getLogger('werkzeug').setLevel(logging.WARNING)

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
    return render_template("index.html")


# -----------------------------------------------------------------------------
# SD card detection
# -----------------------------------------------------------------------------
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
        print("❌ SD detect error:", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# -----------------------------------------------------------------------------
# Analyze SD card
# -----------------------------------------------------------------------------
@app.route("/api/analyze-card", methods=["POST"])
def analyze_card():
    touch_activity()
    return api_analyze_card(ctx, request.json)


# -----------------------------------------------------------------------------
# Set active folder
# -----------------------------------------------------------------------------
@app.route("/api/set-active-folder", methods=["POST"])
def set_active_folder():
    touch_activity()
    return api_set_active_folder(ctx, request.json)


# -----------------------------------------------------------------------------
# Thumbnails
# -----------------------------------------------------------------------------
@app.route("/api/thumbs", methods=["POST"])
def thumbs():
    touch_activity()
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


# -----------------------------------------------------------------------------
# Server runner (CLEAN + FIXED)
# -----------------------------------------------------------------------------
def run_api_server(app_ctx):
    global ctx
    ctx = app_ctx

    # ✅ Start worker ONLY ONCE
    if os.environ.get("WERKZEUG_RUN_MAIN") is None:
        threading.Thread(
            target=exif_scanner_worker,
            args=(ctx,),
            daemon=True,
        ).start()

        # ✅ Auto-open browser once
        threading.Timer(
            1.0,
            lambda: webbrowser.open_new("http://127.0.0.1:5000")
        ).start()

    # ✅ Run Flask clean (no ghost instances)
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )