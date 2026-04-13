#!/usr/bin/env python3
"""
Photo Organizer Backend – v2.7 Advanced EXIF Edition
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import logging
from queue import Queue

from backend.api_server import run_api_server
from context import AppContext

from version import APP_NAME, APP_VERSION, APP_STAGE, APP_BUILD
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
# Entrypoint
# ------------------------------------------------------------
def main():
    backend_log(f"Starting {APP_NAME} {APP_BUILD}")
    ctx = AppContext()
    run_api_server(ctx)

if __name__ == "__main__":
    main()