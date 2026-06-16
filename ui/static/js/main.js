// Role: Frontend application entry point (see Stability Contract)

// ============================================================================
// File: static/js/main.js
//
// Role:
//   Frontend controller for Photo Organizer UI
//
// Responsibilities:
//   - Handle user interactions (analyze, folder select, map)
//   - Call backend APIs
//   - Render folders, thumbnails, and map markers
//
// Notes:
//   - Works with Flask backend endpoints (/api/*)
// ============================================================================
// Role: Frontend application entry point (see Stability Contract)
// ====================================================================
// Photo Organizer main.js – v2.8.0
//
// Main UI controller for the Wizard workflow.
//
// Handles:
//   - Step 1: SD card detection
//   - Step 2: Analyze → session defaults
//   - Step 3: Camera + Lens statistics (read‑only)
//   - Step 4: Thumbnails
//   - Step 5: Mapping
//   - Step 6: Pre‑Import & Organize
//   - Step 7: Logs
//
// NOTE:
// UI logic is bound lazily as steps become active.
// ====================================================================
// Globals here //
import { pairFiles } from './lib/pairing.js';
let currentImages = [];
let pairedImages = [];
let pairingMap = new Map();
let analyzedFolders = [];
let analyzeInProgress = false;
let thumbnails = [];
let currentPreviewIndex = 0;
let organizePreview = null;
let imageCounts = { total: 0, raw: 0, jpg: 0 };
let markerLayer = null;
let selectedFolderGroup = null;
let folderGPS = {};
let folderGroups = {};
let selectedFolder = null;       // "USB" / "Medburn"
let sourceFolderPath = null;   // full path → F:\DCIM\929_FUJI
let workingDirectory = null;
let cameraChart = null;
let lensChart = null;
let combinedGPS = [];
let lastDisplayedGPS = null;
let gpsMode = "logical"; // default
let mapLoading = false;
let groupMode = "all";   // ✅ default: show all files
let currentGroup = null;


// ✅ Top Functions

function normalizePath(path) {
    if (!path) return "";
    return path.replaceAll("\\", "/").toLowerCase();
}

function getBase(path) {
    if (!path) return "";
    return path.split(/[\\/]/).pop().toLowerCase();
}

const $ = id => document.getElementById(id);

// ====================================================================
// UTILITIES (shared across all steps)
// ====================================================================
let inferOrganizationTitle = null;

(async () => {
    const mod = await import("/static/js/lib/inferOrganizationTitle.js");
    inferOrganizationTitle = mod.inferOrganizationTitle;
})();

// ====================================================================
// Debug helper - shows progress status
// ====================================================================
function updateProgress(msg) {
    showGlobalStatus(msg);
}
// =============================================================================
// UI Handler: Organize Button (Start Import)
//
// Role:
//   Trigger import of files from selected SD card to working directory.
//
// Responsibilities:
//   - Reads selected SD card path from dropdown
//   - Reads working directory input
//   - Sends organize request to backend (/api/organize)
//   - Displays success or error feedback to user
//
// Input:
//   - sdSelect (source path)
//   - workingDirectoryInput (destination path)
//
// Output:
//   - Alert showing number of imported files OR error message
//
// Notes:
//   - Requires valid source and destination
//   - Backend handles actual copying + safety checks
// =============================================================================
$("organizeBtn")?.addEventListener("click", async () => {

    const source = $("sdSelect")?.value;
    const destinationInput = $("workingDirectoryInput")?.value;
    const destination = destinationInput && destinationInput.trim() ? destinationInput.trim() : "";

    if (!source) { alert("Please select a card first."); return; }
    if (!destination) { alert("Please select a working directory."); return; }
    if (!analyzedFolders || analyzedFolders.length === 0) {
        alert("Please analyse the card first.");
        return;
    }

    setImportState("running");

    try {
        const res = await fetch("/api/organize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ source, destination })
        });

        const data = await res.json();

        if (data.success) {
            setImportState("done", {
                count: data.count,
                destination: data.destination
            });
        } else {
            setImportState("error", { message: data.error });
        }
    } catch (err) {
        setImportState("error", { message: err.message });
    }
});

// ------------------------------------------------------------
// Import UI state machine
// States: idle | running | done | error
// ------------------------------------------------------------
// ------------------------------------------------------------
// Import timing state
// ------------------------------------------------------------
let _importStartTime   = null;   // Date.now() when copy began
let _importTimerHandle = null;   // setInterval handle for elapsed ticker
let _importLastDone    = 0;      // last known done count (for rate calc)
let _importLastTime    = null;   // timestamp of last progress sample

// ------------------------------------------------------------
// Timing helpers
// ------------------------------------------------------------
function _formatDuration(seconds) {
    seconds = Math.round(seconds);
    if (seconds < 60)  return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function _startElapsedTicker() {
    _importStartTime = Date.now();
    _importLastTime  = _importStartTime;
    _importLastDone  = 0;

    clearInterval(_importTimerHandle);
    _importTimerHandle = setInterval(() => {
        const elapsed = (Date.now() - _importStartTime) / 1000;
        const el = $("importElapsed");
        if (el) el.textContent = _formatDuration(elapsed);
    }, 1000);
}

function _stopElapsedTicker() {
    clearInterval(_importTimerHandle);
    _importTimerHandle = null;
}

function _updateTimingDisplay(done, total) {
    const now     = Date.now();
    const elapsed = (now - _importStartTime) / 1000;          // seconds
    const delta_t = (now - _importLastTime)  / 1000;          // since last sample
    const delta_n = done - _importLastDone;                    // files since last sample

    // Update sample baseline
    _importLastTime = now;
    _importLastDone = done;

    // Rate: use recent window, fall back to overall average
    const rate = delta_t > 0.5 && delta_n > 0
        ? delta_n / delta_t
        : elapsed > 0 ? done / elapsed : 0;

    const rateEl = $("importRate");
    if (rateEl) {
        rateEl.textContent = rate > 0
            ? `${rate.toFixed(1)} files/sec`
            : "—";
    }

    // ETA
    const etaEl = $("importEta");
    if (etaEl) {
        const remaining = total - done;
        if (rate > 0 && remaining > 0) {
            etaEl.textContent = `~${_formatDuration(remaining / rate)} remaining`;
        } else if (remaining === 0) {
            etaEl.textContent = "almost done…";
        } else {
            etaEl.textContent = "—";
        }
    }
}

// ------------------------------------------------------------
// Progress poller — calls /api/progress while import runs
// ------------------------------------------------------------
let _importPollHandle = null;

function _startProgressPoll() {
    clearInterval(_importPollHandle);
    _importPollHandle = setInterval(async () => {
        try {
            const res = await fetch("/api/progress");
            if (!res.ok) return;
            const job = await res.json();

            const done  = job.done  || 0;
            const total = job.total || 0;
            const pct   = total > 0 ? Math.round((done / total) * 100) : 0;

            const bar      = $("importProgressBar");
            const pctEl    = $("importProgressPct");
            const labelEl  = $("importProgressLabel");

            if (bar) {
                bar.style.width = `${pct}%`;
                // Switch from indeterminate to real progress once we have data
                if (total > 0) {
                    bar.classList.remove("progress-bar-animated", "progress-bar-striped");
                }
            }
            if (pctEl)   pctEl.textContent   = total > 0 ? `${pct}%` : "";
            if (labelEl) labelEl.textContent  =
                total > 0 ? `${done} / ${total} files` : "Copying files…";

            if (total > 0) _updateTimingDisplay(done, total);

            // Stop polling once backend goes idle
            if (!job.active) _stopProgressPoll();

        } catch (_) { /* network blip — keep polling */ }
    }, 500);
}

function _stopProgressPoll() {
    clearInterval(_importPollHandle);
    _importPollHandle = null;
}

// ------------------------------------------------------------
// Import UI state machine
// States: idle | running | done | error
// ------------------------------------------------------------
function setImportState(state, payload = {}) {
    const btn      = $("organizeBtn");
    const spinner  = $("organizeSpinner");
    const btnIcon  = $("organizeBtnIcon");
    const btnText  = $("organizeBtnText");
    const progress = $("importProgressContainer");
    const label    = $("importProgressLabel");
    const pct      = $("importProgressPct");
    const bar      = $("importProgressBar");
    const result   = $("importResult");
    const openBtn  = $("openPicturesBtn");
    const summary  = $("importSummary");

    result?.classList.add("d-none");
    openBtn?.classList.add("d-none");

    if (state === "running") {
        btn.disabled = true;
        spinner?.classList.remove("d-none");
        btnIcon?.classList.add("d-none");
        if (btnText) btnText.textContent = "Importing…";
        progress?.classList.remove("d-none");
        if (label) label.textContent = "Copying files…";
        if (pct)   pct.textContent   = "";
        if (bar) {
            bar.style.width = "100%";
            bar.classList.add("progress-bar-animated", "progress-bar-striped");
        }
        // Reset timing display
        if ($("importElapsed")) $("importElapsed").textContent = "0s";
        if ($("importRate"))    $("importRate").textContent    = "—";
        if ($("importEta"))     $("importEta").textContent     = "—";

        summary?.classList.add("d-none");
        _startElapsedTicker();
        _startProgressPoll();
    }

    else if (state === "done") {
        _stopElapsedTicker();
        _stopProgressPoll();

        const totalElapsed = _importStartTime
            ? _formatDuration((Date.now() - _importStartTime) / 1000)
            : null;

        btn.disabled = false;
        spinner?.classList.add("d-none");
        btnIcon?.classList.remove("d-none");
        if (btnIcon) btnIcon.className = "bi bi-check-circle-fill text-success me-1";
        if (btnText) btnText.textContent = "Import again";
        progress?.classList.add("d-none");
        if (bar) bar.style.width = "0%";

        if (result) {
            result.className = "mt-3 alert alert-success";
            result.innerHTML =
                `<i class="bi bi-check-circle-fill me-2"></i>` +
                `<strong>${payload.count} file${payload.count !== 1 ? "s" : ""} imported</strong>` +
                (totalElapsed ? ` <span class="text-muted fw-normal">in ${totalElapsed}</span>` : "") +
                (payload.destination
                    ? `<div class="small mt-1 text-muted">${payload.destination}</div>`
                    : "");
            result.classList.remove("d-none");
        }
        openBtn?.classList.remove("d-none");
    }

    else if (state === "error") {
        _stopElapsedTicker();
        _stopProgressPoll();

        btn.disabled = false;
        spinner?.classList.add("d-none");
        btnIcon?.classList.remove("d-none");
        if (btnIcon) btnIcon.className = "bi bi-play-fill";
        if (btnText) btnText.textContent = "Start Import";
        progress?.classList.add("d-none");

        if (result) {
            result.className = "mt-3 alert alert-danger";
            result.innerHTML =
                `<i class="bi bi-exclamation-triangle-fill me-2"></i>` +
                `Import failed: ${payload.message || "Unknown error"}`;
            result.classList.remove("d-none");
        }
    }

    else { // idle
        _stopElapsedTicker();
        _stopProgressPoll();
        btn.disabled = false;
        spinner?.classList.add("d-none");
        btnIcon?.classList.remove("d-none");
        if (btnIcon) btnIcon.className = "bi bi-play-fill";
        if (btnText) btnText.textContent = "Start Import";
        progress?.classList.add("d-none");
    }
}


window.setGPSMode = function(mode) {
    gpsMode = mode;
    console.log("GPS mode set to:", mode);
    loadMap();
};

window.setGroupMode = function(mode) {
    groupMode = mode;

    document.getElementById("btnGrouped")?.classList.toggle("active", mode === "grouped");
    document.getElementById("btnAll")?.classList.toggle("active", mode === "all");

    console.log("Group mode set to:", mode);
    loadMap();
};


// ====================================================================
// GPS Status helper - shows via badge - needed or done
// ====================================================================
function updateHeaderStatus() {
    const badge = document.getElementById("gpsStatusBadge");

    if (!badge || !selectedFolder) return;

    if (folderGPS[selectedFolder]) {
        badge.textContent = "📍 GPS set";
        badge.classList.remove("text-muted");
        badge.classList.add("text-success");
    } else {
        badge.textContent = "⚪ No location data (optional — add in Mapping if needed)";
        badge.classList.remove("text-success");
        badge.classList.add("text-muted");
    }
}

// ====================================================================
// GPS Set lat and lon variables throughout
// ====================================================================
function getFolderGPS(folderName) {
    const rawGPS = folderGPS[folderName];

    const gps = rawGPS ? {
        lat: rawGPS.lat,
        lon: rawGPS.lon ?? rawGPS.lng
    } : null;

    if (!gps) return null;

    return {
        lat: gps.lat,
        lon: gps.lon ?? gps.lng   // fallback for older entries
    };
}

// ====================================================================
// Folder Indicator helper -
// ====================================================================
function updateFolderIndicators() {
    // just re-render selector
    if (currentImages) {
        renderFolderSelector(currentImages);
    }
}
// ====================================================================
// Pairing helper - keeps jpg and Raw of same photo together
// ====================================================================
function pairImages(files) {
    const map = {};

    files.forEach(path => {
        const name = path.split(/[/\\]/).pop();
        const base = name.split(".")[0];
        const ext = name.split(".").pop().toLowerCase();

        if (!map[base]) {
            map[base] = {
                base: base,
                jpg: null,
                raw: null
            };
        }

        if (ext === "jpg" || ext === "jpeg") {
            map[base].jpg = path;
        } else {
            map[base].raw = path;
        }
    });

    return Object.values(map);
}

// ====================================================================
// Extract Folder Name helper - if user created them - used for gps org
// ====================================================================
function getFolderName(path) {
    if (!path) return "Unknown";

    const workingRootInput = document.getElementById("workingDirectoryInput");
    const workingRoot = workingRootInput?.value?.trim();

    const normalised = path.replace(/\//g, "\\");

    // ✅ If working root is known — use it
    if (workingRoot && normalised.startsWith(workingRoot)) {
        let relative = normalised.slice(workingRoot.length);
        relative = relative.replace(/^\\+/, "");

        const parts = relative.split("\\");

        return parts.length > 0 ? parts[0] : "Root";
    }

    // ✅ fallback: assume folder structure ends with group
    const parts = normalised.split("\\");

    if (parts.length >= 2) {
        return parts[parts.length - 2];
    }

    return "Unknown";
}

function setSDButtonState(state) {
    const btn = $('refreshSdBtn');
    const hint = $('sdHint');

    if (!btn) return;

    if (state === 'initial') {
        btn.innerHTML = '<i class="bi bi-sd-card"></i> Detect cards';
        if (hint) hint.textContent = 'Card ready. Click "Analyze Card" or refresh.';
    } else if (state === 'loaded') {
        btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh card list';
        if (hint) hint.textContent = 'Cards detected. Click to rescan.';
    }
}

function log(msg) {
    const area = $("log");
    if (!area) return;
    area.textContent += msg + "\n";
    area.scrollTop = area.scrollHeight;
}

function showAnalyzeStatus(msg) {
    const el = document.getElementById("analyzeStatus");
    if (!el) return;
    el.textContent = msg;
    el.classList.remove("d-none");
}

function clearAnalyzeStatus() {
    const el = document.getElementById("analyzeStatus");
    if (!el) return;
    el.classList.add("d-none");
    el.textContent = "";
}

function switchStep(step) {

    // IMPORTANT: coerce step to number
    step = Number(step);
// ✅ Clear status when changing step (clean UI)
    clearGlobalStatus();

// ✅ hide / show GPS legend depending on step
    const gpsBadge = document.getElementById("gpsStatusBadge");

    if (gpsBadge) {
        if (step === 1) {
            gpsBadge.style.display = "none";   // ✅ hide on Select Card
        } else {
            gpsBadge.style.display = "block";  // ✅ show elsewhere
        }
    }

    // Require folder selection before proceeding
    if ((step === 3 || step === 4 || step === 5 || step === 6) && !selectedFolder) {
        showGlobalStatus("ℹ️ Select a folder before continuing.");
        return;
    }

    // Hide all steps
    document.querySelectorAll(".wizard-step")
        .forEach(s => s.classList.add("d-none"));

    // Show requested step
    const target = document.querySelector(`.wizard-step[data-step="${step}"]`);
    if (target) target.classList.remove("d-none");

    // Sidebar highlighting
    document.querySelectorAll("#wizardNav .sidebar-item")
        .forEach(item => {
            item.classList.toggle(
                "active",
                Number(item.getAttribute("data-step")) === step
            );
        });

    // Step-specific behaviour
    switch (step) {
        case 3:
            // ✅ Thumbnails first (visual feedback)
            loadThumbnails();
            showGlobalStatus(`
⏳ <strong>Loading thumbnails…</strong><br>
<small>Click “Thumbnails” in the menu to view when ready</small>
`);
            break;

        case 4:
            // ✅ Protect against early access
            if (!pairedImages || pairedImages.length === 0) {
                showGlobalStatus("⏳ Load thumbnails first to generate stats");
                return;
            }

            // ✅ Build + render stats
            gatherPairedStats();
            renderCameraStats();
            renderLensStats();
            renderCharts();
            break;


        case 5:
            initMap();
            loadMap();
            break;

        case 6:
            if (!selectedFolder) {
                showGlobalStatus("ℹ️ Select a folder before organizing.");
                return;
            }

            bindOrganizeEvents();
            clearGlobalStatus();
            break;
// NOTE: Step 6 must not derive or modify title state.
// Title defaults are established after Analyze and may be user-owned.

    }   // ✅ closes switch(step)
}       // ✅ closes function switchStep

function showGlobalStatus(msg) {
    const el = document.getElementById("globalStatus");
    if (!el) return;

    el.innerHTML = msg;
    el.classList.remove("d-none");

    // ✅ Ensure it is visible even if contentArea is scrolled
    // ❌ Disable auto-scroll (prevents UI jumping)
// el.scrollIntoView({ behavior: "smooth", block: "start" });
}

function clearGlobalStatus() {
    const el = document.getElementById("globalStatus");
    if (!el) return;
    el.classList.add("d-none");
    el.innerHTML = "";
}

$("browseworkingDirectoryBtn")?.addEventListener("click", async () => {

    try {
        const res = await fetch("/api/select-folder");
        const data = await res.json();

        if (data?.path) {
            $("workingDirectoryInput").value = data.path;
        } else {
            alert("Folder picker not available.");
        }

    } catch (err) {
        console.error("Folder selection failed:", err);
    }

});

$('refreshSdBtn')?.addEventListener('click', () => {
    const spinner = $("sdSpinner");
    const text = $("sdBtnText");
    const btn = $("refreshSdBtn");

    // ✅ Start loading state
    if (spinner) spinner.classList.remove("d-none");
    if (text) text.style.opacity = "0.6";
    if (btn) btn.disabled = true;

    showGlobalStatus(`
    ⏳ <strong>Detecting cards…</strong><br>
    <span>Reading available drives</span>
`);

    fetchSDCards();
});


// ====================================================================
// STEP 1 – Select Card (SD Card Detection)
// ====================================================================
async function fetchSDCards() {
    const sel = $('sdSelect');

    // ✅ Set scanning state
    if (sel) {
        sel.innerHTML = `<option>Scanning for cards...</option>`;
        sel.disabled = true;
    }

    let secs = 0;
    const startTime = Date.now();
    const MIN_VISIBLE_MS = 600;

    const showVirtual = document.querySelector('#showVirtualDrives')?.checked;

    // ✅ Global status
    showGlobalStatus(`
        ⏳ <strong>Detecting cards…</strong><br>
        Reading available drives
    `);

    // ✅ Live timer
    const timer = setInterval(() => {
        secs++;
        $("sdTimer").textContent = `(${secs}s)`;
        $("sdStatusText").textContent = "⏳ Detecting cards...";
    }, 1000);

    try {
        // ✅ Build URL safely (prevents malformed requests)
        const url = new URL("/api/sd-cards", window.location.origin);
        url.searchParams.set("includeVirtual", showVirtual);

        console.log("Fetching:", url.toString()); // ✅ debug

        const res = await fetch(url);
        const data = await res.json();

        clearInterval(timer);

        const duration = ((Date.now() - startTime) / 1000).toFixed(1);

        if (!data.success) {
            $("sdStatusText").textContent = "⚠️ Error detecting cards.";
            $("sdTimer").textContent = "";
            clearGlobalStatus();
            return;
        }

        const visibleDrives = data.drives || [];

        if (visibleDrives.length === 0) {
            $("sdStatusText").textContent = showVirtual
                ? "⚠️ No drives detected."
                : "⚠️ No camera cards detected. Insert a card or enable additional drives.";

            $("sdTimer").textContent = "";
            setSDButtonState('initial');
            clearGlobalStatus();
            return;
        }

        // ✅ Populate dropdown
        sel.innerHTML = '';

        visibleDrives.forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.path;
            opt.textContent = `${d.path} — ${d.label || ''}`;
            sel.appendChild(opt);
        });

        // ✅ Auto-select first detected card
        if (sel.options.length > 0) {
            sel.selectedIndex = 0;
        }

        // ✅ Enable Analyze button
        const analyzeBtn = $("analyzeBtn");
        if (analyzeBtn) analyzeBtn.disabled = false;

        setSDButtonState('loaded');

        const elapsed = Date.now() - startTime;

        // ✅ Final message
        setTimeout(() => {

            $("sdStatusText").innerHTML =
                `✅ ${visibleDrives.length} ${visibleDrives.length === 1 ? "card" : "cards"} detected in ${duration}s`;

            $("sdTimer").textContent = "";

            showGlobalStatus("✅ Cards detected");
            setTimeout(clearGlobalStatus, 1200);

        }, Math.max(0, MIN_VISIBLE_MS - elapsed));

    } catch (err) {
        clearInterval(timer);

        $("sdStatusText").textContent = "⚠️ Failed to detect cards.";
        $("sdTimer").textContent = "";

        log("SD detection error: " + err);
        clearGlobalStatus();

    } finally {
        // ✅ Reset UI state
        const spinner = $("sdSpinner");
        const text = $("sdBtnText");
        const btn = $("refreshSdBtn");

        if (spinner) spinner.classList.add("d-none");
        if (text) text.style.opacity = "1";
        if (btn) btn.disabled = false;

        if (sel) sel.disabled = false;
    }
}
// ====================================================================
// STEP 2 – Analyze SD Card
// Derives:
//   - folder analysis
//   - default session metadata (title / shoot_date)
// Remain in Analyze (Step 2) to allow folder selection
// ====================================================================
function updateGlobalStatus(data) {
    let statusText = "";

    // ✅ NEW: EXIF drives readiness (NOT copy)
    if (data.exif_count < data.file_count) {
        statusText = `
🧠 <strong>Processing metadata</strong><br>
<small>${data.exif_count} of ${data.file_count} photos analysed</small>
`;
    }
    else {
        statusText = `
✅ <strong>Analysis complete</strong><br>
<small>
Photos are ready for viewing and organisation<br>
⚠️ Some photos may not have GPS data — locations can be assigned in Mapping
</small>
`;
    }

    showGlobalStatus(statusText);
}
//====================================================================
// Group Images by folder
// ====================================================================
function groupByFolder(images) {
    const groups = {};

    images.forEach(img => {
        const folderName = getFolderName(img.path || img);

        if (!groups[folderName]) {
            groups[folderName] = [];
        }

        groups[folderName].push(img);
    });

    return groups;
}

function renderFolderSelector(images) {
    const container = document.getElementById("folderSelector");

    if (!container) {
        console.warn("⚠️ folderSelector container not found");
        return;
    }

    if (!images || images.length === 0) {
        console.warn("⚠️ No images to group");
        return;
    }

    // ✅ build groups from working images
    folderGroups = groupByFolder(images);

    console.log("✅ Folder groups:", Object.keys(folderGroups));

    // ✅ clear existing UI
    container.innerHTML = "";

    Object.keys(folderGroups).forEach(folder => {

        const btn = document.createElement("button");
        btn.className = "btn btn-sm btn-outline-secondary m-1";

        const rawGPS = folderGPS[folder];
        const hasGPS = rawGPS && (rawGPS.lon != null || rawGPS.lng != null);

        btn.innerHTML = `
    📁 ${folder} (${folderGroups[folder].length})
    <span class="ms-2 small ${hasGPS ? 'text-success' : 'text-secondary'}">
        ${hasGPS ? '📍 Location assigned' : '⚪ No location data (optional — add in Mapping if needed)'}
    </span>
`;

        btn.onclick = () => {

            selectedFolder = folder;
            currentGroup = folder;   // 🔥 force map to use this folder’s GPS
            manualLocation = null;   // ✅ CLEAR override
            const folderNameEl = document.getElementById("currentFolderName");
            if (folderNameEl) {
                folderNameEl.textContent = folder;
            }

            updateHeaderStatus();

            const group = folderGroups[folder];
            selectedFolderGroup = group;

            if (!group || group.length === 0) {
                sourceFolderPath = null;
                return;
            }

            const firstImage = group[0];

            if (firstImage && firstImage.path) {
                sourceFolderPath = firstImage.path
                    .split(/[\\/]/)
                    .slice(0, -1)
                    .join("\\");
            } else {
                sourceFolderPath = null;
            }

            container.querySelectorAll("button")
                .forEach(b => b.classList.remove("active"));

            btn.classList.add("active");

            const gpsRaw = folderGPS[selectedFolder];

            const gps = gpsRaw ? {
                lat: gpsRaw.lat,
                lon: gpsRaw.lon ?? gpsRaw.lng
            } : null;

            if (gps && gps.lat != null && gps.lon != null) {
                manualLocation = { lat: gps.lat, lon: gps.lon };

                const latInput = document.getElementById("latInput");
                const lonInput = document.getElementById("lonInput");

                if (latInput && lonInput) {
                    latInput.value = gps.lat.toFixed(6);
                    lonInput.value = gps.lon.toFixed(6);
                }
            }


            // ✅ Only run when Mapping step is NOT active
            const mappingActive =
                document.querySelector('[data-step="5"]')
                    ?.classList.contains('d-none') === false;
            loadMap();

            if (!mappingActive) {
                loadThumbnails();
                switchStep(3);
            }
        };

        container.appendChild(btn);

    });
}
// ✅ auto-select first folder
if (!selectedFolder && Object.keys(folderGroups).length > 0) {
    const firstBtn = container.querySelector("button");
    if (firstBtn) firstBtn.click();
}
function renderAnalyzeFolders() {

    const container = document.getElementById("foldersList");
    if (!container) {
        console.error("❌ analyzeFolders container not found");
        return;
    }

    container.innerHTML = "";

    if (!analyzedFolders || analyzedFolders.length === 0) {
        console.warn("⚠️ No analyzed folders to render");
        container.innerHTML = "<p>No folders found</p>";
        return;
    }

    analyzedFolders.forEach(folder => {

        const item = document.createElement("div");
        item.classList.add("mb-2", "folder-item");

        const sample = folder.sample || "";

        item.innerHTML = `
<div class="card bg-dark border-secondary folder-card p-3 d-flex flex-row align-items-center">

    <!-- Thumbnail -->
    <div style="width:70px; height:70px; margin-right:12px; flex-shrink:0;">
        ${
            sample
                ? `<img src="/api/photo-proxy?path=${encodeURIComponent(sample)}"
                        style="width:100%; height:100%; object-fit:cover; border-radius:6px; display:block;">`
                : `<div style="width:100%; height:100%; background:#333; border-radius:6px;"></div>`
        }
    </div>

    <!-- Content -->
    <div class="flex-grow-1 d-flex flex-column justify-content-center">

        <div class="d-flex justify-content-between align-items-center">

            <div class="fw-semibold">
                📁 ${folder.name || "Unnamed Folder"}
            </div>

            <span class="badge bg-primary">
                ${folder.photo_count || 0}
            </span>

        </div>

        <div class="small text-secondary mt-1">
            RAW: ${folder.raw_count || 0} • JPG: ${folder.jpeg_count || 0}
            &nbsp;•&nbsp;
            ${folder.camera_model || ""}
        </div>

    </div>

</div>
`;

        // ✅ CLICK HANDLER
        if (!item) {
            console.error("❌ item is undefined!");
            return;
        }

        item.onclick = async () => {
            const folderPath = folder.path;

            if (!folderPath) {
                console.error("❌ folder.path missing!", folder);
                return;
            }

            // ✅ SOURCE (correct)
            sourceFolderPath = folderPath;
            selectedFolder = folder.name;

            // ✅ Reset grouping when switching folder
            currentGroup = null;

            console.log("SOURCE:", sourceFolderPath);
            console.log("WORKING:", workingDirectory);

// ✅ Reset map state
            gpsRetryCount = 0;
            const status = document.getElementById("mapStatus");
            if (status) status.innerHTML = "";

            // ✅ API call
            try {
                const res = await fetch("/api/set-active-folder", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        folder: sourceFolderPath,
                        working_dir: workingDirectory
                    })
                });

                const data = await res.json();
                workingDirectory = data.working_dir;

                console.log("WORKING:", workingDirectory);
                if (!data.success) {
                    console.error("❌ Set active folder failed:", data);
                    return;
                }

                // ✅ Highlight selection
                document.querySelectorAll(".folder-item")
                    .forEach(el => el.classList.remove("selected"));

                item.classList.add("selected");

                // ✅ UI update
                document.querySelectorAll('#wizardNav .sidebar-item')
                    .forEach(el => el.classList.remove('recommended'));

                const nextStep = document.querySelector('[data-step="5"]');
                nextStep?.classList.add('recommended');

                const wdEl = document.getElementById("workingDirectoryDisplay");
                if (wdEl) {
                    wdEl.textContent = data.working_dir;
                }

                showGlobalStatus("✅ Folder ready.");
                setTimeout(() => showGlobalStatus(""), 2000);

            } catch (err) {
                console.error("❌ Error setting active folder:", err);
            }
        };
        // ✅ MUST be inside loop
        container.appendChild(item);

    }); // ✅ CLOSE forEach

} // ✅ CLOSE function

// =============================================================================
// Data Builder: metadataMap (Post-Thumbnail Load)
//
// Role:
//   Build a lookup map for all images currently loaded into the UI,
//   providing a central store for metadata used throughout the app.
//
// Responsibilities:
//   - Initialize metadata entries for each image path
//   - Store camera, lens, and GPS data (updated later)
//   - Provide data for mapping, stats, and thumbnails
//
// Input:
//   - currentImages[] (populated after thumbnail load)
//
// Output:
//   - metadataMap (Map)
//       key   = file path
//       value = {
//           camera_model,
//           lens,
//           lat,
//           lon
//       }
//
// Notes:
//   - Must run AFTER thumbnails are loaded
//   - GPS values start as null and are updated via mapping
//   - Used by:
//       • mapping (GPS markers)
//       • manual GPS assignment
//       • stats and UI display
// =============================================================================

let metadataMap = new Map();

// ====================================================================
// STEP 3 – Camera + Lens Stats (READ‑ONLY)
// Summary derived from analyzed folders.
// Counts are approximate and folder‑based.
// ====================================================================

let cameraStats = {};
let lensStats = {};

function gatherStats() {
    cameraStats = {};
    lensStats = {};
    console.log("Analyzed folders:", analyzedFolders);
    if (!analyzedFolders || analyzedFolders.length === 0) {
        showGlobalStatus("⚠️ No folders analysed.");
        return;
    }
    const statsSummary = document.getElementById("statsSummary");

    if (statsSummary) {
        const totalPhotos = analyzedFolders.reduce(
            (sum, f) => sum + (f.photo_count || 0),
            0
        );

        statsSummary.innerHTML = `
        <div class="mb-2 text-muted">
     // Old version      Total photos: <strong>${totalPhotos}</strong> across ${analyzedFolders.length} folders
     Total images: ${pairedImages.length}

        </div>
    `;
    } else {
        console.warn("⚠️ statsSummary element not found");
    }


    analyzedFolders.forEach(folder => {
        const cam = folder.camera_model || "Unknown";
        const lens = folder.lens || "Unknown Lens";

        const folderName = folder.path.split(/[\\/]/).pop();
        const count = folder.photo_count || 0;

        // ✅ CAMERA
        if (!cameraStats[cam]) {
            cameraStats[cam] = {
                total: 0,
                folders: {}
            };
        }

        cameraStats[cam].total += count;
        cameraStats[cam].folders[folderName] = count;

        // ✅ LENS
        if (!lensStats[lens]) {
            lensStats[lens] = {
                total: 0,
                folders: {}
            };
        }

        lensStats[lens].total += count;
        lensStats[lens].folders[folderName] = count;
    });

    console.log("📊 Aggregated camera stats:", cameraStats);
    console.log("📊 Aggregated lens stats:", lensStats);
}
// Pair Raw and Jpg photos where the same
function gatherPairedStats() {
    cameraStats = {};
    lensStats = {};

    if (!pairedImages || pairedImages.length === 0) {
        console.warn("⚠️ No paired images available");
        return;
    }

    pairedImages.forEach(img => {

        // ✅ choose representative file (prefer JPG)
        const file = img.jpg || img.raw;

        if (!file) return;

        // ✅ Extract folder path from file
        const folderPath = file.split(/[\\/]/).slice(0, -1).join("\\");

        // ✅ Find matching analyzed folder
        const normalise = p => p.replace(/\\/g, "/").toLowerCase();

        const normalFile = normalise(file);

        const folderMeta = analyzedFolders.find(f =>
            normalFile.startsWith(normalise(f.path))
        );



        const camera = folderMeta?.camera_model || "Unknown";
        const lens   = folderMeta?.lens || "Unknown Lens";

        // ✅ Folder name (for display) — ONLY ONCE
        const folderName = file.split(/[\\/]/).slice(-2, -1)[0] || "Unknown";

        // ✅ CAMERA
        if (!cameraStats[camera]) {
            cameraStats[camera] = {
                total: 0,
                folders: {},
                paired: 0,
                jpgOnly: 0,
                rawOnly: 0
            };
        }


        cameraStats[camera].total++;

        // ✅ pairing breakdown
        if (img.jpg && img.raw) cameraStats[camera].paired++;
        else if (img.jpg) cameraStats[camera].jpgOnly++;
        else if (img.raw) cameraStats[camera].rawOnly++;

        const camFolder = cameraStats[camera].folders;
        camFolder[folderName] = (camFolder[folderName] || 0) + 1;

        // ✅ LENS
        if (!lensStats[lens]) {
            lensStats[lens] = {
                total: 0,
                folders: {},
                paired: 0,
                jpgOnly: 0,
                rawOnly: 0
            };
        }

        lensStats[lens].total++;

        if (img.jpg && img.raw) lensStats[lens].paired++;
        else if (img.jpg) lensStats[lens].jpgOnly++;
        else if (img.raw) lensStats[lens].rawOnly++;

        const lensFolder = lensStats[lens].folders;
        lensFolder[folderName] = (lensFolder[folderName] || 0) + 1;
    });
}


function renderCameraStats() {

    const grandTotal = Object.values(cameraStats)
        .reduce((sum, c) => sum + c.total, 0);

    $('cameraStats').innerHTML =
        Object.entries(cameraStats)
            .sort((a, b) => b[1].total - a[1].total)
            .map(([cam, data]) => {

                const pctTotal = grandTotal
                    ? ((data.total / grandTotal) * 100).toFixed(1)
                    : "0.0";

                const folderBreakdown = Object.entries(data.folders)
                    .map(([folder, count]) => {
                        const pct = data.total
                            ? ((count / data.total) * 100).toFixed(1)
                            : "0.0";

                        return `
                            <div class="small text-muted ms-3">
                                ${folder}: ${count} images (${pct}%)
                            </div>
                        `;
                    })
                    .join("");

                return `
                <div class="list-group-item bg-dark-subtle text-light">

                    <strong>${cam}</strong>
                    <span class="text-secondary">
                        — ${data.total} images (${pctTotal}%)
                    </span>

                    <div class="small mt-1">
                        ✅ ${data.paired} paired —
                        🖼️ ${data.jpgOnly} JPG —
                        📷 ${data.rawOnly} RAW
                    </div>

                    ${folderBreakdown}

                </div>
                `;
            })
            .join('');
}

function renderLensStats() {

    const grandTotal = Object.values(lensStats)
        .reduce((sum, l) => sum + l.total, 0);

    $('lensStats').innerHTML =
        Object.entries(lensStats)
            .sort((a, b) => b[1].total - a[1].total)
            .map(([lens, data]) => {

                const pctTotal = grandTotal
                    ? ((data.total / grandTotal) * 100).toFixed(1)
                    : "0.0";

                const folderBreakdown = Object.entries(data.folders)
                    .map(([folder, count]) => {
                        const pct = data.total
                            ? ((count / data.total) * 100).toFixed(1)
                            : "0.0";

                        return `
                            <div class="small text-muted ms-3">
                                ${folder}: ${count} images (${pct}%)
                            </div>
                        `;
                    })
                    .join("");

                return `
                <div class="list-group-item bg-dark-subtle text-light">

                    <strong>${lens}</strong>
                    <span class="text-secondary">
                        — ${data.total} images (${pctTotal}%)
                    </span>

                    <!-- ✅ ADD THIS BLOCK -->
                    <div class="small mt-1">
                        ✅ ${data.paired} paired —
                        🖼️ ${data.jpgOnly} JPG —
                        📷 ${data.rawOnly} RAW
                    </div>

                    ${folderBreakdown}

                </div>`;
            })
            .join('');
}

function renderCharts() {
    console.log("Camera stats for chart:", cameraStats);

    // Guard: canvas elements must exist before Chart.js can render
    if (!$('chartCameras') || !$('chartLenses')) {
        console.warn("renderCharts: canvas not in DOM yet, skipping");
        return;
    }

    const usePercent = document.getElementById("togglePercent")?.checked;

    if (cameraChart) cameraChart.destroy();
    if (lensChart) lensChart.destroy();

    const useStacked = document.getElementById("toggleStacked")?.checked;

    const cameraLabels = Object.keys(cameraStats);
    const lensLabels = Object.keys(lensStats);

    // ✅ SIMPLE MODE
    if (!useStacked) {

        cameraChart = new Chart($('chartCameras'), {
            type: "bar",
            data: {
                labels: cameraLabels,
                datasets: [{
                    label: "Photos per Camera",
                    data: Object.values(cameraStats).map(c => c.total),
                    backgroundColor: "#4dc9f6"
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    x: { stacked: false },
                    y: { stacked: false }
                }
            }
        });

        lensChart = new Chart($('chartLenses'), {
            type: "bar",
            data: {
                labels: lensLabels,
                datasets: [{
                    label: "Photos per Lens",
                    data: Object.values(lensStats).map(l => l.total),
                    backgroundColor: "#f67019"
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    x: { stacked: false },
                    y: { stacked: false }
                }
            }
        });

        return;
    }

    // ✅ ✅ STACKED MODE

    const folders = [...new Set(
        analyzedFolders.map(f => f.path.split(/[\\/]/).pop())
    )];

    const colors = [
        "#4dc9f6", "#f67019", "#f53794",
        "#537bc4", "#acc236", "#166a8f"
    ];

    const cameraDatasets = folders.map((folderName, i) => ({
        label: folderName,
        backgroundColor: colors[i % colors.length],
        borderColor: "#111",
        borderWidth: 1,
        data: cameraLabels.map(cam => {
            const value = cameraStats[cam].folders[folderName] || 0;

            if (!usePercent) return value;

            const total = cameraStats[cam].total || 1;
            return (value / total) * 100;
        })
    }));

    cameraChart = new Chart($('chartCameras'), {
        type: "bar",
        data: {
            labels: cameraLabels,
            datasets: cameraDatasets
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                x: { stacked: true },
                y: {
                    stacked: true,
                    max: usePercent ? 100 : undefined,
                    ticks: {
                        callback: value => usePercent ? value + "%" : value
                    }
                }
            }
        }
    });

    // ✅ LENS STACKED

    const lensDatasets = folders.map((folderName, i) => ({
        label: folderName,
        backgroundColor: colors[i % colors.length],
        borderColor: "#111",
        borderWidth: 1,
        data: lensLabels.map(l => {
            const value = lensStats[l].folders[folderName] || 0;

            if (!usePercent) return value;

            const total = lensStats[l].total || 1;
            return (value / total) * 100;
        })

    }));

    lensChart = new Chart($('chartLenses'), {
        type: "bar",
        data: {
            labels: lensLabels,
            datasets: lensDatasets
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                x: { stacked: true },
                y: {
                    stacked: true,
                    max: usePercent ? 100 : undefined,
                    ticks: {
                        callback: value => usePercent ? value + "%" : value
                    }
                }

            }
        }
    });
}

//=====================================================================
// Chart toggle
//=====================================================================
const chartsContainer = $('chartsContainer');
const toggleChartsBtn = $('toggleChartsBtn');

toggleChartsBtn?.addEventListener('click', () => {
    const showing = !chartsContainer.classList.contains('d-none');

    if (showing) {
        chartsContainer.classList.add('d-none');
        toggleChartsBtn.textContent = "Show charts";
    } else {
        chartsContainer.classList.remove('d-none');
        toggleChartsBtn.textContent = "Hide charts";

        // Charts render only if explicitly shown
        if (!chartsContainer.classList.contains('d-none')) {
            renderCharts();
        }

    }
});

// Re-render charts when stacked toggle changes
document.getElementById("toggleStacked")
    ?.addEventListener("change", () => {
        // Only re-render if charts are visible (important!)
        if (!chartsContainer.classList.contains('d-none')) {
            renderCharts();
        }
    });


// ====================================================================
// STEP 4 — THUMBNAILS
// ====================================================================
function getFilename(img) {
    return (img.path || img).split("\\").pop().split("/").pop();
}

function updateProgressBar(processed, total) {

    const container = document.getElementById("progressContainer");
    const bar = document.getElementById("progressBar");
    const text = document.getElementById("progressText");

    if (!container || !bar) return;

    container.style.display = "block";

    const pct = total ? Math.floor((processed / total) * 100) : 0;

    bar.style.width = pct + "%";

    if (text) {
        text.textContent = `${processed} / ${total} images (${pct}%)`;
    }
}

function openFullImage(path) {

    const modal = document.getElementById("imageModal");

    // ✅ Set current index
    currentPreviewIndex = thumbnails.indexOf(path);

    updatePreviewImage();

    modal.classList.remove("d-none");
}
async function loadThumbnails() {

    if (!sourceFolderPath) {
        console.warn("❌ No folder selected — aborting thumbnail load");
        return;
    }

    try {
        const res = await fetch("/api/thumbs", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                folder: sourceFolderPath
            })
        });

        const data = await res.json();

        // ✅ ✅ REMOVE infinite retry loop — handle empty safely
        if (!data || data.length === 0) {
            console.warn("⚠️ No thumbnails returned");

            $("thumbnailGallery").innerHTML = `
                <div class="text-muted text-center py-4">
                    ⚠️ No images found in this folder<br>
                    <small>Check folder selection or contents</small>
                </div>
            `;

            return;   // ✅ STOP — no retry
        }

        // ✅ SUCCESS: render thumbnails
        thumbnails = Array.isArray(data) ? data : (data.thumbnails || []);
        currentImages = thumbnails;
        // ✅ Build metadataMap AFTER images are loaded
        metadataMap = new Map();

        (currentImages || []).forEach(path => {
            metadataMap.set(path, {
                camera_model: "Unknown",
                lens: "Unknown Lens",
                lat: null,
                lon: null
            });
        });

        console.log("✅ metadataMap built:", metadataMap.size);


        // ✅ Pair JPG + RAW files into logical images
        pairedImages = pairFiles(thumbnails);

        // ✅ Render grouped images
        $("thumbnailGallery").innerHTML = "";
        renderThumbnailsChunked(pairedImages, 0, 6);
        showGlobalStatus(`
✅ <strong>Thumbnails ready</strong><br>
<small>
Viewing: <b>${selectedFolder}</b><br>
Select another folder or go back to Analyse to choose a different card
</small>
`);

        // ✅ Logs
        console.log("✅ Thumbnails loaded:", thumbnails.length);
        console.log("✅ currentImages length:", currentImages?.length);
        console.log("✅ pairedImages length:", pairedImages?.length);

        // ✅ Prepare folder grouping
        prepareFolderGrouping(currentImages);

        // ✅ Pre-warm stats
        gatherPairedStats();

    } catch (err) {
        console.error("Thumbnail load failed:", err);

        $("thumbnailGallery").innerHTML = `
            <div class="text-danger text-center py-4">
                ❌ Failed to load thumbnails<br>
                <small>Check connection or try again</small>
            </div>
        `;
    }
}
function prepareFolderGrouping(images) {
    if (!images || images.length === 0) return;

    console.log("📂 Preparing folder groups for mapping...");

    // ✅ ALWAYS use working directory images
    folderGroups = groupByFolder(images);


    console.log("✅ Folder groups:", Object.keys(folderGroups));
}
function showNextImage() {
    currentPreviewIndex = (currentPreviewIndex + 1) % thumbnails.length;
    updatePreviewImage();
}

function showPreviousImage() {
    currentPreviewIndex =
        (currentPreviewIndex - 1 + thumbnails.length) % thumbnails.length;
    updatePreviewImage();
}

function renderThumbnailsChunked(items, start = 0, chunkSize = 6) {
    const grid = $("thumbnailGallery");
    const end = Math.min(start + chunkSize, items.length);

    for (let i = start; i < end; i++) {
        const item = items[i];   // ✅ now using pairedImages

        // ✅ Wrapper
        const div = document.createElement("div");
        div.className = "thumbnail-item col-3 position-relative";
        div.style.textAlign = "center";

        // ✅ Choose preview image
        let previewPath = item.jpg || item.raw;

        // ✅ Image
        const img = document.createElement("img");
        img.src = `/api/photo-proxy?path=${encodeURIComponent(previewPath)}`;
        img.className = "img-fluid";
        img.loading = "lazy";
        img.decoding = "async";

        // ✅ Click handler
        const openPath = previewPath;
        const open = () => openFullImage(openPath);

        div.onclick = open;
        img.onclick = open;

        // ✅ Filename label (use base name)
        const label = document.createElement("div");
        label.textContent = item.baseName;
        label.className = "thumb-label";
        label.title = item.baseName;

        // ✅ Badge logic
        let badge = "";
        if (item.jpg && item.raw) {
            badge = "✅";
        } else if (item.jpg) {
            badge = "🖼️";
        } else if (item.raw) {
            badge = "📷";
        }

        if (badge) {
            const badgeEl = document.createElement("div");
            badgeEl.className = "pair-badge";
            badgeEl.innerHTML = badge;
            div.appendChild(badgeEl);
        }

        // ✅ Assemble
        div.appendChild(img);
        div.appendChild(label);
        grid.appendChild(div);
    }

    // ✅ Continue chunking
    if (end < items.length) {
        setTimeout(() => {
            renderThumbnailsChunked(items, end, chunkSize);
        });
    } else {
        // ✅ ✅ ONLY once when ALL thumbnails finished

        const hasMissingGPS = !folderGPS[selectedFolder];

        if (hasMissingGPS) {
            showGlobalStatus(`
⚠️ <strong>No GPS data for ${selectedFolder}</strong><br>
<small>You can add a location in the Mapping step</small>
`);
        } else {
            showGlobalStatus(`
✅ <strong>Viewing: ${selectedFolder}</strong><br>
<small>Location assigned</small>
`);
        }
    }
}
function updatePreviewImage() {
    const img = $("previewImage");

    if (!img) {
        console.warn("previewImage element missing");
        return;
    }

    img.src = `/api/full-image?path=${encodeURIComponent(
        thumbnails[currentPreviewIndex]
    )}`;

    img.style.maxWidth = "100%";
    img.style.maxHeight = "85vh";
    img.style.width = "auto";
    img.style.height = "auto";
}

Object.keys(folderGroups).forEach(folder => {

    const btn = document.createElement("button");

    btn.className = "btn btn-sm btn-outline-secondary me-2";
    btn.textContent = folder;

    btn.onclick = () => {

        selectedFolder = folder;

        const group = folderGroups[folder];
        selectedFolderGroup = group;

        if (!group || group.length === 0) {
            sourceFolderPath = null;
            return;
        }

        const firstImage = group[0];

        if (firstImage && firstImage.path) {
            sourceFolderPath = firstImage.path
                .split(/[\\/]/)
                .slice(0, -1)
                .join("\\");
        } else {
            sourceFolderPath = null;
        }

        container.querySelectorAll("button")
            .forEach(b => b.classList.remove("active"));

        btn.classList.add("active");

        // ✅ map sync block goes here...

    };

    // ✅ ✅ THIS IS REQUIRED
    container.appendChild(btn);
});


function triggerMappingAfterSelection() {
    console.log("⏳ Waiting for EXIF worker before mapping...");

    setTimeout(() => {
        console.log("🗺️ Switching to Mapping step");
        switchStep(5);
    }, 1500);
}

let map = null;
let manualLocation = null;   // ✅ MOVE HERE

function initMap() {
    const el = document.getElementById("map");
    if (!el) {
        console.warn("Map container not found");
        return;
    }

    el.style.height = "400px";
    el.style.width = "100%";
    el.style.display = "block";

    if (map) return;

    map = L.map(el);

    markerLayer = L.layerGroup().addTo(map);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
        maxZoom: 18
    }).addTo(map);

    map.setView([51.5, -0.12], 5);

    map.on("click", function (e) {

        // ✅ Extract from Leaflet
        const lat = e.latlng.lat;
        const lon = e.latlng.lng;

        // ✅ Store variable
        manualLocation = { lat, lon };

        console.log("📍 Selected manual location:", manualLocation);
        console.log("✅ Manual GPS applied to images");

        // ✅ Clear previous marker
        if (markerLayer) {
            markerLayer.clearLayers();
        }

        // ✅ Add marker
        L.marker([lat, lon])
            .addTo(markerLayer)
            .bindPopup("Manual location")
            .openPopup();

        // ✅ Move map (MUST be inside)
        if (map) {
            map.setView([lat, lon], 14);
        }

        // ✅ Show panel
        const panel = document.getElementById("locationDetails");
        if (panel) panel.style.display = "block";

        // ✅ Update inputs
        const latInput = document.getElementById("latInput");
        const lonInput = document.getElementById("lonInput");

        if (latInput && lonInput) {
            latInput.value = lat.toFixed(6);
            lonInput.value = lon.toFixed(6);
        }

        showManualLocation(lat, lon);
    });
}

let gpsRetryCount = 0;
// ✅ Sync manual input → map + state
document.getElementById("latInput")?.addEventListener("change", updateFromInputs);
document.getElementById("lonInput")?.addEventListener("change", updateFromInputs);

async function loadMap() {

    if (mapLoading) return;
    mapLoading = true;
    const status = document.getElementById("mapStatus");

    if (status && gpsRetryCount === 0) {
        status.innerHTML = `
        <div class="map-status loading">
            ⏳ <strong>Loading GPS data…</strong><br>
            Reading metadata from images.
        </div>
    `;
    }
    try {
        // ✅ Build manual GPS list
        const manualGPS = [];

        metadataMap.forEach((value, path) => {
            if (value.lat != null && value.lon != null) {
                manualGPS.push({
                    path,
                    lat: value.lat,
                    lon: value.lon
                });
            }
        });

        console.log("manualGPS:", manualGPS);

        // ✅ Fetch
        const res = await fetch("/api/gps-data", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ manualGPS })
        });

        const gpsData = await res.json();

        const points = gpsData.points || [];
        combinedGPS = points.map(p => {
            const key = normalizePath(p.path);   // ✅ normalize path here
            const override = metadataMap.get(key);  // ✅ lookup here
            if (override && override.lat != null && override.lon != null) {
                console.log("✅ Applying override for:", key);
                return {
                    ...p,
                    lat: override.lat,
                    lon: override.lon
                };
            }
            return p;
        });

        console.log("RAW points:", points.length);

        console.log("Combined after merge:", combinedGPS);

        // ✅ Empty case (clean + correct UX)
        if (!combinedGPS.length) {

            // ✅ EXIF still processing
            if (!gpsData.exif_ready) {

                if (status) {
                    status.innerHTML = `
                <div class="map-status loading">
                    ⏳ <strong>Extracting GPS data…</strong><br>
                    Please wait while images are processed.
                </div>
            `;
                }

                gpsRetryCount++;   // ✅ prevents reset spam

                mapLoading = false;
                setTimeout(loadMap, 2000);
                return;
            }

            // ✅ EXIF done but no GPS found
            if (status) {
                status.innerHTML = `
            <div class="map-status warning">
                ⚠️ <strong>No GPS data found</strong>
            </div>
        `;
            }

            mapLoading = false;
            return;
        }
        // ✅ ✅ ✅ SUCCESS STATE (THIS IS MISSING)
        if (status && combinedGPS.length > 0) {
            status.innerHTML = `
        <div class="map-status success">
            📍 <strong>Showing ${combinedGPS.length} photo locations</strong>
        </div>
    `;
        }

// ✅ reset retry counter
        gpsRetryCount = 0;

        // ✅ ✅ ✅ RENDER ONLY FROM combinedGPS
        renderMapMarkers(combinedGPS);
        renderFolderSelector(combinedGPS);

        // ✅ Fit map
        if (map && combinedGPS.length > 0) {
            const bounds = L.latLngBounds(
                combinedGPS.map(p => [p.lat, p.lon])
            );

            map.fitBounds(bounds, { padding: [20, 20], maxZoom: 15 });
        }

        mapLoading = false;

    } catch (err) {

        console.error("❌ loadMap failed:", err);

        if (status) {
            status.innerHTML = `
                <div class="map-status warning">
                    ⚠️ Failed to load map data
                </div>
            `;
        }

        mapLoading = false;
    }
}

function showManualLocation(lat, lon) {
    console.log("currentImages length:", currentImages?.length);
    console.log("selectedFolderGroup:", selectedFolderGroup);

    const status = document.getElementById("mapStatus");

    if (!status) return;

    status.innerHTML = `
    <div class="map-status info">
        📍 <strong>Selected location</strong><br>
        ${lat.toFixed(5)}, ${lon.toFixed(5)}<br>

        <button id="applyGpsBtn"
                class="btn btn-sm btn-primary mt-2">
            Apply to images
        </button>
    </div>
`;
    document.getElementById("applyGpsBtn").onclick = applyManualGPS;
}

function updateFromInputs() {
    const latInput = document.getElementById("latInput");
    const lonInput = document.getElementById("lonInput");

    if (!latInput || !lonInput) return;

    const lat = parseFloat(latInput.value);
    const lon = parseFloat(lonInput.value);

    if (isNaN(lat) || isNaN(lon)) return;

    manualLocation = { lat, lon };

    console.log("📍 Updated from inputs:", manualLocation);

    // ✅ Move map
    if (map) {
        map.setView([lat, lon], 14);
    }

    // ✅ Update marker
    if (markerLayer) {
        markerLayer.clearLayers();
        L.marker([lat, lon]).addTo(markerLayer)
            .bindPopup("Manual location")
            .openPopup();
    }
}

async function applyManualGPS() {

    if (folderGPS[selectedFolder]) {
        const ok = confirm("⚠️ This folder already has GPS.\nOverwrite?");
        if (!ok) return;
    }

    updateFromInputs();

    if (!manualLocation) return;

    const lat = manualLocation.lat;
    const lon = manualLocation.lon;
    // ✅ start progress UI immediately
    const container = document.getElementById("writeProgressContainer");
    const bar = document.getElementById("writeProgressBar");
    const text = document.getElementById("writeProgressText");

    if (container) container.style.display = "block";
    if (bar) bar.style.width = "5%";
    if (text) text.textContent = "Starting...";

    // ✅ Save folder-level GPS (UI state)
    if (selectedFolder) {
        folderGPS[selectedFolder] = { lat, lon };
        console.log("📍 Saved GPS for folder:", selectedFolder, folderGPS[selectedFolder]);
    }

    if (!analyzedFolders || analyzedFolders.length === 0) {
        console.warn("❌ No folder selected — refusing to apply GPS globally");
        alert("Please select a folder before applying GPS");
        return;
    }

    console.log("🔍 APPLY CLICK");
    console.log("Selected folder:", selectedFolder);

    let targetImages;

    // ✅ Prefer grouped folder
    const group = folderGroups[selectedFolder];

    if (group && group.length > 0) {
        targetImages = group;
        console.log("✅ Using folder group");
    } else {
        console.warn("⚠️ No group found — using all images");
        targetImages = currentImages || [];
    }

    console.log("✅ Applying GPS to:", targetImages.length, "images");

    // ✅ Debug
    targetImages.forEach(img => {
        console.log("MATCH:", (img && img.path) ? img.path : img);
    });

    // ✅ Clear markers before redraw
    if (markerLayer) markerLayer.clearLayers();

    // ✅ Apply GPS to metadataMap (ONLY place this happens)
    targetImages.forEach(img => {

        const pathKey = (img && img.path) ? img.path : img;

        let matched = false;

        // ✅ Direct match
        if (metadataMap.has(pathKey)) {

            const existing = metadataMap.get(pathKey) || {};

            metadataMap.set(pathKey, {
                ...existing,
                lat: lat,
                lon: lon
            });

            console.log("✅ UPDATED (direct):", pathKey);
            matched = true;
        }

        // ✅ Fallback match by filename
        if (!matched && pathKey) {
            const fileName = pathKey.split(/[\\/]/).pop();

            metadataMap.forEach((val, key) => {

                if (key.endsWith(fileName)) {

                    const existing = metadataMap.get(key) || {};

                    metadataMap.set(key, {
                        ...existing,
                        lat: lat,
                        lon: lon
                    });

                    console.log("✅ UPDATED (fallback):", key);
                    matched = true;
                }
            });
        }

        if (!matched) {
            console.warn("❌ NO MATCH:", pathKey);
        }

    });

    // ✅ Refresh map
    console.log("✅ metadataMap updated for all images");
    setTimeout(() => loadMap(), 100);

    // ============================
    // EXIF WRITE LOGIC (unchanged)
    // ============================

    const flatFiles = (targetImages || [])
        .map(img => (img && img.path) ? img.path : img)
        .filter(Boolean);

    const groups = pairImages(flatFiles);

    const files = [];

    groups.forEach(g => {
        if (g.jpg) files.push(g.jpg);
        if (g.raw) files.push(g.raw);
    });

    console.log("📤 File count:", files.length);

    function pollWriteProgress() {

        fetch("/api/write-progress")
            .then(res => res.json())
            .then(data => {

                const container = document.getElementById("writeProgressContainer");
                const bar = document.getElementById("writeProgressBar");
                const text = document.getElementById("writeProgressText");

                // ✅ show progress container
                if (container) container.style.display = "block";

                const pct = data.total
                    ? Math.floor((data.done / data.total) * 100)
                    : 0;

                // ✅ update progress bar
                if (bar) bar.style.width = pct + "%";

                // ✅ update text
                if (text) {
                    text.textContent = `${data.done} / ${data.total} (${pct}%)`;
                }

                // ✅ finished
                if (!data.active) {

                    if (bar) bar.style.width = "100%";
                    if (text) text.textContent = "Complete";

                    setTimeout(() => {
                        if (container) container.style.display = "none";
                    }, 800);

                    showGlobalStatus("✅ GPS writing complete");
                    return;
                }

                // ✅ continue polling
                setTimeout(pollWriteProgress, 300);
            });
    }
    showGlobalStatus("⏳ Writing GPS to images...");
    pollWriteProgress();

    const btn = document.getElementById("applyGpsBtn");
    if (btn) btn.disabled = true;

    try {
        const res = await fetch("/api/write-gps", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                files: files,
                lat: lat,
                lon: lon
            })
        });

        const data = await res.json();

        const status = document.getElementById("mapStatus");

        if (data.success) {
            if (selectedFolder) {
                folderGPS[selectedFolder] = { lat, lon };
                updateFolderIndicators();
                updateHeaderStatus();
            }

            status.innerHTML = `
                <div class="map-status success">
                    ✅ <strong>GPS written to EXIF</strong><br>
                    ${data.updated} updated, ${data.skipped.length} RAW skipped
                </div>
            `;
        } else {
            status.innerHTML = `
                <div class="map-status warning">
                    ⚠️ <strong>EXIF write failed</strong>
                </div>
            `;
        }

        if (btn) btn.disabled = false;

    } catch (err) {
        console.error("❌ EXIF write failed:", err);
    }

    console.log("✅ metadataMap updated with manual GPS");

    loadMap();
}

function showExifCommand(lat, lon) {
    const status = document.getElementById("mapStatus");

    const cmd = `exiftool -GPSLatitude=${lat} -GPSLongitude=${lon} "*.JPG"`;

    status.innerHTML += `
        <div class="map-status mt-2">
            🛠 <strong>EXIFTool command:</strong><br>
            <code>${cmd}</code>
        </div>
    `;
}

function renderMapMarkers(points, start = 0, chunkSize = 25) {
    if (!map) return;

    // ✅ ✅ Clear ONLY on first chunk
    if (start === 0) {
        if (window.folderMarkerGroups) {
            Object.values(window.folderMarkerGroups).forEach(group => {
                group.clearLayers();
                map.removeLayer(group);
            });
        }
        window.folderMarkerGroups = {};
    }

    const end = Math.min(start + chunkSize, points.length);

    // ✅ Ensure container exists
    if (!window.folderMarkerGroups) {
        window.folderMarkerGroups = {};
    }

    for (let i = start; i < end; i++) {
        const p = points[i];

        // ✅ Use PATH for grouping (critical)
        const folderName = getFolderName(p.path || p.filename || "Root");

        // ✅ Create group if needed
        if (!window.folderMarkerGroups[folderName]) {
            window.folderMarkerGroups[folderName] = L.layerGroup().addTo(map);
            console.log("Creating marker group for:", folderName);
        }

        // ✅ Create marker
        const marker = L.marker([p.lat, p.lon])
            .bindPopup(`<b>${folderName}</b><br>${p.filename || "Photo"}`);

        // ✅ Add to correct group
        window.folderMarkerGroups[folderName].addLayer(marker);
    }

    // ✅ Continue chunk rendering
    if (end < points.length) {
        requestAnimationFrame(() =>
            renderMapMarkers(points, end, chunkSize)
        );

    } else {

        // ✅ ✅ FINAL ZOOM BEHAVIOUR (hybrid)
        if (points.length > 0 && map) {

            const bounds = L.latLngBounds(points.map(p => [p.lat, p.lon]));

            if (points.length < 10) {
                // ✅ small set → zoom tightly
                map.fitBounds(bounds, {
                    padding: [20, 20],
                    maxZoom: 14
                });

            } else {
                // ✅ large set → stable overview (no USB dominance)
                const center = bounds.getCenter();
                map.setView(center, 11);
            }
        }
    }
}
// ====================================================================
// STEP 6 – Pre‑Import & Organize
// ====================================================================
function updateSessionMeta() {
    fetch("/api/pre-import/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            title: $('session-title').value,
            shoot_date: $('session-date').value
        })
    });
}

$('organizeBtn')?.addEventListener('click', async () => {
    // unchanged
});
// ====================================================================
// ORGANIZE
// ====================================================================
function bindOrganizeEvents() {
    const btnOrg = $("organizeBtn");
    if (btnOrg && !btnOrg.dataset.bound) {
        btnOrg.onclick = async () => {
            const res = await fetch("/api/organize", { method: "POST" });
            if (res.ok) pollJobStatus();
        };
        btnOrg.dataset.bound = "true";
    }

    const btnOpen = $("openPicturesBtn");
    if (btnOpen && !btnOpen.dataset.bound) {
        btnOpen.onclick = () => fetch("/api/pictures-open");
        btnOpen.dataset.bound = "true";
    }
}
async function pollJobStatus() {
    try {
        // NOTE: outputDirName is currently fixed.
        // In future versions, this should come from the backend job status.
        const outputDirName = "Pictures/PhotoWizard";

        const res = await fetch("/api/progress");
        const job = await res.json();

        const pct = job.total
            ? Math.floor((job.done / job.total) * 100)
            : 0;

        $("progressFill").style.width = `${pct}%`;

        if (job.active) {
            $("progressText").textContent =
                `Processing (${job.done}/${job.total})…`;
            setTimeout(pollJobStatus, 500);
        } else {
            const count = job.done || 0;
            $("progressText").textContent =
                `Done. ${count} photos copied to ${outputDirName}.`;
        }
    } catch (err) {
        console.error(err);
    }
}
// ====================================================================
// STEP 7 – Logs
// ====================================================================
function startLogStream() {
    log("--- Connected to backend log stream ---");
    const es = new EventSource("/api/log-stream");
    es.onmessage = evt => log(evt.data);
}

document.querySelector('[data-step="7"]')
    ?.addEventListener("click", startLogStream);


// ====================================================================
// IMAGE PREVIEW – CLOSE HANDLER
// Closes modal when clicking outside image
// ====================================================================
document.addEventListener("click", (e) => {
    const modal = document.getElementById("imageModal");

    if (!modal || modal.classList.contains("d-none")) return;

    if (e.target.id === "imageModal") {
        modal.classList.add("d-none");
    }
});

// ✅ Global keyboard handler (outside)
document.addEventListener("keydown", (e) => {
    const modal = document.getElementById("imageModal");

    if (!modal || modal.classList.contains("d-none")) return;

    if (e.key === "ArrowRight") showNextImage();
    if (e.key === "ArrowLeft") showPreviousImage();
    if (e.key === "Escape") modal.classList.add("d-none");
});

// ✅ Apply manual/detected GPS to all photos in the selected folder group
function applyGPS() {

    console.log("ApplyGPS → currentGroup:", currentGroup);

    if (!manualLocation || !currentGroup) return;

    const status = document.getElementById("mapStatus");

    let count = 0;

    combinedGPS.forEach(item => {

        if (!item || !item.path) return;

        const cleanGroup = currentGroup
            .replace(/\s*\(\d+\)/, "")
            .toLowerCase();

        const path = normalizePath(item.path);

        if (path.split("/").includes(cleanGroup)) {

            const key = normalizePath(item.path);

            metadataMap.set(key, {
                lat: manualLocation.lat,
                lon: manualLocation.lon
            });

            count++;
        }
    });

    // ✅ ✅ ✅ THIS IS THE NEW FEEDBACK BLOCK (RIGHT PLACE)

    console.log("✅ Applied GPS to", count, "files");

    if (status) {
        status.innerHTML = `
            <div class="map-status success">
                ✅ Applied GPS to ${count} file${count === 1 ? "" : "s"}
            </div>
        `;
    }
    console.log("✅ Applied GPS to", count, "files (from combinedGPS)");
    // ✅ ✅ ✅ THEN refresh map
    loadMap();
}
// ============================================================
// GPS Utility: Copy detected EXIF GPS to manual input
// ------------------------------------------------------------
// Purpose:
//   Allows user to copy existing GPS from one image in the
//   selected folder and apply it to all images.
//
// Behaviour:
//   - Uses first available GPS point from combinedGPS
//   - Populates lat/lon input fields
//   - Updates map marker and view
//   - User can then click "Apply GPS" to propagate
//
// Notes:
//   - Safe fallback if no GPS found
//   - Does NOT write EXIF directly (handled by applyManualGPS)
//
// ============================================================

document.getElementById("copyDetectedGpsBtn")
    ?.addEventListener("click", () => {
        const groups = window.folderMarkerGroups;

        if (!groups || !currentGroup || !groups[currentGroup]) {
            alert("No folder selected or no GPS data.");
            return;
        }

        let latSum = 0;
        let lonSum = 0;
        let count = 0;

        // ✅ ONLY use the selected folder (fixes your bug)
        groups[currentGroup].eachLayer(layer => {
            const ll = layer.getLatLng?.();

            if (ll && ll.lat && ll.lng) {
                latSum += ll.lat;
                lonSum += ll.lng;
                count++;
            }
        });

        if (count === 0) {
            alert("No GPS data found in this folder.");
            return;
        }

        // ✅ average location (better than first point)
        const avgLat = latSum / count;
        const avgLon = lonSum / count;

        // ✅ update global state
        manualLocation = {
            lat: avgLat,
            lon: avgLon
        };

        // ✅ update inputs
        const latInput = document.getElementById("latInput");
        const lonInput = document.getElementById("lonInput");

        if (latInput && lonInput) {
            latInput.value = avgLat.toFixed(6);
            lonInput.value = avgLon.toFixed(6);
        }

        // ✅ move map
        if (map) {
            map.setView([avgLat, avgLon], 14);
        }

        console.log(`📍 Using detected GPS for ${currentGroup}:`, avgLat, avgLon);
    });

// ====================================================================
// INITIALIZE
// ====================================================================
document.addEventListener("DOMContentLoaded", () => {
    // ✅ Initial SD button state
    setSDButtonState('initial');
    // ✅ Close preview (X button)
    document.getElementById("closePreview")?.addEventListener("click", () => {
        $("imageModal").classList.add("d-none");
    });
    // ✅  (navigation buttons)
    document.getElementById("nextBtn")?.addEventListener("click", showNextImage);
    document.getElementById("prevBtn")?.addEventListener("click", showPreviousImage);
    // Apply Button:
    document.getElementById("applyDetailsBtn")
        ?.addEventListener("click", applyManualGPS);
});
// ✅ Sidebar navigation
document.querySelectorAll('#wizardNav .sidebar-item').forEach(item => {
    item.addEventListener('click', e => {
        e.preventDefault();
        const step = item.getAttribute('data-step');
        switchStep(step);
    });
});

// ✅ Get analyze button
const analyzeBtn = document.getElementById("analyzeBtn");

if (!analyzeBtn) {
    console.warn("Analyze button not found");
} else {

    analyzeBtn.onclick = async () => {

        console.log("✅ Analyze clicked");

        if (analyzeInProgress) return;

        analyzeInProgress = true;
        analyzeBtn.disabled = true;

        updateProgress(`
    ⏳ <strong>Scanning folders…</strong><br>
    Detecting folder structure on the card
`);

        showAnalyzeStatus("⏳ Analyzing card…");

        let sd = document.getElementById("sdSelect")?.value;

        if (!sd || !sd.includes(":")) {
            showGlobalStatus("⚠️ Please detect and select a valid SD card first.");
            analyzeInProgress = false;
            analyzeBtn.disabled = false;
            return;
        }

        if (!sd.endsWith("\\")) sd += "\\";

        try {
            const res = await fetch("/api/analyze-card", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ sd_card_path: sd })
            });

            const data = await res.json();
            updateProgress(`
    📊 <strong>Folders found:</strong> ${data.analysis.folders.length}<br>
    Preparing photo overview
`);


            if (!data.success) {
                showAnalyzeStatus("⚠️ Analysis failed.");
                return;
            }

            imageCounts = data.analysis.counts || { total: 0, raw: 0, jpg: 0 };
            analyzedFolders = data.analysis.folders;

            updateProgress(`
    📸 <strong>Preparing thumbnails…</strong><br>
    Loading preview images
`);

            renderAnalyzeFolders();

// ✅ stay on folder selection step
            switchStep(2);

        } catch (err) {
            console.error("Analyze failed:", err);
            showAnalyzeStatus("⚠️ Analyze failed due to an error.");
        } finally {
            analyzeInProgress = false;
            analyzeBtn.disabled = false;
            clearAnalyzeStatus();
        }
    };
}
// ✅ Watch for Mapping step becoming visible
setInterval(() => {

    const step = document.querySelector('[data-step="5"]');

    if (!step) return;

    // ✅ Check if it is visible
    const isVisible = !step.classList.contains("d-none");

    if (isVisible && !step.dataset.mapLoaded) {

        console.log("✅ Mapping visible → triggering loadMap");

        step.dataset.mapLoaded = "true";  // prevent repeat
        loadMap();
    }

}, 500);