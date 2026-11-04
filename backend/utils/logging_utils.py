# Role: Logging setup (see Stability Contract)

# =============================================================================
# File: backend/utils/logging_utils.py
#
# Role:
#   Central logging utility for backend services and API routes.
#
# Responsibilities:
#   - Provide consistent logging interface across the application
#   - Forward log messages to:
#       • Python logger (console + file)
#       • UI log stream via queue
#
# Data Flow:
#   Backend modules
#       → backend_log()
#       → logger (logging module)
#       → log_queue
#       → /api/log-stream
#       → Frontend log viewer
#
# Functions:
#   - backend_log(msg)
#       Logs informational messages and pushes them to UI
#
# Notes:
#   - Avoid using print() in backend code
#   - Use logger.debug/info/warning/error for developer logging
#   - Use backend_log() for user-visible events
#   - Keeps logging decoupled from app.py to avoid circular imports
#
# Used By:
#   - backend/routes/*
#   - backend/services/*
#   - app.py
#
# =============================================================================

import logging
from queue import Queue

logger = logging.getLogger("PhotoOrganizerBackend")

# ✅ Shared queue for UI log streaming
log_queue = Queue()


def backend_log(msg: str):
    """
    Log informational message to logger and UI.
    """
    logger.info(msg)
    log_queue.put(msg)


def backend_warn(msg: str):
    """
    Log warning message to logger and UI.
    """
    logger.warning(msg)
    log_queue.put(f"⚠️ {msg}")


def backend_error(msg: str):
    """
    Log error message to logger and UI.
    """
    logger.error(msg)
    log_queue.put(f"❌ {msg}")
