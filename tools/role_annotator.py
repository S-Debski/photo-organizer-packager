# Role: Development tooling (role annotation system) (see Stability Contract)
#!/usr/bin/env python3
"""
Role Annotator

Annotates source files with a one-line architectural Role header.

Modes:
- DRY-RUN (default)
- --apply → add missing headers
- --fix → fix incorrect headers
- --check → fail if headers incorrect/missing
- --report → audit display

"""

from pathlib import Path
import argparse
import sys

# =============================================================================
# Configuration
# =============================================================================

ROLE_MAP = {
    "main.py": "Application entry point",
    "app.py": "UI application wiring",
    "api_server.py": "Backend service / IPC boundary",
    "cli.py": "Command-line interface",
    "thread_manager.py": "Background job and thread coordination",
    "mutex.py": "Cross-process and critical-section locking",
    "config.py": "Central configuration",
    "main.js": "Frontend application entry point",
    "gps_data.py": "GPS data API route",
    "exif_stats.py": "EXIF statistics API route",
    "reader.py": "EXIF extraction interface",
    "lens.py": "Lens metadata resolver",
    "analyze_card.py": "SD card analysis engine",
    "role_annotator.py": "Development tooling (role annotation system)",
}

GENERIC_ROLES = {
    ".js": "JavaScript module",
    ".ts": "TypeScript module",
}

COMMENT_STYLES = {
    ".py": "#",
    ".js": "//",
    ".ts": "//",
    ".sh": "#",
    ".ps1": "#",
    ".cmd": "REM",
    ".bat": "REM",
}

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".eggs",
}

CONTRACT_DOC = Path("docs/Stability Contract.md")

# =============================================================================
# Helpers
# =============================================================================


def get_comment_prefix(path: Path) -> str | None:
    return COMMENT_STYLES.get(path.suffix.lower())


def should_consider_path(path: Path) -> bool:
    if not path.is_file():
        return False

    path_str = str(path)

    if any(ex in path_str for ex in EXCLUDE_DIRS):
        return False

    allowed_exts = {".py", ".js", ".ts", ".ps1", ".bat", ".cmd", ".sh"}

    return path.suffix.lower() in allowed_exts


# =============================================================================
# Core processing
# =============================================================================


def process_file(
    path: Path,
    role: str,
    *,
    apply: bool,
    check: bool,
    fix: bool,
    report: bool,
    missing: list[Path],
):
    comment = get_comment_prefix(path)
    if not comment:
        return

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    lines = text.splitlines()
    expected_header = f"{comment} Role: {role} (see Stability Contract)"

    # Find first non-empty line
    first_line_idx = None
    for i, line in enumerate(lines):
        if line.strip():
            first_line_idx = i
            break

    has_header = False
    current_header = None

    if first_line_idx is not None:
        if lines[first_line_idx].strip().startswith(f"{comment} Role:"):
            has_header = True
            current_header = lines[first_line_idx]

    # ✅ REPORT mode
    if report:
        print(f"\nFILE: {path}")

        if first_line_idx is not None:
            print("  CURRENT :", lines[first_line_idx])
        else:
            print("  CURRENT : <no header found>")

        print("  EXPECTED:", expected_header)

        if (
            has_header
            and current_header
            and current_header.strip() == expected_header.strip()
        ):
            print("  STATUS  : ✅ OK")
        else:
            print("  STATUS  : ❌ MISMATCH")

        return

    # ✅ CHECK mode
    # Any well-formed one-line Role header passes; ROLE_MAP / GENERIC_ROLES
    # are only the defaults --apply writes (names like gps_data.py exist in
    # more than one package, so the map can't be the authority).
    if check:
        header = (current_header or "").strip()
        if not (
            has_header
            and header.endswith("(see Stability Contract)")
            and len(header) > len(f"{comment} Role: (see Stability Contract)")
        ):
            missing.append(path)
        return

    # ✅ FIX mode
    if fix and has_header and first_line_idx is not None:
        if current_header.strip() != expected_header.strip():
            print(f"FIX  Role header → {path}")
            lines[first_line_idx] = expected_header
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    # ✅ ADD mode
    if not has_header:
        print(f"ADD  Role header → {path}")
        header = expected_header + "\n\n"
        if apply:
            path.write_text(header + text, encoding="utf-8")

    # ✅ DRY-RUN display
    elif not apply and not fix:
        print(f"[OK] {path}")


# =============================================================================
# Scanning
# =============================================================================


def scan_explicit_files(
    root: Path,
    *,
    apply: bool,
    check: bool,
    fix: bool,
    report: bool,
    missing: list[Path],
):
    for filename, role in ROLE_MAP.items():
        path = root / filename
        if path.exists():
            process_file(
                path,
                role,
                apply=apply,
                check=check,
                fix=fix,
                report=report,
                missing=missing,
            )


def scan_stable_directories(
    root: Path,
    *,
    apply: bool,
    check: bool,
    fix: bool,
    report: bool,
    missing: list[Path],
):
    for path in root.rglob("*"):
        if not should_consider_path(path):
            continue

        role = ROLE_MAP.get(path.name)

        if not role:
            role = GENERIC_ROLES.get(path.suffix, "Application module")

        process_file(
            path,
            role,
            apply=apply,
            check=check,
            fix=fix,
            report=report,
            missing=missing,
        )


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Annotate files with Role headers")

    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--report", action="store_true")

    args = parser.parse_args()

    root = Path(".")
    missing: list[Path] = []

    mode = (
        "REPORT"
        if args.report
        else (
            "CHECK"
            if args.check
            else (
                "FIX+APPLY"
                if args.fix and args.apply
                else "FIX" if args.fix else "APPLY" if args.apply else "DRY-RUN"
            )
        )
    )

    print("Role annotation")
    print("Mode:", mode)
    print("-" * 40)

    scan_explicit_files(
        root,
        apply=args.apply,
        check=args.check,
        fix=args.fix,
        report=args.report,
        missing=missing,
    )

    scan_stable_directories(
        root,
        apply=args.apply,
        check=args.check,
        fix=args.fix,
        report=args.report,
        missing=missing,
    )

    if args.check and missing:
        print("\nMissing or incorrect Role headers:")
        for p in missing:
            print(" -", p)
        sys.exit(1)

    print("-" * 40)
    print("Done.")


if __name__ == "__main__":
    main()
