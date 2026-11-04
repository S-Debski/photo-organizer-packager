# Role: Application module (see Stability Contract)

# photo_core/export/pixel.py
# -----------------------------------------------------------------------------
# Copy an imported shoot onto an Android phone using Android's adb tool.
# The app only copies to the phone; it never uploads anywhere. (The author
# sends to a Pixel XL, whose own Google Photos backup takes it from there.)
#
# A phone over USB is an MTP device, not a drive, so ordinary file copies
# can't reach it; adb can. Photos go into ONE phone folder so a phone-side
# backup app (e.g. Google Photos) only has to be pointed at it once.
#
#   - Never overwrites on the phone: same name + same size → skipped
#     (already sent); same name, different photo → numbered name
#   - Reads the imported copies only; never touches the card
#   - After pushing, asks the phone's media scanner to index the files
#
# adb is Google's "Android SDK Platform-Tools" (free download). It is not
# bundled; it's found like ExifTool: PHOTO_ORGANIZER_ADB, PATH, or common
# install folders.
# -----------------------------------------------------------------------------
import os
import shlex
import shutil
import subprocess
import sys

PHONE_FOLDER = "/sdcard/DCIM/PhotoOrganizer"

JPG_EXTS = (".jpg", ".jpeg")
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def resolve_adb() -> str | None:
    explicit = os.environ.get("PHOTO_ORGANIZER_ADB")
    if explicit and os.path.isfile(explicit):
        return explicit

    found = shutil.which("adb")
    if found:
        return found

    home = os.path.expanduser("~")
    exe = "adb.exe" if os.name == "nt" else "adb"
    candidates = [
        os.path.join(r"C:\Users\Public\Tools\platform-tools", exe),
        os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk", "platform-tools", exe
        ),
        os.path.join(home, "Library", "Android", "sdk", "platform-tools", exe),
        "/opt/homebrew/bin/adb",
        "/usr/local/bin/adb",
    ]
    if sys.platform == "win32":
        candidates.append(r"C:\platform-tools\adb.exe")
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def _run(adb: str, *args, timeout=60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [adb, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        creationflags=NO_WINDOW,
        timeout=timeout,
    )


def list_devices(adb: str) -> list[dict]:
    """
    Connected phones: [{serial, state, model}]. state is "device" when
    ready, "unauthorized" until the phone's "Allow USB debugging" prompt
    is accepted, "offline" while it reconnects.
    """
    proc = _run(adb, "devices", "-l", timeout=15)
    devices = []
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2:
            continue
        info = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        devices.append(
            {
                "serial": parts[0],
                "state": parts[1],
                "model": info.get("model", "").replace("_", " ") or "Android phone",
            }
        )
    return devices


def pick_files(folder: str, include_raw: bool) -> list[str]:
    """Photos in the imported folder to send (JPG, plus RAW if asked)."""
    from utils.fs_utils import IMAGE_EXTS_RAW

    exts = JPG_EXTS + (tuple(IMAGE_EXTS_RAW) if include_raw else ())
    return sorted(
        os.path.join(folder, n)
        for n in os.listdir(folder)
        if n.lower().endswith(exts) and os.path.isfile(os.path.join(folder, n))
    )


def phone_files(adb: str, serial: str, folder: str = PHONE_FOLDER) -> dict[str, int]:
    """{name: size} of what's already in the phone folder."""
    _run(adb, "-s", serial, "shell", f"mkdir -p {shlex.quote(folder)}")
    proc = _run(
        adb,
        "-s",
        serial,
        "shell",
        f"stat -c '%n|%s' {shlex.quote(folder)}/* 2>/dev/null",
    )
    existing = {}
    for line in proc.stdout.splitlines():
        if "|" not in line:
            continue
        path, size = line.rsplit("|", 1)
        try:
            existing[path.rsplit("/", 1)[-1]] = int(size)
        except ValueError:
            continue
    return existing


def plan_names(
    files: list[str], existing: dict[str, int]
) -> list[tuple[str, str | None]]:
    """
    [(local path, phone name or None to skip)]. Never overwrites: a name
    already on the phone with the same size is the same photo (skip);
    with a different size it's another photo, so number the new one.
    """
    taken = dict(existing)
    plan = []
    for path in files:
        name = os.path.basename(path)
        size = os.path.getsize(path)
        if taken.get(name) == size:
            plan.append((path, None))
            continue
        if name in taken:
            stem, ext = os.path.splitext(name)
            n = 2
            while f"{stem}_{n}{ext}" in taken:
                n += 1
            name = f"{stem}_{n}{ext}"
        taken[name] = size
        plan.append((path, name))
    return plan


def send_folder(
    adb: str,
    serial: str,
    folder: str,
    include_raw: bool = False,
    progress=None,
    phone_folder: str = PHONE_FOLDER,
) -> dict:
    """
    Push a folder's photos to the phone. `progress(done, total, message)`
    is called after each file. Returns a summary dict.
    """
    files = pick_files(folder, include_raw)
    plan = plan_names(files, phone_files(adb, serial, phone_folder))
    to_send = [(p, n) for p, n in plan if n]
    sent, failed = [], []

    for i, (path, name) in enumerate(to_send, 1):
        remote = f"{phone_folder}/{name}"
        proc = _run(
            adb, "-s", serial, "push", os.path.abspath(path), remote, timeout=600
        )
        if proc.returncode == 0:
            sent.append(remote)
        else:
            failed.append(
                f"{os.path.basename(path)}: {(proc.stderr or proc.stdout).strip()[:200]}"
            )
        if progress:
            progress(i, len(to_send), f"Sending to phone {i}/{len(to_send)}…")

    # Let the gallery and Google Photos see the new files straight away
    for remote in sent:
        _run(
            adb,
            "-s",
            serial,
            "shell",
            "am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "
            + shlex.quote("file://" + remote),
            timeout=30,
        )

    return {
        "sent": len(sent),
        "skipped": len(plan) - len(to_send),
        "failed": failed,
        "phone_folder": phone_folder,
    }
