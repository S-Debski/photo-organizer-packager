## Installing the App (v3.0)

Download from GitHub → Actions → latest "Build desktop apps" run → Artifacts.
ExifTool is bundled; nothing else is required for importing.

### Windows
- Unzip `PhotoOrganizer-windows`
- Keep `Photo Organizer.exe` together with its `_internal` folder
- SmartScreen warning (unsigned) → More info → Run anyway
- Tray icon → Open Photo Organizer / Quit

### macOS
- Unzip `PhotoOrganizer-mac` until you have `Photo Organizer.app` (GitHub wraps it in a second zip)
- First launch: right‑click → Open → Open (unsigned app)
- If macOS says the app is damaged or can't be verified, run once in Terminal, then open normally:

```bash
xattr -dr com.apple.quarantine ~/Downloads/"Photo Organizer.app"
```

- Moved it to Applications first? Use that path instead:

```bash
xattr -dr com.apple.quarantine /Applications/"Photo Organizer.app"
```

- Menu‑bar icon (no Dock icon) → Open Photo Organizer / Quit
- Allow access to removable volumes when asked (needed to read cards)
- Log: `~/Library/Logs/PhotoOrganizer/photo-organizer.log`

### Optional: Send to Phone (adb)
- Download Android "SDK Platform‑Tools" from developer.android.com/tools/releases/platform-tools
- Unzip so you have `C:\Users\Public\Tools\platform-tools\adb.exe` (beside ExifTool)
- Phone: Settings → About phone → tap Build number 7× → Developer options → USB debugging on
- Plug in, tap Allow on "Allow USB debugging?" (tick Always allow)
- See [[15 - Send to Phone]]

---

## Optional: ExifTool (Recommended)

Bundled with the v3.0 app builds. The notes below apply when running from source.

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