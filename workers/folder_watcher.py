# workers/folder_watcher.py
import time

def folder_watcher_worker(ctx):
    """
    SD CARD SAFE VERSION:
    - Does NOT watch the SD card at all
    - Prevents cache clears during EXIF/thumbnail generation
    - Prevents UI breaks, stats blank, thumb blank
    - Prevents Windows metadata touches from causing resets
    """
    while not ctx.shutdown_event.is_set():
        time.sleep(60)   # idle  (just prevent thread exit)
