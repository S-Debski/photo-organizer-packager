# Role: Application module (see Stability Contract)

import sys
import os
import glob

print("PYTHON EXECUTABLE:", sys.executable)

root = os.path.dirname(sys.executable)

# Pywin32 can install postinstall script in several different locations
patterns = [
    os.path.join(root, "Scripts", "pywin32_postinstall.py"),
    os.path.join(root, "Lib", "site-packages", "pywin32_postinstall.py"),
    os.path.join(root, "Lib", "site-packages", "pywin32_system32", "pywin32_postinstall.py"),
    os.path.join(root, "Lib", "site-packages", "win32", "pywin32_postinstall.py"),
    os.path.join(root, "Lib", "site-packages", "win32", "*postinstall*.py"),
]

found_any = False

for pattern in patterns:
    for path in glob.glob(pattern):
        print("FOUND:", path)
        found_any = True

if not found_any:
    print("⚠ No pywin32 postinstall script found.")
