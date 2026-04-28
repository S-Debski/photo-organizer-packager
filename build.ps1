# Role: Build automation script (PowerShell) (see Stability Contract)

Write-Host "========================================="
Write-Host " PHOTO ORGANIZER - POWERFUL BUILD SCRIPT "
Write-Host "=========================================`n"

# -------------------------------
# 1. Activate virtual environment
# -------------------------------
$venvPath = ".\.venv\Scripts\Activate.ps1"

if (Test-Path $venvPath) {
    Write-Host "Activating virtual environment..."
    & $venvPath
} else {
    Write-Host "ERROR: venv not found at $venvPath"
    exit 1
}

Write-Host "`nVirtual environment active.`n"

# ------------------------------------
# 2. Delete ALL old spec files
# ------------------------------------
Write-Host "Removing old spec files..."
Get-ChildItem -Recurse -Filter app.spec -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "Old spec files removed.`n"

# ------------------------------------
# 3. Write a clean new app.spec file
# ------------------------------------
Write-Host "Writing clean app.spec ..."

@'
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.building.datastruct import Tree

block_cipher = None

# IMPORTANT FIX FOR PYINSTALLER 6.x:
# Tree() entries are 3-tuples, but Analysis expects 2-tuples,
# so we flatten them manually.
core_tree = [(src, dest) for (src, dest, typecode) in Tree("core", prefix="core")]

a = Analysis(
    ["app.py"],
    pathex=["D:\\PyProj\\photo-organizer-packager"],
    binaries=[],
    datas=[("index.html", ".")] + core_tree,
    hiddenimports=["core", "core.core"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="app",
    icon="icon.ico",
    debug=False,
    console=False,
)
'@ | Set-Content -Path "app.spec"

Write-Host "app.spec written successfully.`n"

# ------------------------------------
# 4. Run PyInstaller
# ------------------------------------
Write-Host "Running PyInstaller build..."
pyinstaller app.spec

Write-Host "`nBuild complete!"

# ------------------------------------
# 5. Open dist folder or single-file EXE
# ------------------------------------

$folderPath = "dist\app"
$exePath = "dist\app.exe"

if (Test-Path $folderPath) {
    Write-Host "Opening output folder: $folderPath"
    Start-Process $folderPath
}
elseif (Test-Path $exePath) {
    Write-Host "Build produced a single-file executable: $exePath"
    Start-Process "dist"
}
else {
    Write-Host "Build completed, but no output folder or EXE found!"
}