#!/usr/bin/env python3
"""
Photo Organizer Flask App - Clean Version
"""

import photo_core.photo_organizer as _po  # noqa: F401
from photo_core import PhotoOrganizer

import logging
import os
import sys
import threading
import time

from flask import Flask, request, jsonify
from flask_cors import CORS

# Works anywhere (external disk, etc)
if getattr(sys, 'frozen', False):
    APP_DIR = sys._MEIPASS
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global state
organizer = PhotoOrganizer()
current_job = {
    'status': 'idle',
    'progress': 0,
    'total': 0,
    'message': '',
    'errors': []
}
job_lock = threading.Lock()

# Timeout settings
INACTIVITY_TIMEOUT = 1800
last_activity_time = time.time()
shutdown_timer = None


def update_last_activity():
    global last_activity_time
    last_activity_time = time.time()


def reset_shutdown_timer():
    global shutdown_timer
    if shutdown_timer:
        shutdown_timer.cancel()
    shutdown_timer = threading.Timer(INACTIVITY_TIMEOUT, shutdown_due_to_inactivity)
    shutdown_timer.daemon = True
    shutdown_timer.start()


def shutdown_due_to_inactivity():
    logger.info(f"No activity for {INACTIVITY_TIMEOUT} seconds. Shutting down...")
    print("\n" + "=" * 60)
    print("INACTIVITY TIMEOUT - Shutting down server")
    print("=" * 60)
    os._exit(0)


def update_progress(current, total):
    global current_job
    with job_lock:
        current_job['progress'] = current
        current_job['total'] = total


# Routes

from pathlib import Path
from flask import Response

# earlier in file APP_DIR is already set
INDEX_PATH = Path(APP_DIR) / "index.html"

@app.route('/', methods=['GET'])
def index():
    update_last_activity()
    reset_shutdown_timer()
    try:
        with INDEX_PATH.open('r', encoding='utf-8') as f:
            return Response(f.read(), mimetype='text/html; charset=utf-8')
    except Exception as e:
        logger.error(f"Error serving index.html from {INDEX_PATH}: {e}")
        return f"<h1>Error loading UI</h1><p>{str(e)}</p>", 500


@app.route('/api/health', methods=['GET'])
def health():
    update_last_activity()
    reset_shutdown_timer()
    return jsonify({'status': 'ok'})


@app.route('/api/sd-cards', methods=['GET'])
def get_sd_cards():
    update_last_activity()
    reset_shutdown_timer()
    try:
        drives = organizer.list_sd_cards()
        return jsonify({'success': True, 'drives': drives})
    except Exception as e:
        logger.error(f"Error listing SD cards: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sd-card-info', methods=['POST'])
def get_sd_card_info():
    """Get SD card information including name and manufacturer"""
    update_last_activity()
    reset_shutdown_timer()

    data = request.get_json()
    sd_card_path = data.get('sd_card_path')

    if not sd_card_path:
        return jsonify({'success': False, 'error': 'sd_card_path required'}), 400

    if not Path(sd_card_path).exists():
        return jsonify({'success': False, 'error': 'SD card path does not exist'}), 400

    try:
        card_info = organizer.get_sd_card_info(sd_card_path)
        return jsonify({
            'success': True,
            'info': card_info
        })
    except Exception as e:
        logger.error(f"Error getting SD card info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analyze-card', methods=['POST'])
def analyze_card():
    """Analyze SD card structure to find photo folders"""
    update_last_activity()
    reset_shutdown_timer()

    data = request.get_json()
    sd_card_path = data.get('sd_card_path')

    if not sd_card_path:
        return jsonify({'success': False, 'error': 'sd_card_path required'}), 400

    if not Path(sd_card_path).exists():
        return jsonify({'success': False, 'error': 'SD card path does not exist'}), 400

    try:
        analysis = organizer.analyze_card(sd_card_path)
        return jsonify({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        logger.error(f"Error analyzing card: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/photos', methods=['GET'])
def get_photos():
    update_last_activity()
    reset_shutdown_timer()
    directory = request.args.get('directory')
    if not directory:
        return jsonify({'success': False, 'error': 'directory parameter required'}), 400
    try:
        photos = organizer.find_photo_files(directory)
        return jsonify({'success': True, 'photos': photos, 'count': len(photos)})
    except Exception as e:
        logger.error(f"Error listing photos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/check-duplicates', methods=['POST'])
def check_duplicates():
    """Quick check for duplicate photos by filename"""
    global organizer
    update_last_activity()
    reset_shutdown_timer()

    data = request.get_json()
    folder_mapping = data.get('folder_mapping')
    sd_card_folder_name = data.get('sd_card_folder_name')

    if not folder_mapping:
        return jsonify({'success': False, 'error': 'folder_mapping required'}), 400

    try:
        # Reinitialize organizer with the SD card name so it can find existing photos
        if sd_card_folder_name:
            organizer = PhotoOrganizer(sd_card_name=sd_card_folder_name)
            logger.info(f"Check-duplicates using SD card folder: {sd_card_folder_name}")

        duplicates_found = []
        total_checked = 0

        # Get all existing photo filenames in destination
        existing_files = set()
        if organizer.sd_card_root and organizer.sd_card_root.exists():
            for item in organizer.sd_card_root.rglob('*'):
                if item.is_file() and organizer._is_photo(item):
                    existing_files.add(item.name)

        # Check each source photo filename against existing
        for folder_info in folder_mapping:
            source_path = folder_info.get('path')
            if not source_path:
                continue

            photos = organizer.find_photo_files(source_path)
            total_checked += len(photos)

            for photo_file in photos:
                filename = Path(photo_file).name
                if filename in existing_files:
                    duplicates_found.append(filename)

        return jsonify({
            'success': True,
            'duplicates_found': len(duplicates_found),
            'total_checked': total_checked,
            'duplicates': list(set(duplicates_found))[:10]  # Unique, first 10
        })
    except Exception as e:
        logger.error(f"Error checking duplicates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/organize', methods=['POST'])
def organize_photos():
    global current_job, organizer
    update_last_activity()
    reset_shutdown_timer()

    data = request.get_json()
    if not data.get('sd_card_path'):
        return jsonify({'success': False, 'error': 'sd_card_path required'}), 400

    # Get SD card folder name (e.g., "NO NAME (Panasonic)")
    sd_card_folder_name = data.get('sd_card_folder_name')
    if sd_card_folder_name:
        # Reinitialize organizer with custom SD card name
        organizer = PhotoOrganizer(sd_card_name=sd_card_folder_name)
        logger.info(f"Using SD card folder: {sd_card_folder_name}")

    # Support both old format (single folder) and new format (multiple folders)
    folder_mapping = data.get('folder_mapping')  # New: list of {folder_path, camera_name, event_name}
    camera_name = data.get('camera_name')  # Old: single camera for all
    event_name = data.get('event_name')  # Old: single event for all

    if not folder_mapping and not camera_name:
        return jsonify({'success': False, 'error': 'camera_name or folder_mapping required'}), 400

    if not Path(data['sd_card_path']).exists():
        return jsonify({'success': False, 'error': 'SD card path does not exist'}), 400

    def job_worker():
        global current_job
        try:
            with job_lock:
                current_job['status'] = 'copying'
                current_job['message'] = 'Scanning photos...'
                current_job['progress'] = 0
                current_job['total'] = 0
                current_job['errors'] = []

            total_copied = 0

            # Handle folder mapping (new smart workflow)
            if folder_mapping:
                for folder_info in folder_mapping:
                    folder_path = folder_info.get('path')  # Changed from 'folder_path' to 'path'
                    cam_name = folder_info.get('camera_name')
                    evt_name = folder_info.get('event_name')

                    if not folder_path or not cam_name:
                        continue

                    # Create folder
                    camera_folder = organizer.create_camera_folder(cam_name, event_name=evt_name)

                    # Copy photos from this folder
                    photo_files = organizer.find_photo_files(folder_path)
                    total_files = len(photo_files)

                    with job_lock:
                        current_job['total'] += total_files

                    copied, errors = organizer.copy_photos(
                        folder_path,
                        camera_folder,
                        progress_callback=update_progress
                    )

                    total_copied += copied
                    with job_lock:
                        current_job['errors'].extend(errors)
            else:
                # Handle old format (single camera/event)
                camera_folder = organizer.create_camera_folder(
                    camera_name,
                    event_name=event_name
                )

                # Count photos
                photo_files = organizer.find_photo_files(data['sd_card_path'])
                total_photos = len(photo_files)

                with job_lock:
                    current_job['total'] = total_photos
                    current_job['message'] = f'Copying {total_photos} photos...'
                    current_job['progress'] = 0

                # Copy photos
                copied, errors = organizer.copy_photos(
                    data['sd_card_path'],
                    camera_folder,
                    progress_callback=update_progress
                )
                total_copied = copied
                with job_lock:
                    current_job['errors'].extend(errors)

            with job_lock:
                current_job['status'] = 'complete' if not current_job['errors'] else 'error'
                current_job['message'] = f"Copied {total_copied} photos"
                current_job['progress'] = total_copied

        except Exception as e:
            logger.error(f"Job worker error: {e}")
            with job_lock:
                current_job['status'] = 'error'
                current_job['message'] = str(e)
                current_job['errors'].append(str(e))

    if current_job['status'] not in ['idle', 'complete', 'error']:
        return jsonify({'success': False, 'error': 'A job is already running'}), 409

    thread = threading.Thread(target=job_worker, daemon=True)
    thread.start()
    return jsonify({'success': True, 'message': 'Job started'})


@app.route('/api/job-status', methods=['GET'])
def get_job_status():
    update_last_activity()
    reset_shutdown_timer()
    with job_lock:
        status = {
            'status': current_job['status'],
            'progress': current_job['progress'],
            'total': current_job['total'],
            'message': current_job['message'],
            'errors': current_job['errors']
        }
    return jsonify(status)


@app.route('/api/stats', methods=['GET'])
def get_stats():
    update_last_activity()
    reset_shutdown_timer()
    try:
        stats = organizer.get_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/eject-card', methods=['POST'])
def eject_card():
    """Eject an SD card safely"""
    update_last_activity()
    reset_shutdown_timer()

    data = request.get_json()
    card_path = data.get('card_path')

    if not card_path:
        return jsonify({'success': False, 'error': 'card_path required'}), 400

    try:
        import subprocess

        if sys.platform == 'darwin':  # Mac
            # Try unmount first (more reliable than eject)
            try:
                result = subprocess.run(['diskutil', 'unmount', card_path],
                                        capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    logger.info(f"Unmounted card: {card_path}")
                    return jsonify({'success': True, 'message': f'Card ejected: {card_path}'})
                else:
                    # If unmount fails, try eject
                    result = subprocess.run(['diskutil', 'eject', card_path],
                                            capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        logger.info(f"Ejected card: {card_path}")
                        return jsonify({'success': True, 'message': f'Card ejected: {card_path}'})
                    else:
                        logger.error(f"Eject failed: {result.stderr}")
                        return jsonify(
                            {'success': False, 'error': 'Card may be in use. Close all files and try again.'}), 400
            except subprocess.TimeoutExpired:
                return jsonify({'success': False, 'error': 'Eject command timed out'}), 500

        elif os.name == 'nt':  # Windows
            try:
                subprocess.run(['eject', card_path], check=True, capture_output=True, timeout=5)
                logger.info(f"Ejected card: {card_path}")
                return jsonify({'success': True, 'message': f'Card ejected: {card_path}'})
            except subprocess.TimeoutExpired:
                return jsonify({'success': False, 'error': 'Eject command timed out'}), 500
        else:  # Linux
            try:
                subprocess.run(['eject', card_path], check=True, capture_output=True, timeout=5)
                logger.info(f"Ejected card: {card_path}")
                return jsonify({'success': True, 'message': f'Card ejected: {card_path}'})
            except subprocess.TimeoutExpired:
                return jsonify({'success': False, 'error': 'Eject command timed out'}), 500

    except Exception as e:
        logger.error(f"Error ejecting card: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pictures-path', methods=['GET'])
def get_pictures_path():
    update_last_activity()
    reset_shutdown_timer()
    path = str(organizer.pictures_base)

    try:
        if sys.platform == 'darwin':
            os.system(f'open "{path}"')
        elif sys.platform == 'win32':
            os.startfile(path)
        else:
            os.system(f'xdg-open "{path}"')
    except Exception as e:
        logger.warning(f"Could not open folder: {e}")

    return jsonify({'success': True, 'path': path})


if __name__ == '__main__':
    import webbrowser
    import threading
    import time

    debug_mode = not getattr(sys, 'frozen', False)


    def open_browser():
        time.sleep(2)
        webbrowser.open('http://127.0.0.1:5000')


    if not debug_mode:
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,
        use_reloader=False,
        use_debugger=False
    )
