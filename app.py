# Role: UI application wiring (see Stability Contract)

#!/usr/bin/env python3
"""
Photo Organizer – v3.0 Hybrid Ingest Edition

Starts the Flask backend in a background thread and keeps the main thread
for the tray / menu-bar icon (Open, Quit). Falls back to running headless
until Ctrl+C when no tray is available (e.g. Linux without a status tray).
"""

import os
import sys
import socket
import atexit
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Bundled data (templates, icons, exiftool) lives in sys._MEIPASS when frozen
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", ROOT_DIR))
FROZEN = getattr(sys, "frozen", False)


def _log_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "PhotoOrganizer"
    if os.name == "nt":
        return Path.home() / "AppData" / "Local" / "PhotoWizardCache"
    return Path.home() / ".cache" / "PhotoOrganizer"


# A windowed build has no console: sys.stdout/stderr are None and every
# print() and traceback vanishes. Send them to a log file instead.
LOG_FILE = None
if sys.stdout is None or sys.stderr is None:
    _dir = _log_dir()
    _dir.mkdir(parents=True, exist_ok=True)
    LOG_FILE = _dir / "photo-organizer.log"
    # Append (a second launch must not truncate the running instance's
    # log); roll over to .old once it passes 2 MB.
    try:
        if LOG_FILE.stat().st_size > 2_000_000:
            LOG_FILE.replace(LOG_FILE.with_suffix(".log.old"))
    except OSError:
        pass
    _fh = open(LOG_FILE, "a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = sys.stdout or _fh
    sys.stderr = sys.stderr or _fh

# Emoji in worker print() calls raise UnicodeEncodeError on cp1252 streams
# (redirected output), which silently kills the EXIF scanner thread.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import logging  # noqa: E402

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("PhotoOrganizerBackend")

from backend import api_server  # noqa: E402
from photo_core.ctx.context import AppContext  # noqa: E402
from photo_core.exif.reader import resolve_exiftool_cmd  # noqa: E402
from version import APP_NAME, APP_BUILD, APP_VERSION  # noqa: E402


# ------------------------------------------------------------
# Clean shutdown handler
# ------------------------------------------------------------
# Daemon threads (EXIF scanner, Flask) may still be printing when Python
# shuts down; redirecting to devnull avoids the Windows stdout-lock crash.
# ------------------------------------------------------------
def _suppress_output_on_exit():
    try:
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
    except Exception:
        pass


atexit.register(_suppress_output_on_exit)


def _probe(port: int) -> str:
    """'free', 'ours' (a running Photo Organizer) or 'other' (another program)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        if s.connect_ex((api_server.HOST, port)) != 0:
            return "free"
    try:
        import json
        import urllib.request

        url = f"http://{api_server.HOST}:{port}/api/whoami"
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            if json.load(resp).get("app") == api_server.APP_ID:
                return "ours"
    except Exception:
        pass
    return "other"


def _choose_port() -> tuple[int | None, bool]:
    """
    (port, already_running). Port 5000 is often taken — macOS AirPlay
    Receiver listens on it — so try the next few, and recognise a running
    Photo Organizer on any of them.
    """
    base = api_server.PORT
    for port in range(base, base + 10):
        state = _probe(port)
        if state == "ours":
            return port, True
        if state == "free":
            return port, False
        logger.info(f"Port {port} is used by another program; trying the next one")
    return None, False


def _run_tray(ctx) -> bool:
    """Run the tray icon on the main thread. False if unavailable."""
    try:
        from tray.tray_icon import run_tray

        run_tray(
            ctx,
            RESOURCE_DIR / "assets" / "icon.png",
            api_server.open_ui,
            title=f"{APP_NAME} {APP_VERSION}",
        )
        return True
    except Exception as e:
        logger.warning(f"Tray icon unavailable ({e}); running without it")
        return False


# ------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------
def main():
    logger.info(f"Starting {APP_NAME} {APP_VERSION} ({APP_BUILD})")
    if LOG_FILE:
        logger.info(f"Logging to {LOG_FILE}")

    port, running = _choose_port()
    if port is None:
        logger.error("No free port found (tried 10); not starting")
        return
    api_server.set_port(port)

    # Second launch: show the running instance's page and exit
    if running:
        logger.info(f"Already running on port {port} — opening the existing window")
        api_server.open_ui()
        return
    logger.info(f"Using {api_server.APP_URL}")

    exiftool = resolve_exiftool_cmd()
    if exiftool:
        logger.info(f"ExifTool: {exiftool}")
    else:
        logger.warning(
            "ExifTool not found — EXIF dates, camera and GPS will be missing"
        )

    ctx = AppContext()
    api_server.start_api_server(ctx)

    if not _run_tray(ctx):
        try:
            # Timed waits so Ctrl+C is delivered on Windows
            while not ctx.shutdown_event.wait(0.5):
                pass
        except KeyboardInterrupt:
            pass

    ctx.shutdown_event.set()
    logger.info("Shutting down")


if __name__ == "__main__":
    main()
