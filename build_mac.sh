#!/usr/bin/env bash
# Role: Build automation script (macOS) (see Stability Contract)
#
# Builds "dist/Photo Organizer.app" and a zip of it from photo-organizer.spec.
# Bundles ExifTool (Image-ExifTool, runs on the system perl).
#
#   ./build_mac.sh                   # downloads ExifTool if needed
#   EXIFTOOL_DIR=/path ./build_mac.sh
set -euo pipefail
cd "$(dirname "$0")"

# Current release number; set EXIFTOOL_VERSION to pin one
EXIFTOOL_VERSION="${EXIFTOOL_VERSION:-$(curl -fsSL https://exiftool.org/ver.txt | tr -d '[:space:]')}"

if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt pyinstaller pystray
fi

if [ -z "${EXIFTOOL_DIR:-}" ]; then
    EXIFTOOL_DIR="build/exiftool-mac/Image-ExifTool-${EXIFTOOL_VERSION}"
    if [ ! -f "$EXIFTOOL_DIR/exiftool" ]; then
        mkdir -p build/exiftool-mac
        # exiftool.org links its downloads to SourceForge
        curl -fsSL "https://sourceforge.net/projects/exiftool/files/Image-ExifTool-${EXIFTOOL_VERSION}.tar.gz/download" \
            | tar -xz -C build/exiftool-mac
    fi
fi
export EXIFTOOL_DIR

rm -rf "dist/Photo Organizer" "dist/Photo Organizer.app"
.venv/bin/python -m PyInstaller --noconfirm photo-organizer.spec

# Make sure the bundled exiftool script stays executable
find "dist/Photo Organizer.app" -path "*exiftool/exiftool" -type f -exec chmod +x {} +

# Unsigned build: ad-hoc sign so Apple Silicon will launch it
codesign --force --deep --sign - "dist/Photo Organizer.app"

(cd dist && ditto -c -k --keepParent "Photo Organizer.app" "PhotoOrganizer-mac.zip")
echo "Built: dist/Photo Organizer.app (and dist/PhotoOrganizer-mac.zip)"
