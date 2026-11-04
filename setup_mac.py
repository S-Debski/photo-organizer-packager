# Role: Application module (see Stability Contract)

#!/usr/bin/env python3
"""
Setup script for building Mac .app bundle
Usage: python3 setup_mac.py py2app
"""

from setuptools import setup

APP = ["app.py"]
DATA_FILES = [
    ("templates", ["templates"]),
    ("static", ["static"]),
]

OPTIONS = {
    "argv_emulation": False,
    "packages": [
        "flask",
        "pathlib",
        "PIL",
        "piexif",
        "jinja2",
        "werkzeug",
        "click",
        "itsdangerous",
        "markupsafe",
    ],
    "includes": [
        "jinja2",
        "werkzeug",
        "flask",
    ],
    "excludes": [
        "matplotlib",
        "numpy",
        "pandas",
    ],
    "plist": {
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "CFBundleIdentifier": "com.photoorganizer.app",
        "NSPrincipalClass": "NSApplication",
    },
}

setup(
    name="Photo Organizer",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
    author="Photo Organizer",
    author_email="",
    url="",
    description="Smart photo import with automatic camera detection",
    long_description="Organize photos from SD cards with intelligent duplicate detection and camera identification.",
)
