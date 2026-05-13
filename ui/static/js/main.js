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
let analyzedFolders = [];
let analyzeInProgress = false;
let thumbnails = [];
let currentPreviewIndex = 0;
let organizePreview = null;
let imageCounts = { total: 0, raw: 0, jpg: 0 };
let markerLayer = null;
let currentImages = [];
let selectedFolderGroup = null;
let folderGPS = {};
let folderGroups = {};
let selectedFolder = null;       // "USB" / "Medburn"
let selectedFolderPath = null;   // full path → F:\DCIM\929_FUJI

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
    const parts = path.split("\\");
    return parts.length > 2 ? parts[parts.length - 2] : "Root";
}

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

    // ✅ Use ONE consistent status system
    showGlobalStatus(`
        ⏳ <strong>Detecting cards…</strong><br>
        Reading available drives
    `);

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
            clearGlobalStatus();
            return;
        }

        const visibleDrives = data.drives || [];

        if (visibleDrives.length === 0) {
            $('sdStatus').textContent = showVirtual
                ? "⚠️ No drives detected."
                : "⚠️ No camera cards detected. Insert a card or enable additional drives.";

            setSDButtonState('initial');
            clearGlobalStatus();
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

        // ✅ Enable Analyze button
        const analyzeBtn = $("analyzeBtn");
        if (analyzeBtn) analyzeBtn.disabled = false;

        setSDButtonState('loaded');

        const elapsed = Date.now() - startTime;

        setTimeout(() => {
            const durationText = secs > 0 ? `${secs}s` : "under 1s";

            $('sdStatus').textContent =
                `✅ Card detected in ${durationText}. Click "Analyze Card" to continue or rescan if needed.`;

            // ✅ clean success message
            showGlobalStatus("✅ Card detected");
            setTimeout(clearGlobalStatus, 1200);

        }, Math.max(0, MIN_VISIBLE_MS - elapsed));

    } catch (err) {
        clearInterval(timer);
        $('sdStatus').textContent = "⚠️ Failed to detect cards.";
        log("SD detection error: " + err);
        clearGlobalStatus();

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

//====================================================================
// Group Images by folder
// ====================================================================
function groupByFolder(images) {
    const groups = {};

    images.forEach(img => {
        const folder = getFolderName(img.path || img);

        if (!groups[folder]) {
            groups[folder] = [];
        }

        groups[folder].push(img);
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

    // ✅ create a button per folder
    Object.keys(folderGroups).forEach(folder => {
        const btn = document.createElement("button");

        btn.className = "btn btn-sm btn-outline-secondary m-1";
        btn.textContent = `${folder} (${folderGroups[folder].length})`;

        btn.onclick = () => {

            selectedFolder = folder;

            const group = folderGroups[folder];
            selectedFolderGroup = group;

            if (!group || group.length === 0) {
                selectedFolderPath = null;
                return;
            }

            const firstImage = group[0];

            if (firstImage && firstImage.path) {
                selectedFolderPath = firstImage.path
                    .split(/[\\/]/)
                    .slice(0, -1)
                    .join("\\");
            } else {
                selectedFolderPath = null;
            }

            // ✅ highlight button
            container.querySelectorAll("button")
                .forEach(b => b.classList.remove("active"));

            btn.classList.add("active");

            // Show gps co-ords on folder click
            const gps = folderGPS[selectedFolder];

            if (gps) {
                manualLocation = gps;

                document.getElementById("latInput").value = gps.lat.toFixed(6);
                document.getElementById("lonInput").value = gps.lon.toFixed(6);

                updateFromInputs();
            }
        };

        container.appendChild(btn);
    });
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

        item.onclick = async () => {

            const folderPath = folder.path;

            if (!folderPath) {
                console.error("❌ folder.path missing!", folder);
                return;
            }

            selectedFolderPath = folderPath;   // full path ✅
            selectedFolder = folderPath.split(/[\\/]/).pop();  // name ✅

            // ✅ Reset map state
            gpsRetryCount = 0;

            const status = document.getElementById("mapStatus");
            if (status) status.innerHTML = "";

            // ✅ Read working directory from FIRST PAGE ONLY
            const workingDirInput = document.getElementById("workingDirInput");

            let workingDir = null;

            if (workingDirInput) {
                const val = workingDirInput.value.trim();
                if (val.length > 0) {
                    workingDir = val;
                }
            }

            try {
                const res = await fetch("/api/set-active-folder", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        folder: selectedFolderPath,
                        working_dir: workingDir
                    })
                });

                const data = await res.json();

                if (!data.success) {
                    console.error("❌ Set active folder failed:", data);
                    return;
                }

                // ✅ Highlight selection
                document.querySelectorAll(".folder-item")
                    .forEach(el => el.classList.remove("selected"));

                item.classList.add("selected");

                // ✅ Mark mapping as next step
                document.querySelectorAll('#wizardNav .sidebar-item')
                    .forEach(el => el.classList.remove('recommended'));

                const mapStep = document.querySelector('[data-step="5"]');
                mapStep?.classList.add('recommended');

                // ✅ Show confirmed working directory (read‑only)
                showGlobalStatus(`
                    ✅ <strong>Folder selected.</strong><br>
                    Working directory: ${data.working_dir}<br>
                    You can now view stats, thumbnails, or mapping.
                `);

            } catch (err) {
                console.error("❌ Error setting active folder:", err);
            }
        };

        container.appendChild(item);
    });
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

    if (!selectedFolder) {
        console.warn("⚠️ No folder selected");
        return;
    }

    try {
        const res = await fetch("/api/thumbs", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                folder: selectedFolderPath
            })
        });
        const data = await res.json();

// ✅ waiting
        if (!data || data.length === 0) {
            console.log("⏳ Waiting for EXIF cache...");

            $("thumbnailGallery").innerHTML = `
        <div class="text-muted text-center py-4">
            ⏳ Preparing thumbnails…<br>
            <small>This can take a few seconds on first load</small>
        </div>
    `;

            setTimeout(loadThumbnails, 1000);
            return;
        }

// ✅ SUCCESS: render thumbnails
        thumbnails = data;
        currentImages = data;   // keep full dataset

        $("thumbnailGallery").innerHTML = "";

        renderThumbnailsChunked(thumbnails, 0, 6);

        console.log("✅ Thumbnails loaded:", thumbnails.length);

// ✅ ✅ STEP 3: prepare folder grouping (NEW)
        window.folderGroups = groupByFolder(currentImages);

    } catch (err) {
        console.error("Thumbnail load failed:", err);
    }
}

function prepareFolderGrouping(images) {
    if (!images || images.length === 0) return;

    console.log("📂 Preparing folder groups for mapping...");

    // ✅ ALWAYS use working directory images
    window.folderGroups = groupByFolder(currentImages);

    console.log("✅ Folder groups:", Object.keys(window.folderGroups));
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
        const t = items[i];

        // ✅ Wrapper
        const div = document.createElement("div");
        div.className = "thumbnail-item col-3";
        div.style.textAlign = "center";

        // ✅ Image
        const img = document.createElement("img");
        img.src = `/api/photo-proxy?path=${encodeURIComponent(t)}`;
        img.className = "img-fluid";
        img.loading = "lazy";
        img.decoding = "async";

        // ✅ Click handler
        const open = () => openFullImage(items[i]);
        div.onclick = open;
        img.onclick = open;

        // ✅ Filename extraction
        const filename = t.split("\\").pop() || t.split("/").pop();

        // ✅ Label
        const label = document.createElement("div");
        label.textContent = filename;
        label.className = "thumb-label";  // ✅ use CSS
        label.title = filename;           // ✅ full name on hover

        // ✅ Assemble
        div.appendChild(img);
        div.appendChild(label);
        grid.appendChild(div);
    }

    // ✅ Continue chunking
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

Object.keys(folderGroups).forEach(folder => {

    const btn = document.createElement("button");

    btn.onclick = () => {

        selectedFolder = folder;

        const group = folderGroups[folder];
        selectedFolderGroup = group;

        if (!group || group.length === 0) {
            selectedFolderPath = null;
            return;
        }

        const firstImage = group[0];

        if (firstImage && firstImage.path) {
            selectedFolderPath = firstImage.path
                .split(/[\\/]/)
                .slice(0, -1)
                .join("\\");
        } else {
            selectedFolderPath = null;
        }

        console.log("📂 Selected folder:", selectedFolder);
        console.log("📁 Folder path:", selectedFolderPath);

        container.querySelectorAll("button")
            .forEach(b => b.classList.remove("active"));

        btn.classList.add("active");
    };

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
        const { lat, lng } = e.latlng;

        manualLocation = { lat, lng };

        console.log("📍 Selected manual location:", manualLocation);

        // ✅ Clear previous marker
        markerLayer.clearLayers();

        // ✅ Add new marker
        L.marker([lat, lng])
            .addTo(markerLayer)
            .bindPopup("Manual location")
            .openPopup();

        // ✅ Zoom to selected point (THIS is where it goes ✅)
        map.setView([lat, lng], 14);

        // ✅ Show / update details panel
        const panel = document.getElementById("locationDetails");
        if (panel) panel.style.display = "block";

        const latInput = document.getElementById("latInput");
        const lonInput = document.getElementById("lonInput");

        if (latInput && lonInput) {
            latInput.value = lat.toFixed(6);
            lonInput.value = lng.toFixed(6);
        }

        showManualLocation(lat, lng);
    });


}

let gpsRetryCount = 0;
// ✅ Sync manual input → map + state
document.getElementById("latInput")?.addEventListener("change", updateFromInputs);
document.getElementById("lonInput")?.addEventListener("change", updateFromInputs);


async function loadMap() {
    const status = document.getElementById("mapStatus");
    const folderContainer = document.getElementById("folderSelector");

    // ✅ Clear markers once at start
    if (markerLayer) {
        markerLayer.clearLayers();
    }

    // ✅ Clear folder selector (important when switching folders)
    if (folderContainer) {
        folderContainer.innerHTML = "";
    }

    try {
        // ✅ First call only → show loading
        if (gpsRetryCount === 0 && status) {
            status.innerHTML = `
                <div class="map-status loading">
                    ⏳ <strong>Loading GPS data…</strong><br>
                    Reading metadata from images.
                </div>
            `;
        }

        const res = await fetch("/api/gps-data", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({})
        });

        const gps = await res.json();

        // ✅ EMPTY GPS CASE
        if (!gps || gps.length === 0) {

            let prog = { active: false };

            try {
                const progRes = await fetch("/api/progress");
                prog = await progRes.json();
            } catch {}

            // ✅ STILL SCANNING
            if (prog.active) {
                if (status) {
                    status.innerHTML = `
                        <div class="map-status loading">
                            ⏳ <strong>Scanning for GPS data…</strong><br>
                            Extracting metadata from images.
                        </div>
                    `;
                }

                setTimeout(loadMap, 1000);
                return;
            }

            // ✅ DONE → NO GPS → FINAL STATE
            if (status) {
                status.innerHTML = `
                    <div class="map-status warning">
                        ⚠️ <strong>No GPS data found</strong><br>
                        Select a folder and click on the map to assign a location.
                    </div>
                `;
            }

            // ✅ Show input panel immediately (UX fix)
            const panel = document.getElementById("locationDetails");
            if (panel) panel.style.display = "block";

// ✅ render folder buttons
            if (currentImages && currentImages.length && folderContainer) {
                renderFolderSelector(currentImages);
            }

            return;
        }

        // ✅ SUCCESS (GPS exists)
        gpsRetryCount = 0;

        if (!map) return;

        if (status) {
            status.innerHTML = `
                <div class="map-status success">
                    <i class="bi bi-geo-alt-fill"></i>
                    <strong>Showing ${gps.length} photo locations</strong><br>
                    Locations are based on EXIF GPS data.
                </div>
            `;
        }

        renderMapMarkers(gps);

    } catch (err) {
        console.warn("GPS load failed:", err);

        if (status) {
            status.innerHTML = `
                <div class="map-status warning">
                    ⚠️ <strong>Unable to load GPS data</strong>
                </div>
            `;
        }
    }
}

function showManualLocation(lat, lng) {
    console.log("currentImages length:", currentImages?.length);
    console.log("selectedFolderGroup:", selectedFolderGroup);

    const status = document.getElementById("mapStatus");

    if (!status) return;

    status.innerHTML = `
        <div class="map-status info">
            📍 <strong>Selected location</strong><br>
            ${lat.toFixed(5)}, ${lng.toFixed(5)}<br>

            <button id="applyGpsBtn"
                    class="btn btn-sm btn-primary mt-2">
                Apply to all images
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
    updateFromInputs();   // ✅ ensures latest values used

    if (!manualLocation) return;
    const lat = manualLocation.lat;
    const lon = manualLocation.lon ?? manualLocation.lng;
    if (selectedFolder) {
        folderGPS[selectedFolder] = { lat, lon };
        console.log("📍 Saved GPS for folder:", selectedFolder, folderGPS[selectedFolder]);
    }

    let targetImages;

    if (!selectedFolder) {
        console.warn("❌ No folder selected — refusing to apply GPS globally");
        alert("Please select a folder before applying GPS");
        return;
    }

    console.log("🔍 APPLY CLICK");
    console.log("Selected folder:", selectedFolder);

    const group = folderGroups[selectedFolder];

    if (!group || group.length === 0) {
        console.warn("⚠️ No group for folder:", selectedFolder);
        return;
    }

    targetImages = group;

    console.log("✅ Applying GPS to:", targetImages.length, "images");

    /*if (targetImages.length === 0) {
        console.warn("⚠️ No matching images for folder:", selectedFolder);
        return;

        redundant - to be removed later
    }*/

    // when user switches folder
    const gps = folderGPS[selectedFolder];
    if (gps) {
        console.log("📍 Using saved GPS for", selectedFolder);
    }
    console.log("✅ Applying GPS to:", targetImages.length, "images");
    console.log("Selected folder:", selectedFolder);
    console.log("Images matched:", targetImages.length);
    console.log("Selected folder:", selectedFolder);
    console.log("Matches:", targetImages.length);

    // might be wrong place
    targetImages.forEach(img => {
        console.log("MATCH:", img.path);
    });


    // ✅ Clear markers
    markerLayer.clearLayers();

    // ✅ Update markers visually
    targetImages.forEach(img => {
//        img.manualGPS = { lat, lng: lon };
        img.manualGPS = { lat: lat, lon: lon };
        L.marker([lat, lon])
            .addTo(markerLayer)
            .bindPopup(getFilename(img));
    });


// ✅ Prepare file list for backend
    const flatFiles = (targetImages || [])
        .map(img => typeof img === "string" ? img : img.path)
        .filter(Boolean);

// ✅ Pair them
    const groups = pairImages(flatFiles);

// ✅ Expand back to files, but grouped
    const files = [];

    groups.forEach(g => {
        if (g.jpg) files.push(g.jpg);
        if (g.raw) files.push(g.raw);
    });
    console.log("📤 File count:", files.length);
    console.log(`📷 ${groups.length} image groups (${files.length} files)`);

// Show exif write progress
    function pollWriteProgress() {
        fetch("/api/write-progress")
            .then(res => res.json())
            .then(data => {

                if (!data.active) {
                    showGlobalStatus("✅ GPS writing complete");
                    return;
                }

                const pct = data.total
                    ? Math.floor((data.done / data.total) * 100)
                    : 0;

                showGlobalStatus(`
                ⏳ Writing GPS to images...<br>
                ${data.done} / ${data.total} (${pct}%)
            `);

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

    const end = Math.min(start + chunkSize, points.length);

    for (let i = start; i < end; i++) {
        const p = points[i];

        const marker = L.marker([p.lat, p.lon]);
        marker.bindPopup(`<b>${p.filename || "Photo"}</b>`);

        markerLayer.addLayer(marker);   // ✅ IMPORTANT

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
            switchStep(2);

            showGlobalStatus(`
    ✅ <strong>Analysis complete</strong><br>
    <span>Select a folder below to continue</span>
`);

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