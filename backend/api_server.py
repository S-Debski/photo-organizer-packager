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
import json
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
from backend.routes.write_gps import api_write_gps, write_gps_tags, write_gps_sidecar

from backend.services.sdcard import list_all_sources

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
from photo_core.export import pixel
from photo_core.exif.reader import read_exif
from photo_core.organize.destination import (
    resolve_destination,
    check_writable,
    is_within,
    DestinationError,
)

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
# Local-only guard
# -----------------------------------------------------------------------------
# The app listens on 127.0.0.1, but a web page could still reach it through
# DNS rebinding (a hostile domain that resolves to 127.0.0.1). Such requests
# carry the attacker's host name, so only accept requests addressed to this
# machine by name.
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}

# File types the photo endpoints may read or hand to other apps
PHOTO_EXTS = {*IMAGE_EXTS_ALL, ".png", ".tif", ".tiff", ".xmp"}


def is_photo_file(path: str) -> bool:
    return bool(path) and os.path.splitext(path)[1].lower() in PHOTO_EXTS \
        and os.path.isfile(path)


def _host_name(host: str) -> str:
    """'127.0.0.1:5000' → '127.0.0.1'; '[::1]:5000' → '[::1]'."""
    host = (host or "").lower()
    if host.startswith("["):
        return host[: host.find("]") + 1]
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


@app.before_request
def _only_local_requests():
    if _host_name(request.host) not in LOCAL_HOSTS:
        return jsonify({"success": False, "error": "Forbidden"}), 403


@app.after_request
def _security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"     # JSON is never sniffed as HTML
    resp.headers["X-Frame-Options"] = "DENY"               # no embedding in other sites
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


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
# SD card detection
# -----------------------------------------------------------------------------
@app.route("/api/sd-cards", methods=["GET"])
def api_sd_cards():
    try:
        # Default: camera cards and external (USB/FireWire) drives.
        # all=true adds this computer's internal disks and network drives.
        drives = list_all_sources()
        if request.args.get("all") != "true":
            drives = [d for d in drives if d["kind"] in ("card", "external")]
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
        data = request.json or {}
        source      = data.get("source")
        destination = data.get("destination")

        import shutil

        if not source or not os.path.isdir(source):
            return {"success": False,
                    "error": "The source folder isn't available. Is the card still inserted?"}

        # ------------------------------------------------------------------
        # Destination (design 07/09): <destination>/<template(title, date)>.
        # Validated before anything is created; never on the card/source.
        # Without a title, fall back to the old "<folder> - <card label>".
        # ------------------------------------------------------------------
        protected = [ctx.state.get("current_sd_root"), source]
        title = (data.get("title") or "").strip()
        relative = None
        try:
            if title:
                dest_dir, relative = resolve_destination(
                    destination=destination,
                    template=data.get("template"),
                    title=title,
                    shoot_date=data.get("shoot_date"),
                    protected=protected,
                )
            else:
                if not (destination or "").strip():
                    raise DestinationError("Choose a destination folder first.")
                if any(p and is_within(destination, p) for p in protected):
                    raise DestinationError("The destination can't be on the card or inside the folder being imported.")
                dest_dir = os.path.normpath(os.path.join(destination, _legacy_subfolder(source)))
            check_writable(dest_dir)
        except DestinationError as e:
            return {"success": False, "error": str(e)}

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
                        "error": "No photos are marked Keep. Cull first, or choose Import everything."}
            candidates = _with_same_stem_siblings(kept_paths)
        else:
            candidates = [os.path.join(root, f)
                          for root, _, files in os.walk(source) for f in files]

        files = [p for p in candidates
                 if os.path.splitext(p)[1].lower() in ALLOWED_EXTENSIONS
                 and os.path.isfile(p)]

        if not files:
            return {"success": False, "error": "There are no photos to import in this folder."}

        if ctx.progress.get("active"):
            return {"success": False, "error": "Another import is already running"}

        # ------------------------------------------------------------------
        # Location: one for the whole import (Locations step), or per file
        # (older clients). Applied after copying, to the copies only.
        # ------------------------------------------------------------------
        location = None
        loc = data.get("location")
        if loc:
            try:
                location = (float(loc["lat"]), float(loc["lon"]))
            except (KeyError, TypeError, ValueError):
                return {"success": False, "error": "The assigned location isn't valid."}

        gps_by_source = {}
        for g in data.get("gps") or []:
            try:
                gps_by_source[os.path.normcase(os.path.normpath(g["path"]))] = (
                    float(g["lat"]), float(g["lon"]))
            except (KeyError, TypeError, ValueError):
                continue

        # Nothing is created until validation has passed
        os.makedirs(dest_dir, exist_ok=True)

        ctx.progress.update(stage="import", total=len(files), done=0,
                            active=True, message=f"Importing {len(files)} files…")
        copied, skipped, conflicts, errors = [], [], [], []
        to_tag = []          # (dst_path, (lat, lon)) — tagged after copying
        session = ctx.state.get("session")

        try:
            for src_path in files:
                f = os.path.basename(src_path)
                dst_path = os.path.join(dest_dir, f)
                try:
                    if os.path.exists(dst_path):
                        if os.path.getsize(dst_path) == os.path.getsize(src_path):
                            skipped.append(f)          # already imported
                        else:
                            # Same name, different file (another card, or a
                            # broken copy from an old version): never overwrite
                            conflicts.append(f)
                            ctx.progress["done"] += 1
                            continue
                    else:
                        _safe_copy(shutil, src_path, dst_path)
                        copied.append(f)

                        gps = location or gps_by_source.get(
                            os.path.normcase(os.path.normpath(src_path)))
                        if gps:
                            to_tag.append((dst_path, gps))
                    if session:
                        _mark_session_copied(session, f, dst_path)
                except OSError as e:
                    errors.append(f"{f}: {e}")
                    logger.error(f"organize: copy failed {src_path} → {e}")
                ctx.progress["done"] += 1

            # GPS last, so a sidecar copied from the card is updated rather
            # than clashing with one we created
            gps_written = sidecars_written = 0
            for dst_path, (lat, lon) in to_tag:
                ext = os.path.splitext(dst_path)[1].lower()
                if ext in JPG_EXTENSIONS:
                    result = write_gps_tags(dst_path, lat, lon)
                    counter = "jpg"
                elif ext in RAW_EXTENSIONS:
                    result = write_gps_sidecar(dst_path, lat, lon)
                    counter = "xmp"
                else:
                    continue
                if result.returncode == 0:
                    if counter == "jpg":
                        gps_written += 1
                    else:
                        sidecars_written += 1
                else:
                    errors.append(f"{os.path.basename(dst_path)}: location not written — {result.stderr.strip()}")
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
                "conflicts": len(conflicts),
                "errors": len(errors),
                "location": list(location) if location else None,
            })
            try:
                save_session(ctx.state["session_dir"], session)
            except Exception as e:
                logger.error(f"organize: session save failed — {e}")

        problems = len(errors) + len(conflicts)
        return {
            "success": not problems,
            "count": len(copied),
            "skipped": len(skipped),
            "conflicts": conflicts[:20],
            "gps_written": gps_written,
            "sidecars_written": sidecars_written,
            "errors": errors[:20],
            "error": (f"{len(conflicts)} file(s) already exist with different content and were not overwritten. "
                      if conflicts else "") + (f"{len(errors)} file(s) failed." if errors else "") or None,
            "destination": dest_dir,
            "relative": relative,
            "mode": mode,
            # Design: copy-only import of everything → the card can be formatted
            "all_copied": mode == "all" and not problems,
        }

    except Exception as e:
        logger.exception("organize failed")
        return {"success": False, "error": str(e)}


def _safe_copy(shutil, src_path: str, dst_path: str) -> None:
    """
    Copy via a temporary name and rename into place, so an interrupted copy
    never leaves a partial file under the real name (which a later import
    would otherwise skip as "already imported").
    """
    tmp = dst_path + ".part"
    try:
        shutil.copy2(src_path, tmp)
        if os.path.getsize(tmp) != os.path.getsize(src_path):
            raise OSError("copy incomplete (size mismatch)")
        os.replace(tmp, dst_path)
    except BaseException:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)   # our own partial temp file only
        except OSError:
            pass
        raise


def _legacy_subfolder(source: str) -> str:
    """Old layout: "<path below DCIM, joined with ' - '> - <card label>"."""
    sd_root   = ctx.state.get("current_sd_root", "")
    dcim_path = os.path.join(sd_root, "DCIM") if sd_root else ""

    drive_label = ""
    if sd_root:
        try:
            import win32api
            vol_path = sd_root.rstrip("\\/ ") + "\\"
            drive_label = win32api.GetVolumeInformation(vol_path)[0] or ""
        except Exception:
            drive_label = os.path.basename(sd_root.rstrip("\\/ ")) or ""

    source_norm = os.path.normpath(source)
    if dcim_path and source_norm.lower().startswith(dcim_path.lower()):
        camera_folder = os.path.relpath(source_norm, dcim_path).replace(os.sep, " - ")
    else:
        camera_folder = os.path.basename(source_norm)

    if camera_folder and drive_label:
        return f"{camera_folder} - {drive_label}"
    return camera_folder or "Imported"


# -----------------------------------------------------------------------------
# POST /api/pre-import/preview — the exact folder an import would use
# -----------------------------------------------------------------------------
@app.route("/api/pre-import/preview", methods=["POST"])
def pre_import_preview():
    data = request.json or {}
    source = data.get("source") or ctx.state.get("current_active_folder")
    try:
        full, relative = resolve_destination(
            destination=data.get("destination"),
            template=data.get("template"),
            title=data.get("title"),
            shoot_date=data.get("shoot_date"),
            protected=[ctx.state.get("current_sd_root"), source],
        )
        check_writable(full)
    except DestinationError as e:
        return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": True, "path": full, "relative": relative,
                    "exists": os.path.isdir(full)})


# -----------------------------------------------------------------------------
# /api/locations — locations assigned on the Locations step, kept on disk so
# they survive a restart until the import writes them into the copies.
# Keyed by folder path + first photo name, because the next card in the
# same reader has the same paths (F:\DCIM\100_FUJI) but different photos.
# -----------------------------------------------------------------------------
def _locations_file() -> str:
    return os.path.join(ctx.sessions_root, "locations.json")


def _location_key(folder: str) -> str | None:
    if not folder or not os.path.isdir(folder):
        return None
    # First photo's name *and size*: another card can reuse DSCF0001
    first = next(iter(sorted(iter_images(folder), key=lambda p: os.path.basename(p).upper())), None)
    if not first:
        return None
    try:
        size = os.path.getsize(first)
    except OSError:
        size = 0
    return f"{os.path.normcase(os.path.normpath(folder))}|{os.path.basename(first).upper()}|{size}"


def _load_locations() -> dict:
    try:
        # utf-8-sig: tolerate a BOM if the file was edited in Notepad
        with open(_locations_file(), encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_locations(locs: dict) -> None:
    path = _locations_file()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(locs, fh, indent=1)
    os.replace(tmp, path)


# -----------------------------------------------------------------------------
# Send to Pixel (adb) — after import, push the shoot to the user's phone so
# Google Photos backs it up. See photo_core/export/pixel.py.
# -----------------------------------------------------------------------------
@app.route("/api/pixel/status")
def api_pixel_status():
    adb = pixel.resolve_adb()
    devices = []
    error = None
    if adb:
        try:
            devices = pixel.list_devices(adb)
        except Exception as e:
            error = str(e)
    return jsonify({"adb": adb, "devices": devices, "error": error,
                    "phone_folder": pixel.PHONE_FOLDER})


@app.route("/api/pixel/send", methods=["POST"])
def api_pixel_send():
    data = request.json or {}
    folder = data.get("folder") or ""
    serial = data.get("serial") or ""
    include_raw = bool(data.get("include_raw"))

    adb = pixel.resolve_adb()
    if not adb:
        return jsonify({"success": False, "error": "Android platform tools (adb) aren't installed."}), 400
    if not os.path.isdir(folder):
        return jsonify({"success": False, "error": "The imported folder isn't there any more."}), 400
    if any(p and is_within(folder, p) for p in (ctx.state.get("current_sd_root"),)):
        return jsonify({"success": False, "error": "Send the imported copies, not the card."}), 400
    if ctx.progress.get("active"):
        return jsonify({"success": False, "error": "Another operation is running"}), 409

    ready = [d for d in pixel.list_devices(adb) if d["state"] == "device"]
    if serial:
        ready = [d for d in ready if d["serial"] == serial]
    if not ready:
        return jsonify({"success": False, "error": "No phone ready. Connect it with USB and allow USB debugging."}), 400
    serial = ready[0]["serial"]

    def worker():
        ctx.progress.update(stage="pixel", total=0, done=0, active=True,
                            message="Checking the phone…")
        try:
            def on_progress(done, total, message):
                ctx.progress.update(done=done, total=total, message=message)

            result = pixel.send_folder(adb, serial, folder, include_raw, on_progress)
            msg = f"Sent {result['sent']} to the phone" + (
                f", {result['skipped']} already there" if result["skipped"] else "") + (
                f", {len(result['failed'])} failed" if result["failed"] else "")
            ctx.state["pixel_result"] = {**result, "success": not result["failed"], "message": msg}
            ctx.progress.update(message=msg)
        except Exception as e:
            logger.exception("pixel send failed")
            ctx.state["pixel_result"] = {"success": False, "message": f"Sending failed: {e}"}
            ctx.progress.update(message=f"Sending failed: {e}")
        finally:
            ctx.progress.update(stage="idle", active=False)

    ctx.state["pixel_result"] = None
    threading.Thread(target=worker, daemon=True, name="pixel-send").start()
    return jsonify({"success": True, "serial": serial})


@app.route("/api/pixel/result")
def api_pixel_result():
    return jsonify({"result": ctx.state.get("pixel_result"),
                    "progress": ctx.progress})


# -----------------------------------------------------------------------------
# /api/places — named places reused across shoots (venues, regular walks).
# Kept beside the sessions; shared by every card.
# -----------------------------------------------------------------------------
_DEFAULT_PLACES = [
    # Example venue (previously hard-coded in analyze_card.py)
    {"name": "Butley Village Hall", "lat": 52.1072, "lon": 1.4575},
]


def _places_file() -> str:
    return os.path.join(ctx.sessions_root, "places.json")


def _load_places() -> list[dict]:
    path = _places_file()
    if not os.path.exists(path):
        return [dict(p) for p in _DEFAULT_PLACES]
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return [p for p in data if isinstance(p, dict) and p.get("name")]
    except (OSError, ValueError):
        return []


def _save_places(places: list[dict]) -> None:
    path = _places_file()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(places, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


@app.route("/api/places", methods=["GET", "POST"])
def api_places():
    places = _load_places()

    if request.method == "POST":
        data = request.json or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"success": False, "error": "A place needs a name"}), 400

        places = [p for p in places if p["name"].casefold() != name.casefold()]
        if not data.get("delete"):
            try:
                lat, lon = float(data["lat"]), float(data["lon"])
            except (KeyError, TypeError, ValueError):
                return jsonify({"success": False, "error": "lat and lon are required"}), 400
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return jsonify({"success": False, "error": "Coordinates out of range"}), 400
            places.append({"name": name, "lat": lat, "lon": lon})
        _save_places(places)

    places.sort(key=lambda p: p["name"].casefold())
    return jsonify({"success": True, "places": places})


@app.route("/api/locations", methods=["GET", "POST"])
def api_locations():
    locs = _load_locations()

    if request.method == "POST":
        data = request.json or {}
        folders = data.get("folders") or []
        if data.get("clear"):
            for folder in folders:
                key = _location_key(folder)
                if key:
                    locs.pop(key, None)
        else:
            try:
                lat, lon = float(data["lat"]), float(data["lon"])
            except (KeyError, TypeError, ValueError):
                return jsonify({"success": False, "error": "lat and lon are required"}), 400
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return jsonify({"success": False, "error": "Coordinates out of range"}), 400
            for folder in folders:
                key = _location_key(folder)
                if key:
                    locs[key] = {"folder": folder, "lat": lat, "lon": lon,
                                 "set_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        _save_locations(locs)

    # Report locations only for the folders asked about (the current card)
    if request.method == "POST":
        wanted = (request.json or {}).get("folders") or []
    else:
        wanted = request.args.getlist("folder")
    result = {}
    for folder in wanted:
        hit = locs.get(_location_key(folder) or "")
        if hit:
            result[folder] = {"lat": hit["lat"], "lon": hit["lon"]}
    return jsonify({"success": True, "locations": result})


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
def _photo_arg(raw):
    """Absolute path of a photo file from a request, or None (never other files)."""
    if not raw:
        return None
    # Flask has already URL-decoded query values; absolute paths also mean
    # a value can never start with "-" and be read as a tool's option
    path = os.path.abspath(os.path.normpath(raw))
    return path if is_photo_file(path) else None


@app.route("/api/photo-proxy")
def photo_proxy():
    touch_activity()
    path = _photo_arg(request.args.get("path"))
    if not path:
        return jsonify({"success": False, "error": "Photo not found"}), 404
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
# POST /api/file-action — right-click menu: open, open with…, show in folder.
# Photo files only (never anything that could be executed).
# -----------------------------------------------------------------------------
@app.route("/api/file-action", methods=["POST"])
def file_action():
    import subprocess
    data = request.json or {}
    path = _photo_arg(data.get("path"))
    action = data.get("action")

    if not path:
        return jsonify({"success": False, "error": "Not a photo file"}), 400

    system = platform.system()
    try:
        if action == "reveal":
            if system == "Windows":
                # Argument list, not a command string; path is a validated photo
                subprocess.Popen(["explorer", "/select,", path])
            elif system == "Darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        elif action == "open":
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        elif action == "openwith" and system == "Windows":
            # Windows' own "How do you want to open this file?" chooser
            subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", path])
        else:
            return jsonify({"success": False, "error": "Not supported here"}), 400
    except OSError as e:
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True})


# -----------------------------------------------------------------------------
# Photo info for the viewer / review step: shooting details from EXIF
# (already cached by the scanner's batched read). Pass every file of the
# photo (?path=JPG&path=RAW); each field comes from the first file that has it.
# -----------------------------------------------------------------------------
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_taken(raw) -> str | None:
    """'2026:10:10 14:32:05' → '10 Oct 2026, 14:32'."""
    try:
        d, t = str(raw).split(" ", 1)
        y, m, day = d.split(":")
        return f"{int(day)} {_MONTHS[int(m) - 1]} {y}, {t[:5]}"
    except (ValueError, IndexError):
        return str(raw) if raw else None


def _fmt_shutter(t) -> str | None:
    try:
        t = float(t)
    except (TypeError, ValueError):
        return None
    if t <= 0:
        return None
    return f"{t:g} s" if t >= 1 else f"1/{round(1 / t)} s"


def _fmt_num(v, fmt="{:g}"):
    try:
        return fmt.format(float(v))
    except (TypeError, ValueError):
        return None


@app.route("/api/photo-info")
def photo_info():
    paths = [p for p in (_photo_arg(r) for r in request.args.getlist("path")) if p]
    if not paths:
        return jsonify({"success": False, "error": "Photo not found"}), 404

    # JPG first (camera JPEGs carry the same shooting data), then RAW
    paths.sort(key=lambda p: os.path.splitext(p)[1].lower() not in JPG_EXTENSIONS)
    records = [read_exif(p) for p in paths]

    def val(*keys):
        for rec in records:
            for k in keys:
                v = rec.get(k)
                if v not in (None, "", 0, "0"):
                    return v
        return None

    # Some editors move Make/Model into the Exif IFD
    make = str(val("IFD0:Make", "ExifIFD:Make") or "").strip()
    model = str(val("IFD0:Model", "ExifIFD:Model") or "").strip()
    camera = model if make and model.lower().startswith(make.split()[0].lower()) else \
        " ".join(x for x in (make.title() if make.isupper() else make, model) if x)

    focal = _fmt_num(val("ExifIFD:FocalLength"), "{:g} mm")
    focal35 = _fmt_num(val("ExifIFD:FocalLengthIn35mmFormat"), "{:g} mm")
    if focal and focal35 and focal35 != focal:
        focal = f"{focal} ({focal35} eq.)"

    ev = val("ExifIFD:ExposureCompensation")
    ev_text = None
    try:
        if ev is not None and abs(float(ev)) >= 0.05:
            ev_text = f"{float(ev):+.1f} EV"
    except (TypeError, ValueError):
        pass

    w = val("File:ImageWidth", "ExifIFD:ExifImageWidth")
    h = val("File:ImageHeight", "ExifIFD:ExifImageHeight")

    lat, lon = val("Composite:GPSLatitude"), val("Composite:GPSLongitude")
    gps = None
    try:
        if lat is not None and lon is not None:
            gps = [float(lat), float(lon)]
    except (TypeError, ValueError):
        gps = None

    return jsonify({
        "success": True,
        "taken": _fmt_taken(val("ExifIFD:DateTimeOriginal", "ExifIFD:CreateDate", "IFD0:ModifyDate")),
        "camera": camera or None,
        "lens": val("ExifIFD:LensModel", "Composite:LensID", "Composite:Lens"),
        "focal": focal,
        "aperture": _fmt_num(val("ExifIFD:FNumber", "Composite:Aperture"), "f/{:g}"),
        "shutter": _fmt_shutter(val("ExifIFD:ExposureTime", "Composite:ShutterSpeed")),
        "iso": _fmt_num(val("ExifIFD:ISO", "Composite:ISO"), "ISO {:g}"),
        "ev": ev_text,
        "size": f"{w} × {h}" if w and h else None,
        "gps": gps,
        "files": [{"name": os.path.basename(p), "bytes": os.path.getsize(p)} for p in paths],
    })


# -----------------------------------------------------------------------------
# Cached thumbnail / preview (size: grid | strip | preview)
# -----------------------------------------------------------------------------
@app.route("/api/thumb")
def thumb():
    path = _photo_arg(request.args.get("path"))
    if not path:
        return jsonify({"success": False, "error": "Photo not found"}), 404
    return api_thumb(ctx, path, request.args.get("size", "grid"))

# -----------------------------------------------------------------------------
# Full image
# -----------------------------------------------------------------------------
@app.route("/api/full-image")
def full_image():
    touch_activity()
    path = _photo_arg(request.args.get("path"))
    if not path:
        return jsonify({"success": False, "error": "Photo not found"}), 404
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
        # ...but only a session made from these photos: the next card in
        # the same reader slot has the same paths and often the same names.
        current_files = list(iter_images(source_folder)) if os.path.isdir(source_folder) else []
        existing = None if data.get("new") else find_latest_session(
            ctx.sessions_root, source_folder, current_files)

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
            register_paths(session_data, current_files)
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

    except Exception:
        # Full traceback goes to the log only, never to the page
        logger.exception("session/create failed")
        return jsonify({"success": False, "error": "Couldn't start a culling session (see the log)."}), 500


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
APP_ID = "PhotoOrganizer"


def set_port(port: int) -> None:
    """Chosen at start-up by app.py (5000 may belong to another program)."""
    global PORT, APP_URL
    PORT = port
    APP_URL = f"http://{HOST}:{port}"


@app.route("/api/whoami")
def whoami():
    # Lets a second launch tell a running Photo Organizer apart from
    # another program on the same port (e.g. macOS AirPlay on 5000)
    return jsonify({"app": APP_ID, "version": APP_VERSION})


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