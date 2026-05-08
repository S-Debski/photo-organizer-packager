# Role: Application module

#!/usr/bin/env python3
"""
Role Annotator

Annotates source files with a one-line architectural Role header.

Default mode: DRY-RUN (no changes)
Apply changes: --apply
CI verification: --check

Roles may optionally be sourced from the Stability Contract (Obsidian Markdown).

See: Stability Contract
"""

from pathlib import Path
import argparse
import sys

# =============================================================================
# Configuration (policy lives here)
# =============================================================================

# Explicit, authoritative roles (highest priority)
ROLE_MAP = {
    "main.py": "Application entry point",
    "app.py": "UI application wiring",
    "api_server.py": "Backend service / IPC boundary",
    "cli.py": "Command-line interface",
    "thread_manager.py": "Background job and thread coordination",
    "mutex.py": "Cross-process and critical-section locking",
    "config.py": "Central configuration",
}

# Generic fallback roles for discovered files
GENERIC_ROLES = {
    ".js": "JavaScript module",
    ".ts": "TypeScript module",
}

# File-type comment styles
COMMENT_STYLES = {
    ".py": "#",
    ".js": "//",
    ".ts": "//",
    ".sh": "#",
    ".ps1": "#",
    ".cmd": "REM",
    ".bat": "REM",
    ".md": "#",
    ".txt": "#",
}

# Subdirectories that are considered "stable" and eligible for scanning
STABLE_DIRS = {
    "src",
    "ui",
    "frontend",
    "backend",
}

# Directories that must never be scanned
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
}

# Optional Obsidian contract path
CONTRACT_DOC = Path("docs/Stability Contract.md")

HEADER_TEMPLATE = "{comment} Role: {role} (see Stability Contract)\n\n"


# =============================================================================
# Optional: load roles from Obsidian Markdown
# =============================================================================

def load_roles_from_markdown(path: Path) -> dict[str, str]:
    """
    Parse a fenced ```roles block from the Stability Contract.

    Format:
        ```roles
        main.py: Application entry point
        app.py: UI wiring
        ```
    """
    roles = {}
    if not path.exists():
        return roles

    in_block = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if stripped == "```roles":
            in_block = True
            continue

        if stripped == "```" and in_block:
            break

        if in_block and ":" in stripped:
            file, role = stripped.split(":", 1)
            roles[file.strip()] = role.strip()

    return roles


# =============================================================================
# Core helpers
# =============================================================================

def get_comment_prefix(path: Path) -> str | None:
    return COMMENT_STYLES.get(path.suffix.lower())


def already_annotated(text: str, comment: str) -> bool:
    return text.startswith(f"{comment} Role:")


def should_consider_path(path: Path) -> bool:
    if not path.is_file():
        return False

    if any(part in EXCLUDE_DIRS for part in path.parts):
        return False

    # Root-level files are always eligible
    if path.parent == Path("."):
        return True

    # Subdirectories must be explicitly stabilised
    return any(part in STABLE_DIRS for part in path.parts)


# =============================================================================
# File processing
# =============================================================================

def process_file(
    path: Path,
    role: str,
    *,
    apply: bool,
    check: bool,
    missing: list[Path],
):
    comment = get_comment_prefix(path)
    if not comment:
        return

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    # ✅ Already has header → skip
    if already_annotated(text, comment):
        return

    # ✅ If in check mode → record and exit
    if check:
        missing.append(path)
        return

    # ✅ Step 3: build header
    header = f"{comment} Role: {role}\n\n"

    # ✅ Apply or dry-run
    if apply:
        path.write_text(header + text, encoding="utf-8")
        print(f"ADD  Role header → {path}")
    else:
        print(f"[DRY-RUN] Would update {path}")

# =============================================================================
# Scanning logic
# =============================================================================
# File filtering
def should_consider_path(path: Path) -> bool:
    if not path.is_file():
        return False

    path_str = str(path)

    # ✅ Exclude unwanted directories
    if any(ex in path_str for ex in EXCLUDE_DIRS):
        return False

    # ✅ ONLY annotate real source code
    allowed_exts = {
        ".py",
        ".js",
        ".ts",
        ".ps1",
        ".bat",
        ".cmd",
        ".sh",
    }

    return path.suffix.lower() in allowed_exts


def scan_explicit_files(root: Path, *, apply: bool, check: bool, missing: list[Path]):
    for filename, role in ROLE_MAP.items():
        path = root / filename
        if path.exists():
            process_file(path, role, apply=apply, check=check, missing=missing)


def scan_stable_directories(root: Path, *, apply: bool, check: bool, missing: list[Path]):
    for path in root.rglob("*"):   # ✅ FIXED

        if not should_consider_path(path):
            continue

        # ✅ Determine role
        role = ROLE_MAP.get(path.name)

        if not role:
            role = GENERIC_ROLES.get(path.suffix, "Application module")

        # ✅ Step 4: call process_file()
        process_file(
            path,
            role,
            apply=apply,
            check=check,
            missing=missing,
        )

# =============================================================================
# CLI entry point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Annotate files with Role headers")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--check", action="store_true", help="Fail if headers are missing")
    parser.add_argument(
        "--sync-doc",
        action="store_true",
        help="Load ROLE_MAP overrides from Stability Contract",
    )
    args = parser.parse_args()

    if args.sync_doc:
        ROLE_MAP.update(load_roles_from_markdown(CONTRACT_DOC))

    root = Path(".")
    missing: list[Path] = []

    mode = (
        "CHECK"
        if args.check
        else "APPLY"
        if args.apply
        else "DRY-RUN"
    )

    print("Role annotation")
    print("Mode:", mode)
    print("-" * 40)

    scan_explicit_files(root, apply=args.apply, check=args.check, missing=missing)
    scan_stable_directories(root, apply=args.apply, check=args.check, missing=missing)

    if args.check and missing:
        print("\nMissing Role headers:")
        for p in missing:
            print(f" - {p}")
        sys.exit(1)

    print("-" * 40)
    print("Done.")


if __name__ == "__main__":
    main()