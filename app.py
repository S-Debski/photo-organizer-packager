#!/usr/bin/env python3
"""
Photo Organizer Backend – v2.7 Advanced EXIF Edition
"""

import logging
from queue import Queue

from backend.api_server import run_api_server
from context import AppContext

# ------------------------------------------------------------
# Application Version (single source of truth)
# ------------------------------------------------------------
APP_NAME = "Photo Organizer"
APP_VERSION = "2.7.1"
APP_STAGE = "stable"   # stable | beta | dev
APP_BUILD = "v2.7.1-stable"

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