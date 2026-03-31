# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.building.datastruct import Tree

block_cipher = None

# Include photo_core folder so data files come along
photo_core_tree = [(src, dest) for (src, dest, typecode) in Tree("photo_core", prefix="photo_core")]

a = Analysis(
    ["app.py"],
    pathex=["D:\\PyProj\\photo-organizer-packager"],
    binaries=[],
    datas=[("index.html", ".")] + photo_core_tree,
    hiddenimports=[
        "photo_core",
        "photo_core.photo_organizer"
    ],
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