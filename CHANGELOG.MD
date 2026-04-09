# Changelog

## v2.7.1 – Stable Frontend/Backend Alignment
**Release date:** 2026‑04‑09

### ✅ Stability & Architecture
- Aligned Flask HTML serving with Git‑tracked templates (`templates/index.html`)
- Removed ambiguity between legacy UI paths and current frontend structure
- Single authoritative frontend entrypoint (`ui/static/js/main.js`)
- Eliminated inconsistent behaviour caused by ignored or duplicate files

### ✅ Frontend Improvements
- Fixed thumbnail preview modal so images correctly enlarge to screen size
- Restored reliable thumbnail click handling after refactor
- Lazy‑loaded thumbnails to prevent UI freezing
- Prevented Leaflet map from intercepting pointer events outside Mapping step
- Improved wizard step transitions and sidebar behaviour
- Auto‑analyse safely triggers only after SD selection is fully populated
- Clearer SD detection messaging with consistent timing display

### ✅ Backend Improvements
- Added analysis progress reporting endpoint
- Added safe analysis cancellation support
- Improved EXIF lens detection with multi‑field fallback
- Stabilised EXIF scanning without blocking UI threads
- Maintained compatibility with Windows development environment

### ✅ Bug Fixes
- Fixed preview modal regression introduced during frontend refactor
- Fixed inconsistent behaviour after hard refresh (Ctrl+Shift+R)
- Resolved map overlay blocking UI clicks
- Eliminated race conditions between SD detection and auto‑analyse

### 🧱 Known‑Good Baseline
This release represents a **known‑good, stable baseline** suitable for:
- Further feature development
- Branch‑based experimentation
- Packaging and distribution
- Reliable rollback point

Tag: `v2.7.1-stable`