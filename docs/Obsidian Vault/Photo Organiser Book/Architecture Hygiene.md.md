Content:

```markdown
# Architecture Hygiene
#architecture #workflow

This note captures small practices that keep the codebase stable over time.

## Role Annotation

Tool: `tools/role_annotator.py`

Purpose:
- Make architectural intent explicit at the file boundary
- Prevent silent drift during refactors

### When to run

- Before committing new files
- Before refactors that move or rename files
- Before tagging a release

### Normal usage

Check only:
```bash
python tools/role_annotator.py --check
```

Apply when required
python tools/role_annotator.py --apply

- Runs in dry‑run mode by default
- Only scans stabilised directories
- Safe and idempotent

