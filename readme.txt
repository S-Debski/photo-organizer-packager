============================================================
Photo Organizer v2.7 — Advanced EXIF Edition
============================================================

This application ingests photos from SD / CFexpress cards and
organizes them automatically using:

    • Camera Model (EXIF)
    • Lens Model (EXIF)
    • Event Name (chosen by user)
    • RAW + JPG support
    • Smart Defaults (auto-mapping based on EXIF)
    • Live progress bar + percent + ETA
    • Real-time backend logs (SSE)
    • RAW thumbnail preview
    • Full-size RAW decoding on double-click
    • Charting for camera/lens usage

It is designed for multi-camera shoots, rapid culling, and high-speed
import workflows similar to Lightroom, PhotoMechanic, etc.

------------------------------------------------------------
REQUIREMENTS
------------------------------------------------------------

1. Windows (10 or later)
2. Python 3.10–3.12 (if running from source)
3. RAW engines:
   - Pillow (JPG/PNG)
   - rawpy (RAW: ARW, NEF, CR2, CR3, RAF, ORF, RW2)
4. Flask (backend)
5. SD card reader

If running the EXE version: no Python needed.

------------------------------------------------------------
RUNNING FROM SOURCE
------------------------------------------------------------

1. Create & activate a venv:
       python -m venv .venv
       .\.venv\Scripts\activate

2. Install dependencies:
       pip install flask flask-cors pillow rawpy pywin32

3. Launch the app:
       python app.py

4. Open browser:
       http://127.0.0.1:5000

------------------------------------------------------------
EXE VERSION (No Python Required)
------------------------------------------------------------

Double-click:
    dist\Photo Organizer\Photo Organizer.exe

Everything is bundled, including:
    • rawpy
    • Pillow
    • pythoncom/win32
    • templates/static/js/css

------------------------------------------------------------
BUILDING THE EXE YOURSELF
------------------------------------------------------------

1. Activate venv:
       .\.venv\Scripts\activate

2. Build:
       build_exe.bat

3. Final EXE appears in:
       dist\Photo Organizer\Photo Organizer.exe

------------------------------------------------------------
APPLICATION WORKFLOW
------------------------------------------------------------

STEP 1 — Select SD Card  
 • Automatically detects SD / CFexpress cards  
 • Choose a card and click "Analyze"  

STEP 2 — Analyze  
 • Scans folders  
 • Extracts EXIF camera + lens from first image  
 • Shows photo counts per folder  

STEP 3 — Camera + Lens Stats  
 • Lists counts per camera and lens  
 • Shows interactive bar charts (Chart.js)  

STEP 4 — Thumbnails  
 • Displays JPG previews  
 • RAW thumbnails extracted from embedded preview  
 • Double-click → full RAW decode (JPEG 95%)  

STEP 5 — Mapping  
 • For each folder, set:
       - Camera
       - Lens
       - Event
 • Use Smart Defaults to auto-fill based on EXIF
 • Preview table shows final mapping  

STEP 6 — Organize  
 • Copies photos to:
       Pictures/Organized/{Camera}/{Event}/
 • Shows:
       - Progress
       - Percent
       - ETA (live updated)
 • “Open Pictures Folder” opens the destination

STEP 7 — Logs  
 • Live backend logs via SSE  
 • Each operation prints updates  

STEP 8 — Settings  
 • Toggle automatic log scrolling  

------------------------------------------------------------
KNOWN BEHAVIOUR
------------------------------------------------------------

• RAW decode for full-size preview can be slow on older CPUs.  
• Some older RAW formats may not include embedded previews.  
• If camera/lens EXIF missing → defaults to "Unknown".  

------------------------------------------------------------
TROUBLESHOOTING
------------------------------------------------------------

1. SD cards not detected:
   • Ensure EXE run as administrator (sometimes required for drive access)
   • Check that pythoncom/win32 libs are included (PyInstaller spec handles this)

2. Thumbnails missing:
   • Some RAW types embed low-resolution previews
   • Full-size RAW still works (double-click)

3. Mapping errors:
   • Step 6 requires ALL selected folders have Camera + Lens + Event
   • Smart Defaults auto-fills most fields

4. Progress stuck at 0:
   • update_progress() must exist in app.py v2.7
   • Use complete v2.7 backend

------------------------------------------------------------
FILE STRUCTURE
------------------------------------------------------------

photo-organizer-packager/
│
├── app.py                     (Backend server)
├── build_exe.bat              (Build script)
├── photo_organizer.spec       (PyInstaller spec)
│
├── templates/
│   └── index.html             (UI)
│
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
│       └── main.js
│
└── photo_core/
    └── photo_organizer.py     (EXIF + RAW scanning engine)

------------------------------------------------------------
LICENSE
------------------------------------------------------------

All rights reserved by the project author.
Free for personal or internal organizational use.

------------------------------------------------------------
VERSION
------------------------------------------------------------

Photo Organizer v2.7  
Advanced EXIF Edition  
March 2026

## Codebase Responsibilities

The project follows a clear separation of concerns. Each major file or folder has a single, well-defined responsibility:

| File / Directory              | Responsibility |
|------------------------------|----------------|
| `app.py`                     | Application bootstrap, version definition, and logging setup |
| `backend/api_server.py`      | Single Flask application instance and route registration |
| `backend/routes/`            | Feature-specific API endpoints (SD detection, analyze, EXIF, thumbnails, GPS, organize) |
| `workers/`                   | Background processing (EXIF scanning, thumbnailing, folder watching) |
| `templates/index.html`       | UI markup (served by Flask via `render_template`) |
| `ui/static/js/main.js`       | Frontend behaviour and UI logic |
| `ui/static/css/styles.css`   | UI styling and layout |
``


