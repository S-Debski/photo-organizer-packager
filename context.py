# context.py
import os
import threading
import queue

class AppContext:
    def __init__(self):
        self.shutdown_event = threading.Event()

        self.task_queue = queue.Queue()

        self.exif_cache = {}
        self.thumb_cache = {}

        self.config = {}
        self.state = {
            "current_sd_root": None,
            "current_active_folder": None,
            "job": {"active": False, "progress": 0, "status": "Idle"}
        }

        # Logging bus for SSE
        self.log_queue = queue.Queue()

        # Cache directory
        self.cache_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PhotoWizardCache")
        os.makedirs(self.cache_dir, exist_ok=True)

        # Default output folder (can be overridden by config later)
        self.output_dir = os.path.join(os.path.expanduser("~"), "Pictures", "PhotoWizard")
        os.makedirs(self.output_dir, exist_ok=True)

        # Lock for job state
        self.job_lock = threading.Lock()
