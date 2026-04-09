# backend/api_server.py
import os
import json
from flask import Flask, send_file, jsonify, request, Response, stream_with_context
from flask_cors import CORS

# ------------------------------------------------------------
# UI PATHS
# ------------------------------------------------------------
BASE_DIR = os.getcwd()
UI_DIR = os.path.join(BASE_DIR, "ui")
UI_INDEX_PATH = os.path.join(UI_DIR, "index.html")

app = Flask(
    __name__,
    static_folder=os.path.join(UI_DIR, "static"),
    static_url_path="/static"
)
CORS(app)


# ------------------------------------------------------------
# INDEX (RAW HTML SERVE)
# ------------------------------------------------------------
@app.route("/")
def index():
    return send_file(UI_INDEX_PATH)


# ------------------------------------------------------------
# ✅ SD CARD DETECTION (HYBRID)
# ------------------------------------------------------------
from sdcard import detect_sd_cards_hybrid, auto_select_sd_card

@app.route("/api/sd-cards")
def api_sd_cards():
    try:
        drives, timings = detect_sd_cards_hybrid()
        return jsonify({
            "success": True,
            "drives": drives,
            "auto_select": auto_select_sd_card(drives),
            "timings": timings
        })
    except Exception as e:
        print("SD detection error:", e)
        return jsonify({"success": False, "error": str(e)})


# ------------------------------------------------------------
# ✅ ANALYZE CARD
# ------------------------------------------------------------
from backend.routes.analyze_card import api_analyze_card

@app.route("/api/analyze-card", methods=["POST"])
def api_analyze():
    return api_analyze_card(app.ctx, request.json)


# ------------------------------------------------------------
# ✅ SET ACTIVE FOLDER
# ------------------------------------------------------------
from backend.routes.set_active_folder import api_set_active_folder

@app.route("/api/set-active-folder", methods=["POST"])
def api_set_folder():
    return api_set_active_folder(app.ctx, request.json)


# ------------------------------------------------------------
# ✅ EXIF STATS
# ------------------------------------------------------------
from backend.routes.exif_stats import api_exif_stats

@app.route("/api/exif-stats")
def api_exif():
    return api_exif_stats(app.ctx)


# ------------------------------------------------------------
# ✅ THUMBNAILS
# ------------------------------------------------------------
from backend.routes.thumbs import api_thumbs, api_photo_proxy, api_full_image

@app.route("/api/thumbs")
def api_thumbs_route():
    return api_thumbs(app.ctx)

@app.route("/api/photo-proxy")
def api_photo_proxy_route():
    path = request.args.get("path")
    return api_photo_proxy(app.ctx, path)

@app.route("/api/full-image")
def api_full_image_route():
    path = request.args.get("path")
    return api_full_image(app.ctx, path)


# ------------------------------------------------------------
# ✅ GPS DATA
# ------------------------------------------------------------
from backend.routes.gps_data import api_gps_data

@app.route("/api/gps-data")
def api_gps_route():
    return api_gps_data(app.ctx)


# ------------------------------------------------------------
# ✅ ORGANIZE JOB
# ------------------------------------------------------------
from backend.routes.organize import api_organize, api_job_status, api_open_pictures

@app.route("/api/organize", methods=["POST"])
def api_organize_route():
    return api_organize(app.ctx)

@app.route("/api/job-status")
def api_job_status_route():
    return api_job_status(app.ctx)

@app.route("/api/pictures-open")
def api_pictures_open_route():
    return api_open_pictures(app.ctx)


# ------------------------------------------------------------
# ✅ LOG STREAM (SSE) — WINDOWS‑SAFE, BYTE‑ONLY, NEVER CRASHES
# ------------------------------------------------------------
@app.route("/api/log-stream")
def api_log_stream_route():
    # Temporarily disabled – avoids Werkzeug SSE lockups on Windows
    return ("", 204)


# ------------------------------------------------------------
# ✅ THREAD MANAGER ENTRYPOINT
# ------------------------------------------------------------
def run_api_server(ctx):
    app.ctx = ctx
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )