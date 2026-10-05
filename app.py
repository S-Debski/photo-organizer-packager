# Role: UI application wiring (see Stability Contract)

#!/usr/bin/env python3
"""
Photo Organizer Backend – v3.0 Hybrid Ingest Edition
"""
import sys
import atexit
# TODO(remove): unused import, not referenced anywhere in this file. Confirm no
# future signal-handling need before deleting.
# import signal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import logging
from queue import Queue

# Emoji in worker print() calls raise UnicodeEncodeError on cp1252 streams
# (redirected output), which silently kills the EXIF scanner thread.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# TODO(remove): dead import — both names are immediately shadowed by the
# local backend_log()/log_queue definitions below, so this import has no
# effect. Safe to delete once confirmed nothing else relies on import order
# side effects here.
# from backend.utils.logging_utils import backend_log, log_queue
from backend.api_server import run_api_server
from photo_core.ctx.context import AppContext

from version import APP_NAME, APP_BUILD

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("PhotoOrganizerBackend")

log_queue = Queue()

def backend_log(msg: str):
    logger.info(msg)
    log_queue.put(msg)

# ------------------------------------------------------------
# Clean shutdown handler
# ------------------------------------------------------------
# Suppresses the Windows daemon-thread stdout lock crash on exit.
# Daemon threads (EXIF scanner, thumbnail worker) may still be
# running when Python shuts down and try to print — this redirects
# stdout/stderr to devnull at that point to avoid the fatal error.
# ------------------------------------------------------------
def _suppress_output_on_exit():
    try:
        sys.stdout = open(sys.devnull, 'w')
        sys.stderr = open(sys.devnull, 'w')
    except Exception:
        pass

atexit.register(_suppress_output_on_exit)

# ------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------
def main():
    backend_log(f"Starting {APP_NAME} {APP_BUILD}")
    ctx = AppContext()
    run_api_server(ctx)

if __name__ == "__main__":
    main()