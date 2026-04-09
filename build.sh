#!/bin/bash
# Photo Organizer - Cross-Platform Build Script
# Builds standalone apps for Mac, Windows, and Linux

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Photo Organizer Build Script ===${NC}\n"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python3 not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python3 found$(python3 --version)${NC}\n"

# Parse arguments
BUILD_TARGET="${1:-all}"

# Function to build for current OS
build_current_os() {
    OS="$(uname -s)"
    
    case "$OS" in
        Darwin)
            echo -e "${BLUE}Building for macOS...${NC}"
            build_mac
            ;;
        Linux)
            echo -e "${BLUE}Building for Linux...${NC}"
            build_linux
            ;;
        MINGW*|MSYS*|CYGWIN*)
            echo -e "${BLUE}Building for Windows...${NC}"
            build_windows
            ;;
        *)
            echo -e "${RED}Unsupported OS: $OS${NC}"
            exit 1
            ;;
    esac
}

# Mac Build
build_mac() {
    echo "Installing py2app..."
    pip install --break-system-packages py2app
    
    echo "Building Mac .app bundle..."
    python3 setup_mac.py py2app -A
    
    echo -e "${GREEN}✓ Mac app created: dist/Photo\ Organizer.app${NC}"
    echo "  Run: open dist/Photo\ Organizer.app"
}

# Windows Build (requires Windows or cross-compile)
build_windows() {
    echo "Installing PyInstaller..."
    pip install --break-system-packages pyinstaller
    
    echo "Building Windows executable..."
    
    # Use PyInstaller
    pyinstaller --name "PhotoOrganizer" \
        --onefile \
        --windowed \
        --add-data "templates;templates" \
        --add-data "static;static" \
        --collect-all flask \
        --collect-all werkzeug \
        --collect-all jinja2 \
        app.py
    
    echo -e "${GREEN}✓ Windows exe created: dist/PhotoOrganizer.exe${NC}"
    echo "  You can now create an installer with NSIS if desired"
}

# Linux Build (AppImage)
build_linux() {
    echo "Installing PyInstaller..."
    pip install --break-system-packages pyinstaller
    
    echo "Building Linux AppImage..."
    
    pyinstaller --name "PhotoOrganizer" \
        --onefile \
        --add-data "templates:templates" \
        --add-data "static:static" \
        --collect-all flask \
        --collect-all werkzeug \
        --collect-all jinja2 \
        app.py
    
    # Make executable
    chmod +x "$DIST_DIR/PhotoOrganizer"
    
    echo -e "${GREEN}✓ Linux executable created: dist/PhotoOrganizer${NC}"
    echo "  To create AppImage, install appimage-builder and run:"
    echo "  appimage-builder --recipe AppImageBuilder.yml"
}

# Portable Linux (single binary)
build_linux_portable() {
    echo "Building portable Linux binary..."
    
    pip install --break-system-packages pyinstaller
    
    pyinstaller --name "PhotoOrganizer" \
        --onefile \
        --add-data "templates:templates" \
        --add-data "static:static" \
        --collect-all flask \
        --collect-all werkzeug \
        --collect-all jinja2 \
        app.py
    
    chmod +x "$DIST_DIR/PhotoOrganizer"
    
    echo -e "${GREEN}✓ Portable Linux binary: dist/PhotoOrganizer${NC}"
    echo "  Copy this file to any Linux system and run it directly"
}

# Clean build artifacts
clean() {
    echo "Cleaning build artifacts..."
    rm -rf "$BUILD_DIR"
    rm -rf "$DIST_DIR"
    rm -f *.spec
    echo -e "${GREEN}✓ Cleaned${NC}"
}

# Show usage
usage() {
    cat << EOF
Usage: ./build.sh [target]

Targets:
  all          Build for current OS (default)
  mac          Build Mac .app bundle
  windows      Build Windows .exe
  linux        Build Linux AppImage
  linux-portable  Build single portable Linux binary
  clean        Remove build artifacts
  help         Show this help

Examples:
  ./build.sh              # Build for current OS
  ./build.sh mac          # Build Mac app
  ./build.sh windows      # Build Windows exe
  ./build.sh clean        # Clean artifacts

EOF
}

# Main
case "$BUILD_TARGET" in
    all)
        build_current_os
        ;;
    mac)
        build_mac
        ;;
    windows)
        build_windows
        ;;
    linux)
        build_linux
        ;;
    linux-portable)
        build_linux_portable
        ;;
    clean)
        clean
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo -e "${RED}Unknown target: $BUILD_TARGET${NC}\n"
        usage
        exit 1
        ;;
esac

echo -e "\n${GREEN}=== Build Complete ===${NC}"
