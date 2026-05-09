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
let analyzedFolders = [];
let analyzeInProgress = false;
let selectedFolder = null;   // ✅ NEW: user-selected folder
let thumbnails = [];
let currentPreviewIndex = 0;
let organizePreview = null;
let imageCounts = { total: 0, raw: 0, jpg: 0 };


// ====================================================================
// UTILITIES (shared across all steps)
// ====================================================================
let inferOrganizationTitle = null;

(async () => {
    const mod = await import("/static/js/lib/inferOrganizationTitle.js");
    inferOrganizationTitle = mod.inferOrganizationTitle;
})();

const organizeState = {
    inferredTitle: null,
    userTitle: null,
    userOwnsTitle: false,
};

// User editing the title transfers ownership permanently.
// After this point, automatic inference must not override the title.

$('session-title')?.addEventListener('input', e => {
    organizeState.userTitle = e.target.value;
    organizeState.userOwnsTitle = true;
    organizeState.inferredTitle = null; // optional but clarifies ownership
    organizePreview = null;
});

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

function $(id) { return document.getElementById(id); }

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
            gatherStats();
            renderCameraStats();
            renderLensStats();
            requestAnimationFrame(renderCharts);
            break;

        case 4:
            loadThumbnails();
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
        This can take a moment depending on your card reader and system.
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

    $('sdStatusText').innerHTML = `
    ⏳ <strong>Detecting cards…</strong>
    <div class="small text-muted mt-1">
        This can take a moment depending on your card reader and system.
    </div>
`;

    const timer = setInterval(() => {
        secs++;
        $("sdTimer").textContent = `(${secs}s)`;
    }, 1000);

    try {
        const res = await fetch('/api/sd-cards');
        const data = await res.json();
        clearInterval(timer);

        console.log("[SD-CARDS raw response]", data);
        console.log("[SD-CARDS drives]", data.drives);

        if (!data.success) {
            $('sdStatus').textContent = "⚠️ Error detecting cards.";
            return;
        }

        const visibleDrives = data.drives || [];

        if (visibleDrives.length === 0) {
            $('sdStatus').textContent = showVirtual
                ? "⚠️ No drives detected."
                : "⚠️ No camera cards detected. Insert a card or enable additional drives.";

            setSDButtonState('initial');
            return;
        }

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
// ✅ Enable Analyze button now that a valid card exists
        const analyzeBtn = $("analyzeBtn");
        if (analyzeBtn) analyzeBtn.disabled = false;

        setSDButtonState('loaded');

        const elapsed = Date.now() - startTime;
        setTimeout(() => {
            const durationText = secs > 0 ? `${secs}s` : "under 1s";
            $('sdStatus').textContent =
                `✅ Card detected in ${durationText}. Click "Analyze Card" to continue or rescan if needed.`;

            setTimeout(clearGlobalStatus, 500);
        }, Math.max(0, MIN_VISIBLE_MS - elapsed));

    } catch (err) {
        clearInterval(timer);
        $('sdStatus').textContent = "⚠️ Failed to detect cards.";
        log("SD detection error: " + err);

    } finally {
        // ✅ ALWAYS reset UI state
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
        item.classList.add("col-12", "mb-2", "folder-item");

        item.innerHTML = `
            <div class="card bg-dark border-secondary folder-card p-3">
                <div class="d-flex justify-content-between align-items-center">
                    <div class="fw-bold">
                        📁 ${folder.name || "Unnamed Folder"}
                    </div>
                    <span class="badge bg-primary">
                        ${folder.count || folder.photo_count || 0} photos
                    </span>
                </div>

                <div class="small text-secondary mt-2">
                    RAW: ${folder.raw || folder.raw_count || 0}
                    &nbsp;|&nbsp;
                    JPG: ${folder.jpg || folder.jpeg_count || 0}
                </div>
            </div>
        `;

        item.onclick = async () => {

            const folderPath = folder.path;

            if (!folderPath) {
                console.error("❌ folder.path missing!", folder);
                return;
            }

            selectedFolder = folderPath;

            try {
                const res = await fetch("/api/set-active-folder", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ folder: selectedFolder })
                });

                const data = await res.json();

                if (!data.success) {
                    console.error("❌ Set active folder failed:", data);
                    return;
                }

                // ✅ Clear selection
                document.querySelectorAll(".folder-item")
                    .forEach(el => el.classList.remove("selected"));

                item.classList.add("selected");

                // ✅ Clear sidebar recommendations
                document.querySelectorAll('#wizardNav .sidebar-item')
                    .forEach(el => el.classList.remove('recommended'));

                // ✅ Suggest mapping step
                const mapStep = document.querySelector('[data-step="5"]');
                mapStep?.classList.add('recommended');

                // ✅ Status message
                showGlobalStatus(`
                    ✅ <strong>Folder selected.</strong><br>
                    You can now view stats, thumbnails, or mapping.
                `);

            } catch (err) {
                console.error("❌ Error setting active folder:", err);
            }
        };

        container.appendChild(item);
    });
}

function selectFolder(folderPath) {
    selectedFolder = folderPath;
    const selectedLabel = $("selectedFolderLabel");
    const btn = $("analyzeBtn");
    if (btn) btn.disabled = false;
    if (selectedLabel) {
        selectedLabel.textContent = `Selected: ${folderPath}`;
        selectedLabel.classList.remove("d-none");
    }


    // ✅ Visual selection state
    document.querySelectorAll('.folder-entry')
        .forEach(e => e.classList.remove('active'));

    document
        .querySelector(`.folder-entry[data-folder="${folderPath}"]`)
        ?.classList.add('active');

    // ✅ User feedback
    showGlobalStatus(`
        ✅ <strong>Folder selected.</strong><br>
        You can now view stats, thumbnails, or organize photos.
    `);

    setTimeout(clearGlobalStatus, 3000); // or remove entirely
    // ✅ Suggest next step (visual nudge only)
    const statsStep = document.querySelector('[data-step="3"]');
    if (statsStep) {
        statsStep.classList.add('recommended');
    }
}
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

    // ✅ Guard: do nothing if no folder selected
    if (!selectedFolder) {
        showGlobalStatus("⚠️ No folder selected.");
        return;
    }

    const folder = analyzedFolders.find(f => f.path === selectedFolder);

    if (!folder) return;

    const cam = folder.camera_model || "Unknown";
    const lens = folder.lens || "Unknown Lens";

    cameraStats[cam] = folder.photo_count;
    lensStats[lens] = folder.photo_count;
}

document.querySelector('[data-step="3"]')
    ?.addEventListener("click", () => {
        gatherStats();
        renderCameraStats();
        renderLensStats();
        renderCharts();
    });

function renderCameraStats() {
    const total = Object.values(cameraStats).reduce((a, b) => a + b, 0);

    $('cameraStats').innerHTML =
        Object.entries(cameraStats)
            .sort((a, b) => b[1] - a[1])
            .map(([cam, count]) => {
                const pct = total ? ((count / total) * 100).toFixed(1) : "0.0";
                const folder = analyzedFolders.find(f => f.path === selectedFolder);
                const raw = folder?.raw_count || 0;
                const jpg = folder?.jpeg_count || 0;
                const meta = `
    <div class="small text-muted mt-1">
        RAW: ${raw} · JPEG: ${jpg}
    </div>
`;

                return `
  <div class="list-group-item bg-dark-subtle text-light">
    <strong>${cam}</strong>
    <span class="text-secondary">
      — ${count} photos (${pct}%)
    </span>
    ${meta}
  </div>`;

            })
            .join('');
}

function renderLensStats() {
    const total = Object.values(lensStats).reduce((a, b) => a + b, 0);

    // ✅ Get selected folder counts
    const folder = analyzedFolders.find(f => f.path === selectedFolder);
    const raw = folder?.raw_count || 0;
    const jpg = folder?.jpeg_count || 0;

    $('lensStats').innerHTML =
        Object.entries(lensStats)
            .sort((a, b) => b[1] - a[1])
            .map(([lens, count]) => {
                const pct = total ? ((count / total) * 100).toFixed(1) : "0.0";

                const meta = `
                  <div class="small text-muted mt-1">
                      RAW: ${raw} · JPEG: ${jpg}
                  </div>
                `;

                return `
                  <div class="list-group-item bg-dark-subtle text-light">
                    <strong>${lens}</strong>
                    <span class="text-secondary">
                      — ${count} photos (${pct}%)
                    </span>
                    ${meta}
                  </div>`;
            })
            .join('');
}

let cameraChart = null;
let lensChart = null;

function renderCharts() {
    if (cameraChart) cameraChart.destroy();
    if (lensChart) lensChart.destroy();

    cameraChart = new Chart($('chartCameras'), {
        type: "bar",
        data: {
            labels: Object.keys(cameraStats),
            datasets: [{
                label: "Photos per Camera",
                data: Object.values(cameraStats),
                backgroundColor: "#4dc9f6"
            }]
        },
        options: { responsive: true }
    });

    lensChart = new Chart($('chartLenses'), {
        type: "bar",
        data: {
            labels: Object.keys(lensStats),
            datasets: [{
                label: "Photos per Lens",
                data: Object.values(lensStats),
                backgroundColor: "#f67019"
            }]
        },
        options: { responsive: true }
    });
}
//=====================================================================
// Chert toggle
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

// ====================================================================
// STEP 4 — THUMBNAILS
// ====================================================================
function openFullImage(path) {

    const modal = document.getElementById("imageModal");

    // ✅ Set current index
    currentPreviewIndex = thumbnails.indexOf(path);

    updatePreviewImage();

    modal.classList.remove("d-none");
}
async function loadThumbnails() {

    if (!selectedFolder) {
        console.warn("⚠️ No folder selected");
        return;
    }

    try {
        const res = await fetch("/api/thumbs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                folder: selectedFolder
            })
        });

        const data = await res.json();

        // ✅ Waiting state
        if (!data || data.length === 0) {
            console.log("⏳ Waiting for EXIF cache...");

            // ✅ Show user feedback
            $("thumbnailGallery").innerHTML = `
                <div class="text-muted text-center py-4">
                    ⏳ Preparing thumbnails...
                </div>
            `;

            // ✅ Retry until ready
            setTimeout(loadThumbnails, 1000);
            return;
        }

        // ✅ SUCCESS: render thumbnails
        thumbnails = data;

        $("thumbnailGallery").innerHTML = "";

        renderThumbnailsChunked(thumbnails, 0, 6);

        console.log("✅ Thumbnails loaded:", thumbnails.length);

    } catch (err) {
        console.error("Thumbnail load failed:", err);
    }
}
function showNextImage() {
    if (currentPreviewIndex < thumbnails.length - 1) {
        currentPreviewIndex++;
        updatePreviewImage();
    }
}

function showPreviousImage() {
    if (currentPreviewIndex > 0) {
        currentPreviewIndex--;
        updatePreviewImage();
    }
}

function renderThumbnailsChunked(items, start = 0, chunkSize = 6) {
    const grid = $("thumbnailGallery");
    const end = Math.min(start + chunkSize, items.length);

    for (let i = start; i < end; i++) {
        const t = items[i];

        const div = document.createElement("div");
        div.className = "thumbnail-item col-3";

        const img = document.createElement("img");
        img.src = `/api/photo-proxy?path=${encodeURIComponent(t)}`;
        img.className = "img-fluid";
        img.loading = "lazy";
        img.decoding = "async";

        const open = () => openFullImage(items[i]);
        div.onclick = open;
        img.onclick = open;

        div.appendChild(img);
        grid.appendChild(div);
    }

    if (end < items.length) {
        setTimeout(() => {
            renderThumbnailsChunked(items, end, chunkSize);
        }, 0);
    }
}

function updatePreviewImage() {
    const img = $("previewImage");
    img.src = `/api/full-image?path=${encodeURIComponent(
        thumbnails[currentPreviewIndex]
    )}`;

    img.style.maxWidth = "100%";
    img.style.maxHeight = "85vh";
    img.style.width = "auto";
    img.style.height = "auto";
}

// ====================================================================
// STEP 5 – Mapping: FLOW CONTROL
// Handles delayed navigation to mapping once EXIF worker has run
// ====================================================================
function triggerMappingAfterSelection() {
    console.log("⏳ Waiting for EXIF worker before mapping...");

    setTimeout(() => {
        console.log("🗺️ Switching to Mapping step");
        switchStep(5);
    }, 1500);
}


// ====================================================================
// STEP 5 – Mapping: MAP INITIALISATION
// Responsible for creating and configuring Leaflet map instance
// ====================================================================
let map = null;

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

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
        maxZoom: 18
    }).addTo(map);

    map.setView([51.5, -0.12], 5);
}

// ====================================================================
// STEP 5 – Mapping: DATA LOAD + RENDER
// Fetches GPS data and renders markers onto the map
// ====================================================================
async function loadMap() {
    const status = document.getElementById("mapStatus");
    if (status) status.textContent = "";

    try {
        if (status) {
            status.innerHTML = `
                ⏳ <strong>Loading GPS data…</strong><br>
                Reading metadata from images.
            `;
        }

        const res = await fetch("/api/gps-data", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });

        const gps = await res.json();
        console.log("GPS RESPONSE:", gps);

        if (!gps || gps.length === 0) {
            if (status) {
                status.innerHTML = `
            ⏳ <strong>Scanning for GPS data…</strong><br>
            This can take a moment after selecting a folder.
        `;
            }

            // ✅ retry once (worker still processing)
            setTimeout(loadMap, 1000);

            return;
        }


        if (!map) {
            console.warn("Map not initialised yet");
            return;
        }

        if (status) {
            status.innerHTML = `
                <i class="bi bi-geo-alt-fill text-success"></i>
                <strong>Showing ${gps.length} photo locations</strong><br>
                Locations are based on EXIF GPS data.
            `;
        }

        renderMapMarkers(gps);

    } catch (err) {
        console.warn("GPS load failed:", err);
        if (status) status.textContent = "Unable to load GPS data.";
    }
}

function renderMapMarkers(points, start = 0, chunkSize = 25) {
    if (!map) return;

    const end = Math.min(start + chunkSize, points.length);

    for (let i = start; i < end; i++) {
        const p = points[i];

        L.marker([p.lat, p.lon])
            .addTo(map)
            .bindPopup(`<b>${p.filename || "Photo"}</b>`);
    }

    if (end < points.length) {
        requestAnimationFrame(() =>
            renderMapMarkers(points, end, chunkSize)
        );
    } else {
        setTimeout(() => {
            map.fitBounds(points.map(p => [p.lat, p.lon]));
        }, 0);
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

        const res = await fetch("/api/job-status");
        const job = await res.json();

        const pct = job.total
            ? Math.floor((job.done / job.total) * 100)
            : 0;

        $("progressFill").style.width = `${pct}%`;

        if (job.running) {
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

// ====================================================================
// INITIALIZE
// ====================================================================
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

        showGlobalStatus(
            "⏳ <strong>Analyzing card…</strong><br>" +
            "Reading folders and metadata. This may take a moment."
        );

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

            if (!data.success) {
                showAnalyzeStatus("⚠️ Analysis failed.");
                return;
            }

            imageCounts = data.analysis.counts || { total: 0, raw: 0, jpg: 0 };
            analyzedFolders = data.analysis.folders;

            renderAnalyzeFolders();
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