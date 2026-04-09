Write-Host "------------------------"
Write-Host " CLEAN + REBUILD START "
Write-Host "------------------------"

# Kill running EXE
Get-Process app -ErrorAction SilentlyContinue | Stop-Process -Force

# Activate venv
$venv = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $venv) {
    & $venv
} else {
    Write-Host "Venv not found"
    exit 1
}

# Delete old build output
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
Remove-Item app.spec -Force -ErrorAction SilentlyContinue

# Delete cache files
Get-ChildItem -Recurse -Filter __pycache__  | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter *.toc        | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter *.pyz        | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter *.pkg        | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "Clean complete."

# Write new app.spec (super simple: 1 line at a time)
Set-Content app.spec '# -*- mode: python ; coding: utf-8 -*-'
Add-Content app.spec ''
Add-Content app.spec 'from PyInstaller.building.datastruct import Tree'
Add-Content app.spec ''
Add-Content app.spec 'block_cipher = None'
Add-Content app.spec ''
Add-Content app.spec 'core_tree = [(src, dest) for (src, dest, typecode) in Tree("core", prefix="core")]'
Add-Content app.spec ''
Add-Content app.spec 'a = Analysis('
Add-Content app.spec '    ["app.py"],'
Add-Content app.spec '    pathex=["D:\\PyProj\\photo-organizer-packager"],'
Add-Content app.spec '    binaries=[],'
Add-Content app.spec '    datas=[("index.html", ".")] + core_tree,'
Add-Content app.spec '    hiddenimports=["core", "core.photo_organizer"],'
Add-Content app.spec '    hookspath=[],'
Add-Content app.spec '    hooksconfig={},'
Add-Content app.spec '    runtime_hooks=[],'
Add-Content app.spec '    excludes=[],'
Add-Content app.spec '    noarchive=False,'
Add-Content app.spec '    optimize=0,'
Add-Content app.spec ')'
Add-Content app.spec ''
Add-Content app.spec 'pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)'
Add-Content app.spec ''
Add-Content app.spec 'exe = EXE('
Add-Content app.spec '    pyz,'
Add-Content app.spec '    a.scripts,'
Add-Content app.spec '    a.binaries,'
Add-Content app.spec '    a.datas,'
Add-Content app.spec '    [],'
Add-Content app.spec '    name="app",'
