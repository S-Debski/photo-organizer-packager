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


MANIFEST_FILENAME = "session.json"


# =========================================================
# Session Creation
# =========================================================

def create_session(base_dir, source_folder, session_name):
    """
    Create a new timestamped ingest session.

    Responsibilities:
        - create session directory
        - initialize manifest structure
        - persist initial session.json

    Returns:
        (session_dir, session_data)
    """
    pass


# =========================================================
# Manifest I/O
# =========================================================

def load_session(session_dir):
    """
    Load existing session manifest from disk.
    """
    pass


def save_session(session_dir, session_data):
    """
    Persist session manifest atomically.

    Uses temporary file + replace to avoid corruption.
    """
    pass


# =========================================================
# Asset Registration
# =========================================================

def register_asset(
    session_data,
    asset_id,
    raw_source=None,
    jpg_source=None
):
    """
    Add or update an asset in the session manifest.

    asset_id should represent RAW/JPG pairs:
        DSCF0001
    """
    pass


# =========================================================
# Selection / Culling
# =========================================================

def set_asset_selected(
    session_data,
    asset_id,
    selected=True
):
    """
    Persist user culling/selection decision.
    """
    pass


def get_selected_assets(session_data):
    """
    Return selected keeper assets.
    """
    pass


# =========================================================
# Copy Tracking
# =========================================================

def mark_asset_copied(
    session_data,
    asset_id,
    filetype,
    working_path
):
    """
    Mark RAW/JPG asset as copied into working session.
    """
    pass


# =========================================================
# Future Expansion
# =========================================================

# TODO:
# - rating / stars
# - colour labels
# - archive verification
# - checksum validation
# - failed copy retry tracking
# - session resume
# - write-back tracking

