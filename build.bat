REM Role: Build automation script (Windows) (see Stability Contract)
@echo off
setlocal

REM Builds dist\Photo Organizer\Photo Organizer.exe from photo-organizer.spec.
REM ExifTool is bundled from EXIFTOOL_DIR (default C:\Users\Public\Tools\ExifTool).

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo .venv not found - create it and pip install -r requirements.txt first
    exit /b 1
)

echo Cleaning old build output...
rmdir /S /Q build 2>NUL
rmdir /S /Q "dist\Photo Organizer" 2>NUL

echo Building...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean photo-organizer.spec
if errorlevel 1 (
    echo BUILD FAILED
    exit /b 1
)

echo.
echo Built: dist\Photo Organizer\Photo Organizer.exe
endlocal
