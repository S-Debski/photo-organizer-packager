# Role: Test helper (see Stability Contract)
"""
Stand-in for Android's adb, for tests: pretends a Pixel XL is connected
and maps the phone's /sdcard to the folder in FAKE_PHONE_ROOT. Handles
only the commands photo_core/export/pixel.py uses.
"""
import os
import shlex
import shutil
import sys

ROOT = os.environ["FAKE_PHONE_ROOT"]


def local(remote: str) -> str:
    return os.path.join(ROOT, *remote.strip("/").split("/"))


args = sys.argv[1:]
if args[:1] == ["devices"]:
    print("List of devices attached")
    print("FA6AX0301234   device usb:1-1 product:marlin model:Pixel_XL device:marlin transport_id:2")
    sys.exit(0)

if args[:1] == ["-s"]:
    args = args[2:]

if args[0] == "push":
    src, dst = args[1], args[2]
    os.makedirs(os.path.dirname(local(dst)), exist_ok=True)
    shutil.copyfile(src, local(dst))
    print(f"{src}: 1 file pushed")
    sys.exit(0)

if args[0] == "shell":
    line = " ".join(args[1:])
    words = shlex.split(line.replace(" 2>/dev/null", ""))
    if words[:2] == ["mkdir", "-p"]:
        os.makedirs(local(words[2]), exist_ok=True)
    elif words[:2] == ["stat", "-c"]:
        folder = words[3][:-2]                      # strip "/*"
        if os.path.isdir(local(folder)):
            for name in sorted(os.listdir(local(folder))):
                print(f"{folder}/{name}|{os.path.getsize(os.path.join(local(folder), name))}")
    elif words[:2] == ["am", "broadcast"]:
        with open(os.path.join(ROOT, "scans.log"), "a", encoding="utf-8") as fh:
            fh.write(words[-1] + "\n")
    sys.exit(0)

print(f"fake adb: unsupported {args}", file=sys.stderr)
sys.exit(1)
