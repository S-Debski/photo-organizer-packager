# Role: Application module (see Stability Contract)

# workers/copy_worker.py
# =============================================================================
#
# Async copy worker for ingest sessions (v3.0)
#
# Responsibilities:
#   - Copy ONLY selected (keeper) assets from source → session working folder
#   - RAW + JPG treated as a pair (both copied together)
#   - Non-blocking: runs in a daemon thread, reports progress via ctx.progress
#   - Calls mark_asset_copied() per file so session manifest stays current
#   - NEVER mutates source files
#   - Safe to call multiple times (skips already-copied assets)
#
# Triggered by:
#   POST /api/session/copy  (api_server.py)
#
# Progress readable at:
#   GET /api/progress       (existing endpoint — reuses ctx.progress)
#
# =============================================================================

import os
import shutil
import threading
import time
import logging
from pathlib import Path

from photo_core.pre_import.session_state import (
    get_selected_assets,
    mark_asset_copied,
    save_session,
    is_asset_fully_copied,
)

logger = logging.getLogger("copy_worker")

# Recognised extensions — used to decide subfolder inside session
from photo_core.pre_import.session_state import RAW_EXTENSIONS, JPG_EXTENSIONS  # noqa: E402,F401


# =============================================================================
# Public API — called from api_server
# =============================================================================

def start_copy_worker(ctx) -> bool:
    """
    Launch the copy worker in a background daemon thread.

    Safe to call from a Flask route — returns immediately.
    Progress tracked via ctx.progress (same schema as EXIF scanner).

    Returns:
        True  if copy thread started
        False if no active session, nothing selected, or copy already running
    """
    session     = ctx.state.get("session")
    session_dir = ctx.state.get("session_dir")

    if not session or not session_dir:
        logger.warning("start_copy_worker: no active session")
        return False

    if ctx.progress.get("active"):
        logger.warning("start_copy_worker: another operation already active")
        return False

    keepers = get_selected_assets(session)
    if not keepers:
        logger.warning("start_copy_worker: no assets selected")
        return False

    thread = threading.Thread(
        target=_copy_worker_thread,
        args=(ctx, session, session_dir, keepers),
        daemon=True,
        name="copy-worker",
    )
    thread.start()
    logger.info(f"Copy worker started — {len(keepers)} assets to copy")
    return True


# =============================================================================
# Worker thread
# =============================================================================

def _copy_worker_thread(ctx, session: dict, session_dir: str, keepers: dict):
    """
    Background thread: copies selected RAW/JPG pairs into the session folder.

    Layout inside session_dir:
        <session_dir>/
            RAW/        ← all RAW files
            JPG/        ← all JPG files

    Progress:
        ctx.progress is updated per FILE (not per asset pair) so the UI
        bar moves smoothly on large cards.
    """

    # ------------------------------------------------------------------
    # Count total files to copy (for progress bar)
    # ------------------------------------------------------------------
    file_tasks = _build_file_tasks(keepers, session_dir)
    total_files = len(file_tasks)

    if total_files == 0:
        logger.info("copy_worker: all selected assets already copied, nothing to do")
        _set_progress(ctx, stage="idle", total=0, done=0, active=False,
                      message="Already up to date")
        return

    # ------------------------------------------------------------------
    # Initialise progress
    # ------------------------------------------------------------------
    _set_progress(ctx, stage="copy", total=total_files, done=0, active=True,
                  message=f"Copying {total_files} files…")

    # ------------------------------------------------------------------
    # Create output subfolders
    # ------------------------------------------------------------------
    raw_dir = os.path.join(session_dir, "RAW")
    jpg_dir = os.path.join(session_dir, "JPG")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(jpg_dir, exist_ok=True)

    done       = 0
    error_count = 0

    for task in file_tasks:
        src_path  = task["src"]
        dst_path  = task["dst"]
        asset_id  = task["asset_id"]
        filetype  = task["filetype"]    # "raw" or "jpg"

        try:
            # Skip if destination already exists (safe re-run)
            if os.path.exists(dst_path):
                logger.debug(f"Skip (exists): {dst_path}")
                mark_asset_copied(session, asset_id, filetype, dst_path)
                done += 1
                _set_progress(ctx, done=done,
                              message=f"Copying {done}/{total_files}…")
                continue

            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)

            # Copy with metadata preservation (timestamps etc.)
            shutil.copy2(src_path, dst_path)

            # Record in session manifest
            mark_asset_copied(session, asset_id, filetype, dst_path)

            done += 1
            _set_progress(ctx, done=done,
                          message=f"Copying {done}/{total_files}…")

            logger.debug(f"Copied: {src_path} → {dst_path}")

        except Exception as e:
            error_count += 1
            logger.error(f"Copy failed [{asset_id} {filetype}]: {src_path} → {e}")
            _set_progress(ctx, message=f"Error on {os.path.basename(src_path)}: {e}")

    # ------------------------------------------------------------------
    # Persist final manifest — one write after all copies complete
    # ------------------------------------------------------------------
    try:
        save_session(session_dir, session)
        logger.info(f"Session manifest saved after copy ({done} files)")
    except Exception as e:
        logger.error(f"Failed to save session manifest post-copy: {e}")

    # ------------------------------------------------------------------
    # Final progress state
    # ------------------------------------------------------------------
    if error_count:
        msg = f"Done with {error_count} error(s). {done}/{total_files} files copied."
    else:
        msg = f"Copy complete — {done} files ready for editing."

    _set_progress(ctx, stage="idle", total=total_files, done=done,
                  active=False, message=msg)

    # Signal UI that copy is complete (existing gate used by /api/thumbs)
    ctx.state["copy_complete"] = True

    logger.info(f"Copy worker finished: {done}/{total_files} files, {error_count} errors")


# =============================================================================
# Helpers
# =============================================================================

def _build_file_tasks(keepers: dict, session_dir: str) -> list[dict]:
    """
    Build a flat list of individual file copy tasks from the keepers dict.

    Skips files where:
        - source path is None (asset registered without that file type)
        - destination already exists and is marked copied in the manifest

    Returns:
        [
            {
                "asset_id": "DSCF0001",
                "filetype": "raw",
                "src":      "/SD/DCIM/DSCF0001.RAF",
                "dst":      "<session_dir>/RAW/DSCF0001.RAF",
            },
            ...
        ]
    """
    tasks = []
    raw_dir = os.path.join(session_dir, "RAW")
    jpg_dir = os.path.join(session_dir, "JPG")

    for asset_id, entry in keepers.items():
        copied = entry.get("copied", {})

        raw_src = entry.get("raw_source")
        jpg_src = entry.get("jpg_source")

        # RAW task
        if raw_src and not copied.get("raw"):
            filename = Path(raw_src).name
            tasks.append({
                "asset_id": asset_id,
                "filetype": "raw",
                "src":      raw_src,
                "dst":      os.path.join(raw_dir, filename),
            })

        # JPG task
        if jpg_src and not copied.get("jpg"):
            filename = Path(jpg_src).name
            tasks.append({
                "asset_id": asset_id,
                "filetype": "jpg",
                "src":      jpg_src,
                "dst":      os.path.join(jpg_dir, filename),
            })

    return tasks


def _set_progress(ctx, stage=None, total=None, done=None, active=None, message=None):
    """
    Update ctx.progress fields. Only updates keys that are explicitly passed.
    Thread-safe for simple dict field writes (GIL protected).
    """
    if stage   is not None: ctx.progress["stage"]   = stage
    if total   is not None: ctx.progress["total"]   = total
    if done    is not None: ctx.progress["done"]    = done
    if active  is not None: ctx.progress["active"]  = active
    if message is not None: ctx.progress["message"] = message