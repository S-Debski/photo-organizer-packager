## Optional: ExifTool (Recommended)

For full camera and lens metadata detection, Photo Organizer can use
[ExifTool](https://exiftool.org), the industry‑standard metadata utility.

Without ExifTool:
- Camera detection still works
- Lens detection may be limited on some mirrorless cameras

### Installation

**Windows**
- Download from https://exiftool.org
- Ensure `exiftool.exe` is on your PATH

**macOS**
```bash
brew install exiftool
``

### Optional: ExifTool (Recommended)

Photo Organizer can use ExifTool to read advanced camera and lens metadata
(MakerNotes, XMP, mirrorless lenses).

ExifTool may be installed in any folder that is on your PATH.
Administrator rights are not required.

Recommended shared location on Windows:
C:\Users\Public\Tools\ExifTool

This does not require admin rights.

Press Win + R
Run:
rundll32 sysdm.cpl,EditEnvironmentVariables

Under User variables (top half):

Click New…

Add:

Variable name:
PHOTO_ORGANIZER_EXIFTOOL

Variable value:
C:\Users\Public\Tools\ExifTool\exiftool.exe

OK → OK → OK
Restart PyCharm / terminal / app

✅ This works on:

corporate PCs
locked‑down machines
non‑admin accounts

THIS also works:
Also user‑level, no admin required:

1. Same dialog (`EditEnvironmentVariables`)
2. Under **User variables**, select `Path`
3. Add:
    
    ```
    C:\Users\Public\Tools\ExifTool
    ```
    
4. Restart PyCharm

Then:

PowerShell

exiftool -ver  

Show more lines

✅ This is the _standard_ Unix‑style solution  
✅ Works cross‑platform  
✅ Less app‑specific