@echo off
echo ================================
echo PHOTO ORGANIZER - BUILD SCRIPT
echo ================================
echo.

REM --- CLEAN OLD BUILDS ---
echo Cleaning old build folders...
rmdir /S /Q build 2>NUL
rmdir /S /Q dist 2>NUL
del app.spec 2>NUL
echo Done.
echo.

REM --- GENERATE INITIAL SPEC ---
echo Generating base spec file...
pyinstaller app.py --name app --icon icon.ico --splash splash.png --noconsole --specpath .
echo Base spec created.
echo.

REM --- PATCH SPEC FILE ---
echo Patching spec file with correct datas and Tree()...
(
    echo # -*- mode: python ; coding: utf-8 -*-
    echo.
    echo from PyInstaller.building.datastruct import Tree
    echo block_cipher = None
    echo.
    echo a = Analysis(
    echo     ['app.py'],
    echo     pathex=['%CD%'],
    echo     binaries=[],
    echo     datas=[
    echo         ('index.html','.'),              # copy index.html
    echo         Tree('core', prefix='core'),     # copy entire core/ folder
    echo     ],
    echo     hiddenimports=[
    echo         'core',
    echo         'core.core',
    echo         'win32file',
    echo         'win32con',
    echo         'pywintypes',
    echo         'pythoncom',
    echo     ],
    echo     hookspath=[],
    echo     hooksconfig={},
    echo     runtime_hooks=[],
    echo     excludes=[],
    echo     noarchive=False,
    echo     optimize=0,
    echo )
    echo.
    echo pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
    echo.
    echo exe = EXE(
    echo     pyz,
    echo     a.scripts,
    echo     a.binaries,
    echo     a.datas,
    echo     [],
    echo     name='app',
    echo     version='version.txt',
    echo     icon='icon.ico',
    echo     splash='splash.png',
    echo     debug=False,
    echo     bootloader_ignore_signals=False,
    echo     strip=False,
    echo     upx=True,
    echo     upx_exclude=[],
    echo     runtime_tmpdir=None,
    echo     console=False,
    echo )
) > app.spec

echo Spec file updated.
echo.

REM --- RUN THE FINAL BUILD ---
echo Running PyInstaller final build...
pyinstaller app.spec
echo.
echo Build complete.
echo.

REM --- OPEN OUTPUT FOLDER ---
echo Opening dist folder...
explorer dist\app