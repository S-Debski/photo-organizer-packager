REM Role: Windows build automation (see Stability Contract)

@echo off
echo === Building Photo Organizer for Windows ===

REM Activate venv
call venv\Scripts\activate

REM Clean old PyInstaller builds
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

REM Build using spec file
pyinstaller --clean --noconfirm photo-organizer-win.spec

echo.
echo ✅ Windows build complete!
pause
