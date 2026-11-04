# Role: Culling session manifest (see Stability Contract)

"""
session_state.py

Persistent ingest/culling session state.

Purpose
-------
Tracks workflow state independently from runtime UI caches.

This module is intentionally lightweight and JSON-based.

Runtime state such as:
    - metadataMap
    - thumbnails
    - EXIF caches
    - GPS map data

remain in-memory for performance.

Session manifests persist:
    - source folder
    - selected/rejected assets
    - RAW/JPG pairing
    - copy status
    - working session paths

Design Goals
------------
- non-destructive workflow
- recoverable ingest sessions
- resumable copy operations
- RAW/JPG pairing integrity
- persistent culling decisions

Typical Workflow
----------------
SOURCE CARD
    ↓
Browse directly from source
    ↓
Cull rejects / select keepers
    ↓
Create working session
    ↓
Copy selected assets only
    ↓
Normalize metadata / GPS
    ↓
Ready for editing
    ↓
Archive + format card

Manifest Location
-----------------
sessions/<session_name_timestamp>/session.json
"""

import json
import os
import time
import tempfile
import logging

logger = logging.getLogger("session_state")

MANIFEST_FILENAME = "session.json"

from utils.fs_utils import IMAGE_EXTS_JPEG, IMAGE_EXTS_RAW  # noqa: E402

RAW_EXTENSIONS = set(IMAGE_EXTS_RAW) | {".raw"}
JPG_EXTENSIONS = set(IMAGE_EXTS_JPEG)

# Schema version — bump when manifest structure changes
MANIFEST_VERSION = 1


# =========================================================
# Session Creation
# =========================================================


def create_session(
    base_dir: str, source_folder: str, session_name: str
) -> tuple[str, dict]:
    """
    Create a new timestamped ingest session.

    Responsibilities:
        - create session directory
        - initialize manifest structure
        - persist initial session.json

    Args:
        base_dir:       Root sessions directory (e.g. "sessions/")
        source_folder:  Absolute path to source card / folder being ingested
        session_name:   Human-readable label (e.g. "Wedding_2024")

    Returns:
        (session_dir, session_data)
        session_dir:  absolute path to the new session folder
        session_data: the in-memory manifest dict
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_name = _sanitize_name(session_name)
    folder_name = f"{safe_name}_{timestamp}"
    session_dir = os.path.join(base_dir, folder_name)

    os.makedirs(session_dir, exist_ok=True)

    session_data = {
        "manifest_version": MANIFEST_VERSION,
        "session_id": folder_name,
        "session_name": session_name,
        "created_at": timestamp,
        "source_folder": str(source_folder),
        "session_dir": session_dir,
        "assets": {},
        # assets schema per entry:
        # "<asset_id>": {
        #     "asset_id":    str,
        #     "raw_source":  str | None,   # absolute source path
        #     "jpg_source":  str | None,   # absolute source path
        #     "decision":    "keep" | "reject" | None,   # None = unculled
        #     "selected":    bool,          # decision == "keep"
        #     "copied": {
        #         "raw":  str | None,       # working session path after copy
        #         "jpg":  str | None,
        #     }
        # }
    }

    save_session(session_dir, session_data)
    logger.info(f"Session created: {session_dir}")
    return session_dir, session_data


# =========================================================
# Manifest I/O
# =========================================================


def load_session(session_dir: str) -> dict:
    """
    Load existing session manifest from disk.

    Args:
        session_dir: path to the session folder (contains session.json)

    Returns:
        session_data dict

    Raises:
        FileNotFoundError: if session.json does not exist
        ValueError:        if manifest is corrupt / unreadable
    """
    manifest_path = os.path.join(session_dir, MANIFEST_FILENAME)

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"No session manifest found at: {manifest_path}")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(
            f"Failed to load session manifest: {manifest_path} — {e}"
        ) from e

    _validate_manifest(session_data)
    logger.info(f"Session loaded: {manifest_path}")
    return session_data


def same_photos(session_data: dict, current_files) -> bool:
    """
    True if the session was made from (essentially) the photos in
    `current_files`, not merely from the same folder path.

    Sessions with recorded sizes: at least half of the recorded files that
    are still present by name must also match by size — a different card
    reusing DSCF0001… has different sizes. Older sessions without sizes:
    the photo names must match almost exactly (≥ 90% overlap both ways).
    """
    current = {}
    for p in current_files:
        try:
            current[os.path.basename(p).upper()] = os.path.getsize(p)
        except OSError:
            continue
    if not current:
        return False

    assets = session_data.get("assets", {})
    recorded = {
        name: size
        for a in assets.values()
        for name, size in (a.get("sizes") or {}).items()
    }

    if recorded:
        present = [n for n in recorded if n in current]
        if not present:
            return False
        matches = sum(1 for n in present if current[n] == recorded[n])
        return matches > 0 and matches >= 0.5 * len(present)

    # Legacy manifest: compare photo stems
    stems_now = {n.split(".", 1)[0] for n in current}
    stems_then = {a.upper() for a in assets}
    if not stems_then:
        return False
    overlap = len(stems_now & stems_then)
    return overlap >= 0.9 * len(stems_now) and overlap >= 0.9 * len(stems_then)


def find_latest_session(
    base_dir: str, source_folder: str, current_files=None
) -> tuple[str, dict] | None:
    """
    Find the most recently created session for `source_folder`, so culling
    can resume when the same card/folder is opened again.

    With `current_files`, a session only counts if it was made from these
    photos (same_photos) — otherwise a new card in the same reader slot
    would inherit the previous card's keep/reject decisions.

    Returns (session_dir, session_data) or None.
    """
    target = os.path.normcase(os.path.normpath(str(source_folder)))
    best = None
    current_files = list(current_files) if current_files is not None else None

    try:
        entries = list(os.scandir(base_dir))
    except OSError:
        return None

    for entry in entries:
        if not entry.is_dir():
            continue
        try:
            data = load_session(entry.path)
        except (FileNotFoundError, ValueError):
            continue
        if os.path.normcase(os.path.normpath(data["source_folder"])) != target:
            continue
        if current_files is not None and not same_photos(data, current_files):
            continue
        if best is None or data.get("created_at", "") > best[1].get("created_at", ""):
            best = (entry.path, data)

    return best


def save_session(session_dir: str, session_data: dict) -> None:
    """
    Persist session manifest atomically.

    Uses a temporary file + os.replace() to avoid corruption on crash
    or power loss mid-write.

    Args:
        session_dir:   path to the session folder
        session_data:  in-memory manifest dict to persist
    """
    manifest_path = os.path.join(session_dir, MANIFEST_FILENAME)
    dir_path = os.path.dirname(manifest_path)

    try:
        # Write to a temp file in the same directory so os.replace is atomic
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, manifest_path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as e:
        logger.error(f"Failed to save session manifest: {manifest_path} — {e}")
        raise

    logger.debug(f"Session saved: {manifest_path}")


# =========================================================
# Asset Registration
# =========================================================


def register_asset(
    session_data: dict,
    asset_id: str,
    raw_source: str | None = None,
    jpg_source: str | None = None,
) -> None:
    """
    Add or update an asset entry in the session manifest.

    Idempotent: calling again with the same asset_id updates paths
    without resetting culling decisions already made.

    asset_id should be the stem shared by the RAW/JPG pair:
        e.g.  "DSCF0001"  covers  DSCF0001.RAF + DSCF0001.JPG

    Args:
        session_data:  in-memory manifest dict (mutated in place)
        asset_id:      shared stem identifier for the RAW/JPG pair
        raw_source:    absolute path to RAW file on source, or None
        jpg_source:    absolute path to JPG file on source, or None
    """
    assets = session_data.setdefault("assets", {})

    if asset_id not in assets:
        # New asset — initialize with defaults
        assets[asset_id] = {
            "asset_id": asset_id,
            "raw_source": None,
            "jpg_source": None,
            "decision": None,  # default: not yet culled
            "selected": False,
            "copied": {
                "raw": None,
                "jpg": None,
            },
        }

    entry = assets[asset_id]

    # Update source paths only if provided (allow partial registration)
    if raw_source is not None:
        entry["raw_source"] = str(raw_source)
    if jpg_source is not None:
        entry["jpg_source"] = str(jpg_source)

    # File sizes identify *these* photos: the next card in the reader can
    # reuse the same folder path and file names (DCIM/100_FUJI/DSCF0001).
    for src in (raw_source, jpg_source):
        if src:
            try:
                entry.setdefault("sizes", {})[os.path.basename(str(src)).upper()] = (
                    os.path.getsize(src)
                )
            except OSError:
                pass

    logger.debug(f"Asset registered: {asset_id} (raw={raw_source}, jpg={jpg_source})")


def build_pairs(paths) -> dict[str, dict]:
    """
    Group image paths into RAW/JPG pairs keyed by upper-case stem.

    Returns:
        { "DSCF0001": {"raw": path | None, "jpg": path | None,
                       "_original_stem": "DSCF0001"}, ... }

    Stem comparison is case-insensitive (FAT32 SD cards). Solo-RAW and
    solo-JPG assets are included with the missing partner as None.
    """
    pairs: dict[str, dict] = {}

    for path in paths:
        stem, ext = os.path.splitext(os.path.basename(path))
        key = stem.upper()
        ext = ext.lower()

        if key not in pairs:
            pairs[key] = {"raw": None, "jpg": None, "_original_stem": stem}

        if ext in RAW_EXTENSIONS:
            pairs[key]["raw"] = path
        elif ext in JPG_EXTENSIONS:
            pairs[key]["jpg"] = path

    return pairs


def register_paths(session_data: dict, paths) -> int:
    """
    Register every RAW/JPG pair found in `paths` into the session.

    Idempotent — existing culling decisions are preserved.
    Returns the number of assets registered.
    """
    pairs = build_pairs(paths)
    for entry in pairs.values():
        register_asset(
            session_data,
            entry["_original_stem"],
            raw_source=entry["raw"],
            jpg_source=entry["jpg"],
        )
    return len(pairs)


# =========================================================
# Selection / Culling
# =========================================================


def set_asset_selected(
    session_data: dict,
    asset_id: str,
    selected: bool = True,
) -> None:
    """
    Persist a user culling/selection decision for an asset.

    Args:
        session_data:  in-memory manifest dict (mutated in place)
        asset_id:      asset to update
        selected:      True = keep, False = reject
    """
    assets = session_data.get("assets", {})

    if asset_id not in assets:
        logger.warning(
            f"set_asset_selected: unknown asset_id '{asset_id}' — "
            "call register_asset() before culling."
        )
        return

    assets[asset_id]["selected"] = selected
    assets[asset_id]["decision"] = "keep" if selected else "reject"
    logger.debug(f"Asset '{asset_id}' selected={selected}")


def set_asset_decision(session_data: dict, asset_id: str, decision: str | None) -> None:
    """
    Persist a three-state culling decision: "keep", "reject" or None (unculled).

    Unknown asset_ids are registered without source paths so the decision
    is never dropped.
    """
    if decision not in ("keep", "reject", None):
        raise ValueError(f"decision must be 'keep', 'reject' or None, got {decision!r}")

    assets = session_data.setdefault("assets", {})
    if asset_id not in assets:
        logger.warning(f"set_asset_decision: registering unknown asset_id '{asset_id}'")
        register_asset(session_data, asset_id)

    assets[asset_id]["decision"] = decision
    assets[asset_id]["selected"] = decision == "keep"


def get_decisions(session_data: dict) -> dict:
    """
    Return { asset_id: "keep" | "reject" } for every culled asset.

    Manifests written before the "decision" field existed only stored
    `selected`; those map True → "keep" and False → unculled.
    """
    decisions = {}
    for asset_id, entry in session_data.get("assets", {}).items():
        decision = entry.get("decision")
        if decision is None and "decision" not in entry and entry.get("selected"):
            decision = "keep"
        if decision:
            decisions[asset_id] = decision
    return decisions


def get_selected_assets(session_data: dict) -> dict:
    """
    Return only the keeper assets (selected=True).

    Returns:
        dict of { asset_id: asset_entry } for all selected assets.
        Empty dict if none selected.
    """
    assets = session_data.get("assets", {})
    return {
        asset_id: entry
        for asset_id, entry in assets.items()
        if entry.get("selected", False)
    }


def get_rejected_assets(session_data: dict) -> dict:
    """
    Return only the rejected assets (selected=False).

    Returns:
        dict of { asset_id: asset_entry } for all rejected assets.
    """
    assets = session_data.get("assets", {})
    return {
        asset_id: entry
        for asset_id, entry in assets.items()
        if not entry.get("selected", False)
    }


def get_unculled_assets(session_data: dict) -> dict:
    """
    Return assets that have not yet been reviewed.

    Convention: unculled assets have selected=False and no copy recorded.
    Use this to detect a fresh, untouched asset vs an explicit reject.

    Note: Without a distinct 'reviewed' flag this is an approximation.
    A future manifest version may add  "reviewed": bool  per asset.
    """
    assets = session_data.get("assets", {})
    return {
        asset_id: entry
        for asset_id, entry in assets.items()
        if (
            not entry.get("selected", False)
            and entry.get("copied", {}).get("raw") is None
            and entry.get("copied", {}).get("jpg") is None
        )
    }


# =========================================================
# Copy Tracking
# =========================================================


def mark_asset_copied(
    session_data: dict,
    asset_id: str,
    filetype: str,
    working_path: str,
) -> None:
    """
    Record that a file has been copied into the working session.

    Args:
        session_data:  in-memory manifest dict (mutated in place)
        asset_id:      asset that was copied
        filetype:      "raw" or "jpg"  (case-insensitive)
        working_path:  absolute destination path in the working session
    """
    filetype = filetype.lower()
    if filetype not in ("raw", "jpg"):
        raise ValueError(
            f"mark_asset_copied: filetype must be 'raw' or 'jpg', got '{filetype}'"
        )

    assets = session_data.get("assets", {})
    if asset_id not in assets:
        logger.warning(
            f"mark_asset_copied: unknown asset_id '{asset_id}' — "
            "registering automatically."
        )
        register_asset(session_data, asset_id)

    assets[asset_id].setdefault("copied", {})[filetype] = str(working_path)
    logger.debug(
        f"Asset '{asset_id}' {filetype.upper()} marked copied → {working_path}"
    )


def is_asset_fully_copied(session_data: dict, asset_id: str) -> bool:
    """
    Return True only when BOTH the RAW and JPG (if they exist on source)
    have been copied into the working session.

    Handles solo-RAW and solo-JPG assets correctly.
    """
    assets = session_data.get("assets", {})
    entry = assets.get(asset_id)
    if not entry:
        return False

    copied = entry.get("copied", {})
    has_raw_source = entry.get("raw_source") is not None
    has_jpg_source = entry.get("jpg_source") is not None

    raw_done = (not has_raw_source) or (copied.get("raw") is not None)
    jpg_done = (not has_jpg_source) or (copied.get("jpg") is not None)

    return raw_done and jpg_done


# =========================================================
# Session Summary / Diagnostics
# =========================================================


def session_summary(session_data: dict) -> dict:
    """
    Return a lightweight status snapshot — useful for UI display
    and logging without exposing the full manifest.

    Returns:
        {
            "session_id":      str,
            "source_folder":   str,
            "total_assets":    int,
            "selected":        int,
            "rejected":        int,
            "unculled":        int,
            "copied_complete": int,   # both RAW+JPG copied
        }
    """
    assets = session_data.get("assets", {})
    total = len(assets)
    decisions = get_decisions(session_data)
    selected = sum(1 for d in decisions.values() if d == "keep")
    rejected = sum(1 for d in decisions.values() if d == "reject")
    copied_complete = sum(
        1 for aid in assets if is_asset_fully_copied(session_data, aid)
    )

    return {
        "session_id": session_data.get("session_id", "unknown"),
        "source_folder": session_data.get("source_folder", ""),
        "total_assets": total,
        "selected": selected,
        "rejected": rejected,
        "unculled": total - selected - rejected,
        "copied_complete": copied_complete,
    }


# =========================================================
# Internal Helpers
# =========================================================


def _sanitize_name(name: str) -> str:
    """Strip characters unsafe for directory names."""
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in name)
    return safe[:64]  # cap length


def _validate_manifest(session_data: dict) -> None:
    """
    Minimal schema check on load — catches truncated or wrong-file loads.

    Raises:
        ValueError if required top-level keys are missing.
    """
    required = {"manifest_version", "session_id", "source_folder", "assets"}
    missing = required - session_data.keys()
    if missing:
        raise ValueError(f"Session manifest missing required keys: {missing}")


# =========================================================
# Future Expansion
# =========================================================

# TODO:
# - rating / stars per asset
# - colour labels per asset
# - archive verification flag + checksum per file
# - failed copy retry tracking (retry_count, last_error)
# - session resume: store last-culled asset_id cursor
# - write-back tracking (metadata written back to working copy)
# - session locking (prevent concurrent writes)
