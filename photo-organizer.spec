# -*- mode: python ; coding: utf-8 -*-
# Role: Build configuration (see Stability Contract)
#
# PyInstaller spec for Windows and macOS (Linux: later).
#
#   Windows:  build.bat          -> dist\Photo Organizer\Photo Organizer.exe
#   macOS:    ./build_mac.sh     -> dist/Photo Organizer.app
#
# ExifTool is bundled into <bundle>/exiftool/ so the app runs standalone.
# Set EXIFTOOL_DIR to the folder to bundle:
#   Windows: folder containing exiftool.exe + exiftool_files\
#   macOS:   Image-ExifTool distribution (exiftool script + lib/)
# If unset/missing, the build still works and the app falls back to an
# installed exiftool (PATH / Homebrew).

import os
import sys

sys.path.insert(0, SPECPATH)
from version import APP_NAME, APP_VERSION  # noqa: E402

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

datas = [
    ("templates", "templates"),
    ("ui/static", "ui/static"),
    ("assets", "assets"),
]

default_exiftool = r"C:\Users\Public\Tools\ExifTool" if IS_WIN else ""
exiftool_dir = os.environ.get("EXIFTOOL_DIR", default_exiftool)
exe_name = "exiftool.exe" if IS_WIN else "exiftool"
if exiftool_dir and os.path.isfile(os.path.join(exiftool_dir, exe_name)):
    datas.append((exiftool_dir, "exiftool"))
    print(f"Bundling ExifTool from {exiftool_dir}")
else:
    print("WARNING: ExifTool not bundled — set EXIFTOOL_DIR")

hiddenimports = []
if IS_WIN:
    hiddenimports += ["win32api", "win32file", "win32con", "pywintypes",
                      "pythoncom", "pystray._win32"]
if IS_MAC:
    hiddenimports += ["pystray._darwin"]

a = Analysis(
    ["app.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Not used by the app; keep the bundle small
    excludes=["rawpy", "numpy", "matplotlib", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # UI is the browser + tray icon; logs go to a file
    icon="assets/icon.ico" if IS_WIN else "assets/icon.icns",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon="assets/icon.icns",
        bundle_identifier="com.photoorganizer.app",
        version=APP_VERSION,
        info_plist={
            "CFBundleShortVersionString": APP_VERSION,
            "NSHighResolutionCapable": True,
            # Menu-bar app: the UI is a browser tab, so no Dock icon
            "LSUIElement": True,
            "NSRemovableVolumesUsageDescription":
                "Photo Organizer reads photos from your camera cards.",
            "NSDocumentsFolderUsageDescription":
                "Photo Organizer copies imported photos to the folder you choose.",
            "NSDesktopFolderUsageDescription":
                "Photo Organizer copies imported photos to the folder you choose.",
            "NSDownloadsFolderUsageDescription":
                "Photo Organizer copies imported photos to the folder you choose.",
        },
    )
