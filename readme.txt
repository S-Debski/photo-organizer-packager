# Role: User-facing documentation (see Stability Contract)

============================================================
Photo Organizer v3.0 (beta) — Hybrid Ingest
============================================================

Import photos from camera cards, external drives or any folder.
Browse and cull the photos where they are, add a location, then copy
the keepers into a dated shoot folder. The source is never changed.

    • Cards and external drives found automatically (Windows, macOS)
    • Any folder: this computer, USB drive or network share (NAS)
    • RAW + JPG kept together (Fuji, Canon, Nikon, Sony, Olympus,
      Pentax, Panasonic, DNG)
    • Fast cached previews, including RAW-only shots
    • Keep / reject with K and X; decisions saved per card
    • Shooting details + location under each photo while culling
    • Right-click: open, open with, show in Explorer / Finder
    • Per-photo camera and lens summary
    • Locations: per folder or all folders, saved places, map
    • Import into <destination>\2026\10\10 - <Shoot title>\ (editable)
    • Location written to the copies: JPG EXIF + .xmp sidecar for RAW
    • Optional: send the imported shoot to an Android phone (adb)

------------------------------------------------------------
INSTALLING
------------------------------------------------------------

Download the latest release from GitHub (no account needed):
    https://github.com/S-Debski/photo-organizer-packager/releases
    PhotoOrganizer-windows.zip  or  PhotoOrganizer-mac.zip

ExifTool is bundled. No Python needed.

WINDOWS
    1. Unzip PhotoOrganizer-windows anywhere.
    2. Keep "Photo Organizer.exe" together with its _internal folder.
    3. Double-click "Photo Organizer.exe".
       SmartScreen (unsigned app): More info → Run anyway.
    4. A tray icon appears and your browser opens the app.
       Tray icon → Open Photo Organizer / Quit.

MACOS
    1. Unzip PhotoOrganizer-mac until you have "Photo Organizer.app"
       (an Actions test build is wrapped in a second zip).
       Apple Silicon, built on macOS 15.
    2. First launch: right-click the app → Open → Open (unsigned app).
    3. If macOS says the app is damaged or can't be verified, run this
       once in Terminal, then open it normally:

           xattr -dr com.apple.quarantine ~/Downloads/"Photo Organizer.app"

       (If you moved it to Applications, use
        /Applications/"Photo Organizer.app" instead.)
    4. The app lives in the menu bar (top right), not the Dock.
       Menu-bar icon → Open Photo Organizer / Quit.
    5. Allow access to removable volumes when asked (needed for cards).

OPTIONAL — SEND TO PHONE (Android, via adb)
    1. Download "SDK Platform-Tools" from
       https://developer.android.com/tools/releases/platform-tools
    2. Windows: unzip so you have
           C:\Users\Public\Tools\platform-tools\adb.exe
       macOS:  brew install --cask android-platform-tools
    3. On the phone: Settings → About phone → tap Build number 7 times,
       then Developer options → USB debugging on.
    4. Plug in and tap Allow on "Allow USB debugging?".
    The app only copies to the phone (DCIM/PhotoOrganizer); it uploads
    nothing. The phone's own backup (e.g. Google Photos) does the rest.

------------------------------------------------------------
USING IT
------------------------------------------------------------

1  CARD        Pick a card or external drive (found automatically), or
               "Choose a folder…". Tick "Also show this computer's disks
               and network drives" for internal disks and NAS shares.
2  FOLDERS     Pick a folder (shoot folders under DCIM are listed).
3  BROWSE      Thumbnails. Hover and press K (keep) or X (reject), or
               click the circle. S / M / L changes the size.
               Click a photo for full screen: shooting details and
               location are shown under it (press I to hide / show).
               Right-click any photo: Keep / Reject, Open JPG / RAW,
               Open with… (Windows), Show in Explorer / Finder,
               Copy file path.
   REVIEW      One photo at a time, full window, with the same details.
4  CAMERAS     Photos per camera and lens.
5  LOCATIONS   Click the map, type coordinates or pick a saved place,
               then "Assign to this folder" or "Use for all folders".
6  IMPORT      Choose a destination, check the shoot title, date and
               folder layout, then Start import → Import kept only or
               Import everything. The exact folder is previewed first.
               When everything is copied you'll see
               "You can now safely format the card."
               Then optionally "Send to phone".

Nothing is overwritten: files already at the destination (or on the
phone) are skipped; a different photo with the same name is reported.

------------------------------------------------------------
WHERE THINGS ARE KEPT
------------------------------------------------------------

Culling decisions, saved locations, saved places:
    ~/Pictures/PhotoWizard/sessions/
Preview cache:
    Windows  %LOCALAPPDATA%\PhotoWizardCache\thumbs\
Log file:
    Windows  %LOCALAPPDATA%\PhotoWizardCache\photo-organizer.log
    macOS    ~/Library/Logs/PhotoOrganizer/photo-organizer.log

------------------------------------------------------------
TROUBLESHOOTING
------------------------------------------------------------

Keep ONE copy of the app
    • Starting the app when a copy is already running just opens the
      running one, even if it's an older copy somewhere else (e.g. an
      old download). If the app looks out of date: tray icon → Quit,
      then start the copy you want. Delete old copies; your decisions,
      locations and saved places are stored separately and are kept.
"Photo Organizer isn't running"
    • The page was left open after the app quit. Start the app again
      (or tray icon → Open Photo Organizer), then reload the page.
Card not listed
    • Wait a second and switch back to the app window, or press Detect.
    • Still missing: tick "Also show…" or use "Choose a folder…".
No dates / camera names / thumbnails
    • Check the log for a line starting "ExifTool:". If it says
      "ExifTool not found", the build is incomplete.
"No phone connected"
    • USB debugging on, cable connected, Allow tapped on the phone.
The app seems to do nothing when started
    • It's already running: look for the tray / menu-bar icon.
Port in use (e.g. macOS AirPlay on 5000)
    • Handled automatically: the app checks ports 5000-5009 and uses
      the first free one. The address is in the log ("Using http://…").

------------------------------------------------------------
RUNNING FROM SOURCE
------------------------------------------------------------

    python -m venv .venv
    .\.venv\Scripts\activate            (macOS: source .venv/bin/activate)
    pip install -r requirements.txt
    python app.py                       → http://127.0.0.1:5000

ExifTool must be installed when running from source (see the vault
readme: docs/Obsidian Vault/Photo Organiser Book/readme.md.md).

Tests:
    python -m unittest discover -s tests -v

------------------------------------------------------------
BUILDING
------------------------------------------------------------

    Windows   build.bat        → dist\Photo Organizer\Photo Organizer.exe
    macOS     ./build_mac.sh   → dist/Photo Organizer.app
    Both      GitHub Actions → "Build desktop apps" → Run workflow
              (test builds, under the run's Artifacts)

Releasing: push a tag, e.g.
    git tag v3.0.0-beta.2
    git push origin v3.0.0-beta.2
builds both apps and publishes them on the Releases page.
A tag with a "-" (beta, rc) is marked pre-release.

Spec: photo-organizer.spec. Design notes: docs/Obsidian Vault/.

------------------------------------------------------------
FILE STRUCTURE
------------------------------------------------------------

app.py                       Entry point, tray, logging
backend/api_server.py        Flask app and routes
backend/routes/              Analyse, thumbnails, GPS, write-GPS
backend/services/sdcard.py   Cards, external drives, network drives
photo_core/                  EXIF, sessions, destination, export
workers/exif_scanner.py      Background EXIF scan
utils/                       File helpers, thumbnail cache
templates/index.html         Page
ui/static/                   JS, CSS, local libraries
tests/                       Pipeline tests

------------------------------------------------------------
LICENSE
------------------------------------------------------------

MIT License — see LICENSE. Copyright (c) 2026 Steve Debski.

Third-party software, each under its own licence:
    ExifTool (Phil Harvey)       — bundled in app builds; Perl licence
                                   (Artistic / GPL), https://exiftool.org
    Bootstrap, Bootstrap Icons   — MIT
    Leaflet                      — BSD 2-Clause
    Map tiles © OpenStreetMap contributors (ODbL)
    Python packages: Flask (BSD), Pillow (MIT-CMU), pystray (LGPL),
                     pywin32 (PSF), PyInstaller (GPL with bootloader
                     exception)
    Android SDK Platform-Tools (adb) — not included; installed by the
                                   user under Google's terms

------------------------------------------------------------
VERSION
------------------------------------------------------------

Photo Organizer v3.0.0 (beta) — Hybrid Ingest
November 2026
