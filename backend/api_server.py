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
from backend.routes.thumbs import api_thumbs
from pathlib import Path
from backend.routes.thumbs import api_thumbs, api_photo_proxy, api_full_image
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from photo_core.ctx.context import AppContext
from workers.exif_scanner import exif_scanner_worker

# Routes
from backend.routes.analyze_card import api_analyze_card
from backend.routes.set_active_folder import api_set_active_folder
from backend.routes.gps_data import api_gps_data

#Logging
import logging
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# -----------------------------------------------------------------------------
# Paths (CRITICAL — DO NOT REMOVE)
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]

print("BASE_DIR =", BASE_DIR)
print("TEMPLATES =", BASE_DIR / "templates")
print("STATIC =", BASE_DIR / "ui" / "static")

# -----------------------------------------------------------------------------
# Flask app (configured for your project layout)
# -----------------------------------------------------------------------------
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),     # ✅ index.html lives here
    static_folder=str(BASE_DIR / "ui" / "static"),   # ✅ JS/CSS here
    static_url_path="/static"
)

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
from backend.services.sdcard import detect_sd_cards, auto_select_sd_card
import pythoncom

@app.route("/api/sd-cards")
def api_sd_cards():
    pythoncom.CoInitialize()   # ✅ Windows COM init
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
# EXIF progress tracking (read Phase)
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
# EXIF progress tracking (write Phase)
# -----------------------------------------------------------------------------
@app.route("/api/write-progress")
def get_write_progress():
    return jsonify(getattr(ctx, "write_progress", {
        "total": 0,
        "done": 0,
        "active": False
    }))

# -----------------------------------------------------------------------------
# Photo proxy (serve thumbnails / images)
# -----------------------------------------------------------------------------
@app.route("/api/photo-proxy")
def photo_proxy():
    touch_activity()
    path = request.args.get("path")
    return api_photo_proxy(ctx, path)


# -----------------------------------------------------------------------------
# Full image (for preview)
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
    #print("📡 /api/gps-data called")
    return api_gps_data(ctx)
# Write GPS back to original files in working dir
from backend.routes.write_gps import api_write_gps

@app.route("/api/write-gps", methods=["POST"])
def write_gps():
    return api_write_gps(ctx, request.json)

### Let user choose own dir - default if not
@app.route("/api/set-working-dir", methods=["POST"])
def set_working_dir():
    data = request.json
    path = data.get("path")

    if not os.path.isdir(path):
        return jsonify({"error": "Invalid path"}), 400

    ctx.working_base_dir = path
    return jsonify({"success": True})

# -----------------------------------------------------------------------------
# Server runner (called from app.py)
# -----------------------------------------------------------------------------
def run_api_server(app_ctx):
    global ctx
    ctx = app_ctx

    # ✅ Start EXIF scanner worker
    threading.Thread(
        target=exif_scanner_worker,
        args=(ctx,),
        daemon=True,
    ).start()

    print("✅ EXIF scanner worker started")

    # Optional: auto-open browser
    def open_browser():
        webbrowser.open_new("http://127.0.0.1:5000")

    threading.Timer(1.0, open_browser).start()

    # Start Flask
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )