// Role: JavaScript module (see Stability Contract)
//ROLE_MAP["main.js"] = "Frontend application entry point"
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

// ====================================================================
// UTILITIES (shared across all steps)
// ====================================================================
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

            const folder = analyzedFolders.find(f => f.path === selectedFolder);
            if (folder) {
                // Title (already correct)
                $('session-title').value = folder.name;

                // ✅ Shoot date (RESTORE v2.7 behaviour)
                if (folder.shoot_date) {
                    $('session-date').value = folder.shoot_date;
                }
            }

            bindOrganizeEvents();
            clearGlobalStatus();
            break;
    }   // ✅ closes switch(step)
}       // ✅ closes function switchStep

function showGlobalStatus(msg) {
    const el = document.getElementById("globalStatus");
    if (!el) return;

    el.innerHTML = msg;
    el.classList.remove("d-none");

    // ✅ Ensure it is visible even if contentArea is scrolled
    el.scrollIntoView({ behavior: "smooth", block: "start" });
}

function clearGlobalStatus() {
    const el = document.getElementById("globalStatus");
    if (!el) return;
    el.classList.add("d-none");
    el.innerHTML = "";
}

$('refreshSdBtn')?.addEventListener('click', () => {
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
    sel.innerHTML = '';

    let secs = 0;
    const startTime = Date.now();
    const MIN_VISIBLE_MS = 600;

    $('sdStatus').innerHTML = `
        ⏳ <strong>Detecting cards…</strong><br>
        This can take a moment depending on your card reader and system.
    `;

    const timer = setInterval(() => {
        secs++;
        $('sdStatus').innerHTML = `
            ⏳ <strong>Detecting cards…</strong><br>
            This can take a moment depending on your card reader and system.
            <span class="ms-1 text-muted">(${secs}s)</span>
        `;
    }, 1000);

    try {
        const res = await fetch('/api/sd-cards');
        const data = await res.json();
        clearInterval(timer);

        if (!data.success) {
            $('sdStatus').textContent = "⚠️ Error detecting cards.";
            sel.innerHTML = "<option>Error loading cards</option>";
            return;
        }

        sel.innerHTML = '';
        (data.drives || []).forEach(d => {
            const opt = document.createElement('option');
            opt.value = d.path;
            opt.textContent = `${d.path} — ${d.label || ''}`;
            sel.appendChild(opt);
        });

        const elapsed = Date.now() - startTime;
        setTimeout(() => {
            const durationText = secs > 0 ? `${secs}s` : "under 1s";

            $('sdStatus').textContent =
                `✅ Cards detected in ${durationText} (reader / system dependent)`;

            // ✅ Clear global banner shortly after completion
            setTimeout(clearGlobalStatus, 500);

        }, Math.max(0, MIN_VISIBLE_MS - elapsed));

    } catch (err) {
        clearInterval(timer);
        $('sdStatus').textContent = "⚠️ Failed to detect cards.";
        log("SD detection error: " + err);
    }
}
// ====================================================================
// STEP 2 – Analyze SD Card
// Derives:
//   - folder analysis
//   - default session metadata (title / shoot_date)
// Then stay on analyze to check folders (Step 6)
// ====================================================================
function renderAnalyzeFolders() {
    const zone = $('foldersList');
    if (!zone) return;

    zone.innerHTML = '';

    if (!Array.isArray(analyzedFolders) || analyzedFolders.length === 0) {
        zone.innerHTML =
            "<div class='text-warning'>No folders found.</div>";
        return;
    }

    analyzedFolders.forEach(f => {
        zone.innerHTML += `
          <div class="col-12 mb-2">
            <div class="folder-entry p-2 border rounded bg-dark-subtle"
                 data-folder="${f.path}">
              <b>${f.name}</b>
              <span class="text-secondary">(${f.photo_count} photos)</span><br>
              <small class="text-info">${f.path}</small><br>
              <small class="text-warning">
                ${f.camera_model || "Unknown"} — ${f.lens || "Unknown Lens"}
              </small>
            </div>
          </div>`;
    });

    // ✅ Attach click handlers AFTER rendering
    zone.querySelectorAll('.folder-entry').forEach(el => {
        el.addEventListener('click', () => {
            selectFolder(el.dataset.folder);
        });
    });
}

function selectFolder(folderPath) {
    selectedFolder = folderPath;

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

    setTimeout(clearGlobalStatus, 1500);
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

    analyzedFolders.forEach(f => {
        const cam = f.camera_model || "Unknown";
        const lens = f.lens || "Unknown Lens";

        cameraStats[cam] = (cameraStats[cam] || 0) + f.photo_count;
        lensStats[lens] = (lensStats[lens] || 0) + f.photo_count;
    });
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
                return `
                  <div class="list-group-item bg-dark-subtle text-light">
                    <strong>${cam}</strong>
                    <span class="text-secondary">
                      — ${count} photos (${pct}%)
                    </span>
                  </div>`;
            })
            .join('');
}

function renderLensStats() {
    const total = Object.values(lensStats).reduce((a, b) => a + b, 0);

    $('lensStats').innerHTML =
        Object.entries(lensStats)
            .sort((a, b) => b[1] - a[1])
            .map(([lens, count]) => {
                const pct = total ? ((count / total) * 100).toFixed(1) : "0.0";
                return `
                  <div class="list-group-item bg-dark-subtle text-light">
                    <strong>${lens}</strong>
                    <span class="text-secondary">
                      — ${count} photos (${pct}%)
                    </span>
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
async function loadThumbnails() {
    try {
        const res = await fetch("/api/thumbs");
        thumbnails = await res.json();
        $("thumbnailGallery").innerHTML = "";
        renderThumbnailsChunked(thumbnails, 0, 6);
    } catch (err) {
        console.error("Thumbnail load failed:", err);
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
// STEP 5 – Mapping
// ====================================================================

let map = null;

// Map is initialised lazily when Step 5 becomes visible.
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

async function loadMap() {
    const status = document.getElementById("mapStatus");
    if (status) status.textContent = "";

    try {
        const res = await fetch("/api/gps-data");
        const gps = await res.json();

        if (!gps.length) {
            if (status) {
                status.innerHTML = `
                    <i class="bi bi-geo-alt-slash text-secondary"></i>
                    <strong>No GPS location data found</strong><br>
                    These photos do not contain EXIF GPS coordinates.
                `;
            }
            return;
        }

        const hasPrecise = gps.some(p => p.quality === "precise");
        const hasCoarse  = gps.some(p => p.quality === "coarse");

        if (status) {
            if (!hasPrecise && hasCoarse) {
                status.innerHTML = `
                    <i class="bi bi-exclamation-triangle text-warning"></i>
                    <strong>Approximate location data</strong><br>
                    Location information is low‑precision and may represent a region.
                `;
            } else if (hasPrecise && hasCoarse) {
                status.innerHTML = `
                    <i class="bi bi-geo text-info"></i>
                    <strong>Mixed GPS accuracy</strong><br>
                    Some photos have precise locations; others are approximate.
                `;
            } else {
                status.innerHTML = `
                    <i class="bi bi-geo-alt-fill text-success"></i>
                    <strong>Showing photo locations</strong><br>
                    Locations are based on EXIF GPS data from the camera.
                `;
            }
        }

        requestAnimationFrame(() => renderMapMarkers(gps));

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
            .bindPopup(`<b>${p.filename}</b>`);
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
// INITIALIZE
// ====================================================================
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('#wizardNav .sidebar-item').forEach(item => {
        item.addEventListener('click', e => {
            e.preventDefault();
            const step = item.getAttribute('data-step');
            switchStep(step);
        });
    });

    const analyzeBtn = document.getElementById("analyzeBtn");
    if (!analyzeBtn) {
        console.warn("Analyze button not found");
        return;
    }

    analyzeBtn.addEventListener("click", async () => {

        if (analyzeInProgress) return;
        analyzeInProgress = true;
        analyzeBtn.disabled = true;

        showGlobalStatus(
            "⏳ <strong>Analyzing card…</strong><br>" +
            "Reading folders and metadata. This may take a moment."
        );
        showAnalyzeStatus("⏳ Analyzing card…");

        try {
            let sd = document.getElementById("sdSelect")?.value;
            if (sd && !sd.endsWith("\\")) sd += "\\";

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

            analyzedFolders = data.analysis.folders;
            renderAnalyzeFolders();

            switchStep(2);

            showGlobalStatus(
                "✅ <strong>Analysis complete.</strong><br>" +
                "Select a folder below to continue."
            );
            setTimeout(clearGlobalStatus, 2000);

        } finally {
            analyzeInProgress = false;
            analyzeBtn.disabled = false;
            clearAnalyzeStatus();
        }
    });
});