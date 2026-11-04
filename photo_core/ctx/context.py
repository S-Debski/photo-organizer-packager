# Role: Application module (see Stability Contract)

# context.py
import threading
import queue
import os

class AppContext:
    def __init__(self):
        self.shutdown_event = threading.Event()
        # ------------------------------------------------------------
        # Scan/write coordination lock
        # ------------------------------------------------------------
        # Ensures EXIF scan and GPS write never run at the same time
        #
        self.scan_lock = threading.Lock()

        self.working_base_dir = None  # user-selected base directory
        self.working_dir = None
        self.session_id = None

        self.task_queue = queue.Queue()

        self.exif_cache = {}
        self.thumb_cache = {}

        self.config = {}
        self.scan_enabled = True

        # ------------------------------------------------------------
        # Unified progress tracking (scan + write)
        # ------------------------------------------------------------
        # Used across:
        # - EXIF scanner (read phase)
        # - GPS write (mutation phase)
        #
        # This replaces fragmented progress systems and provides
        # a single source of truth for UI progress display.
        #
        self.progress = {
            "stage": "idle",  # "scan" | "write" | "idle"
            "total": 0,
            "done": 0,
            "active": False,
            "message": ""
        }

        self.state = {
            "current_sd_root": None,
            "current_active_folder": None,
            "job": {"active": False, "progress": 0, "status": "Idle"}

        }

        # Logging bus for SSE (currently unused / deferred)
        self.log_queue = queue.Queue()

        # Cache directory
        self.cache_dir = os.path.join(
            os.path.expanduser("~"),
            "AppData",
            "Local",
            "PhotoWizardCache"
        )
        os.makedirs(self.cache_dir, exist_ok=True)

        # ------------------------------------------------------------
        # Organize output directory
        # ------------------------------------------------------------
        # Default destination for organized photos.
        #
        # NOTE:
        # - This is intentionally fixed for v2.7 to keep Organize safe and predictable.
        # - In a future version (v2.8+), this will become user-configurable
        #   via Settings and persisted in ctx.config.
        #
        # IMPORTANT:
        # - All Organize-related code MUST use ctx.output_dir.
        # - Do not introduce alternative destination fields.
        #
        self.output_dir = os.path.join(
            os.path.expanduser("~"),
            "Pictures",
            "PhotoWizard"
        )
        os.makedirs(self.output_dir, exist_ok=True)

        # ------------------------------------------------------------
        # Sessions root (v3.0 ingest)
        # ------------------------------------------------------------
        # Each ingest session gets its own subfolder here, named
        # <session_id>, containing session.json plus copied RAW/JPG.
        # Referenced by backend/api_server.py's /api/session/create.
        #
        self.sessions_root = os.path.join(self.output_dir, "sessions")
        os.makedirs(self.sessions_root, exist_ok=True)

        # Lock for job state
        self.job_lock = threading.Lock()
