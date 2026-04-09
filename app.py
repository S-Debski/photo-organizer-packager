#!/usr/bin/env python3
"""
Photo Organizer Backend – v2.7 Advanced EXIF Edition
"""

import os
import sys
import time
import threading
import logging
from pathlib import Path
import pythoncom
from queue import Queue

import flask
flask.templating._default_template_ctx_processor = lambda: {}

from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    render_template,
    Response,
)
from flask_cors import CORS

# Core logic
from photo_core.photo_organizer import PhotoOrganizer

# SD card detection
from sdcard import detect_sd_cards, auto_select_sd_card

# ---------------------------------------------------------
# Debugging Options
# ---------------------------------------------------------
ENABLE_SD_DEBUG = True   # Set False for production

def timed(label):
    """Simple timing utility for SD debug timing logs."""
    t = time.time()
    backend_log(f"[SD DEBUG] {label}: {t:.3f}")
    return t

# ---------------------------------------------------------
# PyInstaller-safe Base Directory
# ---------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR   = BASE_DIR / "static"

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("PhotoOrganizerBackend")
log_queue = Queue()

def backend_log(msg: str):
    """Send logs to browser + Python logger."""
    logger.info(msg)
    log_queue.put(msg)

# ---------------------------------------------------------
# Flask App
# ---------------------------------------------------------
app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=str(STATIC_DIR),
    static_url_path="/static"
)

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Debug route for confirming template paths
@app.route("/debug-index-path")
def debug_index_path():
    try:
        path = os.path.abspath(os.path.join(app.template_folder, "index.html"))
        stat = os.stat(path)
        return f"""
        <b>INDEX PATH:</b> {path}<br>
        <b>SIZE:</b> {stat.st_size} bytes<br>
        <b>MODIFIED:</b> {stat.st_mtime}<br>
        """
    except Exception as e:
        return f"<b>Exception:</b> {e}", 500

CORS(app)
organizer = PhotoOrganizer()

# ---------------------------------------------------------
# Job state
# ---------------------------------------------------------
current_job = {
    "status": "idle",
    "progress": 0,
    "total": 0,
    "percent": 0,
    "message": "",
    "errors": []
}
job_lock = threading.Lock()

def update_progress(current, total):
    with job_lock:
        current_job["progress"] = current
        current_job["total"] = total
        if total > 0:
            current_job["percent"] = round((current / total) * 100, 1)
        else:
            current_job["percent"] = 0

# ---------------------------------------------------------
# Idle shutdown timer
# ---------------------------------------------------------
INACTIVITY_TIMEOUT = 1800
last_activity = time.time()
shutdown_timer = None

def update_last_activity():
    global last_activity
    last_activity = time.time()

def reset_shutdown():
    global shutdown_timer
    if shutdown_timer:
        shutdown_timer.cancel()
    shutdown_timer = threading.Timer(INACTIVITY_TIMEOUT, force_shutdown)
    shutdown_timer.daemon = True
    shutdown_timer.start()

def force_shutdown():
    backend_log("Inactivity timeout reached — shutting down.")
    os._exit(0)

# ---------------------------------------------------------
# Index / Root
# ---------------------------------------------------------
@app.route("/")
def index():
    update_last_activity()
    reset_shutdown()
    return render_template("index.html")

# ---------------------------------------------------------
# SD Card Detection API
# ---------------------------------------------------------
@app.route("/api/sd-cards", methods=["GET"])
def api_sd_cards():
    pythoncom.CoInitialize()
    update_last_activity()
    reset_shutdown()

    backend_log("Scanning for SD/CFexpress cards…")

    try:
        if ENABLE_SD_DEBUG:
            t0 = timed("Detection start")

        cards = detect_sd_cards()

        if ENABLE_SD_DEBUG:
            t1 = timed("Detection finished")
            backend_log(f"[SD DEBUG] TOTAL detection time → {t1 - t0:.3f}s")

        return jsonify({"success": True, "drives": cards})

    except Exception as e:
        backend_log(f"SD detection error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ---------------------------------------------------------
# SD Card Details
# ---------------------------------------------------------
@app.route("/api/sd-card-details", methods=["POST"])
def api_sd_details():
    pythoncom.CoInitialize()
    update_last_activity()
    reset_shutdown()

    path = request.json.get("path")
    if not path:
        return jsonify({"success": False, "error": "path required"}), 400

    cards = detect_sd_cards()
    info = next((c for c in cards if c["path"] == path), None)

    if not info:
        backend_log(f"Card not found: {path}")
        return jsonify({"success": False, "error": "Drive not found"}), 404

    backend_log(f"Selected card: {path}")
    return jsonify({"success": True, "info": info})

# ---------------------------------------------------------
# RAW/JPG Thumbnails
# ---------------------------------------------------------
@app.route("/api/photo-proxy")
def api_photo_proxy():
    pythoncom.CoInitialize()
    update_last_activity()

    file_path = request.args.get("path")
    if not file_path:
        return jsonify({"success": False, "error": "Missing path"}), 400

    fp = Path(file_path)
    if not fp.exists():
        return jsonify({"success": False, "error": "File not found"}), 404

    ext = fp.suffix.lower()

    # RAW thumbnails
    if ext in {".arw", ".nef", ".cr2", ".cr3", ".raf", ".rw2", ".orf"}:
        try:
            import rawpy
            import io

            with rawpy.imread(str(fp)) as raw:
                thumb = raw.extract_thumb()

                if thumb.format == rawpy.ThumbFormat.JPEG:
                    return Response(thumb.data, mimetype="image/jpeg")

                if thumb.format == rawpy.ThumbFormat.BITMAP:
                    import PIL.Image as Image
                    img = Image.fromarray(thumb.data)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG")
                    return Response(buf.getvalue(), mimetype="image/jpeg")

        except Exception as e:
            backend_log(f"RAW thumbnail error: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    # JPG passthrough
    return send_file(fp, mimetype="image/jpeg")

# ---------------------------------------------------------
# Full RAW/JPG Preview
# ---------------------------------------------------------
@app.route("/api/full-image")
def api_full_image():
    pythoncom.CoInitialize()
    update_last_activity()

    file_path = request.args.get("path")
    if not file_path:
        return jsonify({"success": False, "error": "Missing path"}), 400

    fp = Path(file_path)
    if not fp.exists():
        return jsonify({"success": False, "error": "File not found"}), 404

    ext = fp.suffix.lower()

    # RAW → JPEG decode
    if ext in {".arw", ".nef", ".cr2", ".cr3", ".raf", ".rw2", ".orf"}:
        try:
            import rawpy
            import io
            import PIL.Image as Image

            with rawpy.imread(str(fp)) as raw:
                rgb = raw.postprocess()
                img = Image.fromarray(rgb)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=95)
                return Response(buf.getvalue(), mimetype="image/jpeg")

        except Exception as e:
            backend_log(f"RAW full-image error: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    return send_file(fp, mimetype="image/jpeg")

# ---------------------------------------------------------
# Analyze Card
# ---------------------------------------------------------
@app.route("/api/analyze-card", methods=["POST"])
def api_analyze_card():
    pythoncom.CoInitialize()
    update_last_activity()
    reset_shutdown()

    sd = request.json.get("sd_card_path")
    if not sd:
        return jsonify({"success": False, "error": "sd_card_path required"}), 400

    if not sd.endswith("\\"):
        sd = sd + "\\"

    backend_log(f"Analyzing SD card {sd}…")

    try:
        analysis = organizer.analyze_card(sd)
        backend_log(f"Analysis complete. {analysis['total_photos']} photos found.")
        return jsonify({"success": True, "analysis": analysis})

    except Exception as e:
        backend_log(f"Analyze error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ---------------------------------------------------------
# Organize / Copy Photos
# ---------------------------------------------------------
@app.route("/api/organize", methods=["POST"])
def api_organize():
    pythoncom.CoInitialize()
    update_last_activity()
    reset_shutdown()

    data = request.json
    sd_path = data.get("sd_card_path")
    folder_map = data.get("folder_mapping")
    camera_name = data.get("camera_name")
    event_name = data.get("event_name")

    if not sd_path:
        return jsonify({"success": False, "error": "sd_card_path required"}), 400

    if current_job["status"] == "copying":
        return jsonify({"success": False, "error": "Job already running"}), 409

    def worker():
        pythoncom.CoInitialize()
        try:
            backend_log("Starting organize process…")

            with job_lock:
                current_job.update({
                    "status": "copying",
                    "progress": 0,
                    "total": 0,
                    "percent": 0,
                    "message": "Copying photos…",
                    "errors": []
                })

            if folder_map:
                for fmap in folder_map:
                    src = fmap["path"]
                    cam = fmap["camera_name"]
                    evt = fmap["event_name"]

                    backend_log(f"Processing folder: {src}")

                    dest = organizer.create_camera_folder(cam, evt)
                    photos = organizer.find_photo_files(src)

                    with job_lock:
                        current_job["total"] += len(photos)

                    copied, errors = organizer.copy_photos(
                        src, dest, progress_callback=update_progress
                    )

                    current_job["errors"].extend(errors)

            else:
                dest = organizer.create_camera_folder(camera_name, event_name)
                photos = organizer.find_photo_files(sd_path)

                with job_lock:
                    current_job["total"] = len(photos)

                copied, errors = organizer.copy_photos(
                    sd_path, dest, progress_callback=update_progress
                )

                current_job["errors"].extend(errors)

            backend_log("Copy complete.")

            with job_lock:
                current_job["status"] = "complete" if not current_job["errors"] else "error"

        except Exception as e:
            backend_log(f"Organize error: {e}")
            with job_lock:
                current_job.update({"status": "error", "message": str(e)})

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"success": True, "message": "Job started"})

# ---------------------------------------------------------
# Job Status
# ---------------------------------------------------------
@app.route("/api/job-status", methods=["GET"])
def api_job_status():
    pythoncom.CoInitialize()
    update_last_activity()
    reset_shutdown()

    with job_lock:
        return jsonify(current_job)

# ---------------------------------------------------------
# SSE Log Stream
# ---------------------------------------------------------
@app.route("/api/log-stream")
def api_log_stream():
    def event_stream():
        while True:
            msg = log_queue.get()
            yield f"data: {msg}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")

# ---------------------------------------------------------
# Open Pictures Folder
# ---------------------------------------------------------
@app.route("/api/pictures-open", methods=["GET"])
def api_pictures_open():
    try:
        path = organizer.pictures_base
        os.startfile(path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ---------------------------------------------------------
# Server Startup + Browser Auto-open
# ---------------------------------------------------------
import webbrowser

def open_browser():
    url = "http://127.0.0.1:5000"
    webbrowser.open_new(url)

if __name__ == "__main__":
    threading.Timer(1.0, open_browser).start()
    backend_log("Starting Photo Organizer v2.7 server…")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )

# Disable caching
@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response