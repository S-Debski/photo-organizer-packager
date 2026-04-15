/* ============================================================
   GLOBAL HELPERS (MUST BE FIRST)
   ============================================================ */
console.log("✅ main.js loaded");
const $ = (id) => document.getElementById(id);

let folderProcessing = false;

/* ============================================================
   STEP SWITCHING
   ============================================================ */
function showStep(stepNum) {
    // debug line only console.log("showStep called:", stepNum);

    document.querySelectorAll(".wizard-step").forEach(step => {
        const n = parseInt(step.dataset.step);
        step.classList.toggle("active-step", n === stepNum);
        step.classList.toggle("d-none", n !== stepNum);
    });

    document.querySelectorAll(".sidebar-item").forEach(item => {
        item.classList.toggle("active", parseInt(item.dataset.step) === stepNum);
    });

    if (stepNum === 3) {
        prepareStatsUI();
    }

    if (stepNum === 4) {
        loadThumbnails();
    }

    if (stepNum === 5) {
        initMap();
        map.invalidateSize();
        loadMap();
    }

}
/* ============================================================
   GLOBAL STATE
   ============================================================ */
let sdFolders = [];
let thumbnails = [];
let currentPreviewIndex = 0;

let cameraChart = null;
let lensChart = null;
let map = null;

/* ============================================================
   STEP 1 — SD CARD DETECTION
   ============================================================ */
async function detectSDCards() {
    const sel = $("sdSelect");
    console.log("Detecting SD cards…");
    const status = $("sdStatus");

    sel.innerHTML = "<option>Detecting...</option>";
    status.textContent = "Detecting SD cards…";

    try {
        const res = await fetch("/api/sd-cards");

        // ✅ NEW: handle HTTP errors explicitly
        if (!res.ok) {
            const text = await res.text();
            console.error("SD API error:", text);
            status.textContent = "❌ SD card detection failed.";
            sel.innerHTML = "<option>No SD card</option>";
            return;
        }

        const data = await res.json();

        // ✅ NEW: guard against unexpected response shape
        if (!data || !Array.isArray(data.drives)) {
            console.error("Invalid SD response:", data);
            console.log("SD DATA RECEIVED:", data);
            status.textContent = "❌ SD card detection failed.";
            sel.innerHTML = "<option>No SD card</option>";
            return;
        }

        sel.innerHTML = "";

        data.drives.forEach((d, idx) => {
            const opt = document.createElement("option");
            opt.value = d.path;
            opt.textContent = `${d.path} — ${d.label || ""}`;
            if (idx === 0) opt.selected = true;
            sel.appendChild(opt);
        });

        if (data.drives.length === 1) {
            status.innerHTML = "✅ <strong>SD card detected</strong> and auto-selected";

            setTimeout(() => {
                analyzeCard();
            }, 100);

        } else {
            status.textContent = `${data.drives.length} SD cards detected`;
        }

    } catch (err) {
        console.error(err);
        status.textContent = "❌ Error detecting SD cards.";
        sel.innerHTML = "<option>No SD card</option>";
    }
}

/* ============================================================
   STEP 2 — ANALYZE CARD
   ============================================================ */
async function analyzeCard() {
    console.log("analyzeCard() called");
    const sd = $("sdSelect").value;
    if (!sd) return;

    $("sdStatus").textContent = "Analyzing card…";

    try {
        const res = await fetch("/api/analyze-card", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sd_card_path: sd })
        });

        const data = await res.json();
        if (!data.success) return;

        sdFolders = data.analysis.folders;

        renderAnalysisFolders();
        showStep(2);

    } catch (err) {
        console.error("Analyze card failed:", err);
    }
}

function renderAnalysisFolders() {
    const box = $("foldersList");
    box.innerHTML = "";

    sdFolders.forEach(f => {
        const wrapper = document.createElement("div");
        wrapper.className = "col-12";

        wrapper.innerHTML = `
            <div class="folder-entry p-3 bg-panel border rounded mb-2" data-folder="${f.path}">
                <b>${f.name}</b>
                ${f.raw_only ? `<span class="badge bg-warning text-dark ms-2">RAW Only</span>` : ``}
                <span class="text-muted">(${f.photo_count} photos)</span>
                <br>
                <small class="text-info">${f.path}</small>
                <br>
                <small class="text-warning">${f.camera_model} — ${f.lens}</small>
            </div>
        `;

        wrapper.onclick = () => selectFolder(f.path);
        box.appendChild(wrapper);
    });
}

/* ============================================================
   STEP 3 — CAMERA & LENS STATS
   ============================================================ */
async function waitForStatsReady() {
    const MAX_WAIT_MS = 30000; // 30 seconds
    const POLL_INTERVAL = 500;
    const start = Date.now();

    while (true) {
        const res = await fetch("/api/exif-stats");
        const data = await res.json();

        if (data && data.ready) {
            return data;
        }

        if (Date.now() - start > MAX_WAIT_MS) {
            throw new Error("Timed out waiting for EXIF stats");
        }

        await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
    }
}

async function selectFolder(folder) {
    if (folderProcessing) {
        console.warn("Folder load already in progress – ignoring click");
        return;
    }

    folderProcessing = true;

    // ✅ RESET thumbnail state when folder changes
    thumbnails = [];
    const gallery = $("thumbnailGallery");
    if (gallery) gallery.innerHTML = "";


    try {
        // Always move to Step 3 immediately
        showStep(3);

        // Destroy existing charts safely
        if (cameraChart) {
            cameraChart.destroy();
            cameraChart = null;
        }
        if (lensChart) {
            lensChart.destroy();
            lensChart = null;
        }

        // Clear thumbnails + map
        thumbnails = [];
        $("thumbnailGallery").innerHTML = "";
        clearMap();

        // Tell backend the new active folder
        const res = await fetch("/api/set-active-folder", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ folder })
        });

        const data = await res.json();
        if (!data.success) {
            throw new Error("set-active-folder failed");
        }

        // Wait for EXIF stats fresh each time
        const stats = await waitForStatsReady();

        $("statsLoading")?.classList.add("d-none");

        renderCameraList(stats.cameras);
        renderLensList(stats.lenses);
        renderCameraChart(stats.cameras);
        renderLensChart(stats.lenses);

        // Let UI breathe first
        //   Promise.resolve().then(loadThumbnails);
        // Promise.resolve().then(loadMap);


    } catch (err) {
        console.error("selectFolder failed:", err);
    } finally {
        folderProcessing = false;
    }
}

function clearMap() {
    if (!map) return;
    map.eachLayer(layer => {
        if (layer instanceof L.Marker) {
            map.removeLayer(layer);
        }
    });
}

function renderCameraList(cameras) {
    const list = $("cameraStats");
    list.innerHTML = cameras.map(c =>
        `<div class="list-group-item">
            <b>${c.model}</b>
            <span class="float-end text-info">${c.count} photos</span>
         </div>`
    ).join("");
}

function renderLensList(lenses) {
    const list = $("lensStats");
    list.innerHTML = lenses.map(l =>
        `<div class="list-group-item">
            <b>${l.lens}</b>
            <span class="float-end text-info">${l.count} photos</span>
         </div>`
    ).join("");
}

function renderCameraChart(cameras) {
    if (cameraChart) cameraChart.destroy();
    cameraChart = new Chart($("chartCameras"), {
        type: "bar",
        data: {
            labels: cameras.map(c => c.model),
            datasets: [{
                label: "Photos",
                data: cameras.map(c => c.count),
                backgroundColor: "#0d6efd"
            }]
        }
    });
}

function prepareStatsUI() {
    const loading = $("statsLoading");
    if (loading) {
        loading.classList.add("d-none");
        loading.style.pointerEvents = "none";
    }

    $("statsLoadingMessage") && ($("statsLoadingMessage").textContent = "");
    $("cameraStats") && ($("cameraStats").innerHTML = "");
    $("lensStats") && ($("lensStats").innerHTML = "");

    // Reset charts safely
    if (cameraChart) {
        cameraChart.destroy();
        cameraChart = null;
    }
    if (lensChart) {
        lensChart.destroy();
        lensChart = null;
    }
}

function renderLensChart(lenses) {
    if (lensChart) lensChart.destroy();
    lensChart = new Chart($("chartLenses"), {
        type: "bar",
        data: {
            labels: lenses.map(l => l.lens),
            datasets: [{
                label: "Photos",
                data: lenses.map(l => l.count),
                backgroundColor: "#6610f2"
            }]
        }
    });
}

/* ============================================================
   STEP 4 — THUMBNAILS
   ============================================================ */
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

// ✅ click should work regardless of where user clicks
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
// function openPreview(i) {
//    currentPreviewIndex = i;
//    const modal = new bootstrap.Modal($("previewModal"));
//    updatePreviewImage();
//    modal.show();
//}

function updatePreviewImage() {
    const img = $("previewImage");

    // Force full-size preview
    img.src = `/api/full-image?path=${encodeURIComponent(
        thumbnails[currentPreviewIndex]
    )}`;

    img.style.maxWidth = "100%";
    img.style.maxHeight = "85vh";
    img.style.width = "auto";
    img.style.height = "auto";
}

/* ============================================================
   STEP 5 — MAP
   ============================================================ */
async function loadMap() {
    const status = document.getElementById("mapStatus");
    status.textContent = ""; // reset

    try {
        const res = await fetch("/api/gps-data");
        const gps = await res.json();

        if (!gps.length) {
            status.innerHTML = `
                <i class="bi bi-geo-alt-slash text-secondary"></i>
                <strong>No GPS location data found</strong><br>
                These photos do not contain EXIF GPS coordinates.
            `;
            return;
        }

        const hasPrecise = gps.some(p => p.quality === "precise");
        const hasCoarse  = gps.some(p => p.quality === "coarse");

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

        // Existing marker logic
        requestAnimationFrame(() => renderMapMarkers(gps));

    } catch (err) {
        console.warn("GPS load failed:", err);
        status.textContent = "Unable to load GPS data.";
    }
}
// Map is initialised lazily when Step 5 becomes visible.
// Height is set inline to avoid flexbox collapse issues.
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
        // Defer expensive fitBounds call
        setTimeout(() => {
            map.fitBounds(points.map(p => [p.lat, p.lon]));
        }, 0);
    }
}

/* ============================================================
   STEP 6 — ORGANIZE
   ============================================================ */
function bindOrganizeEvents() {
    const btnOrg = $("organizeBtn");
    if (btnOrg)
        btnOrg.onclick = async () => {
            const res = await fetch("/api/organize", {method: "POST"});
            if (res.ok) pollJobStatus();
        };

    const btnOpen = $("openPicturesBtn");
    if (btnOpen)
        btnOpen.onclick = () => fetch("/api/pictures-open");
}

async function pollJobStatus() {
    try {
        // NOTE: outputDirName is currently fixed.
        // In future versions, this should come from the backend job status.
        const outputDirName = "Pictures/PhotoWizard";
        //
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

/* ============================================================
   STEP 7 — LOG STREAM
   ============================================================ */
function bindLogStream() {
    const log = $("log");
    if (log) {
        log.textContent = "Live logs are disabled in this build.";
    }
}
/* ============================================================
   INIT — SAFE DOM READY
   ============================================================ */
window.addEventListener("DOMContentLoaded", () => {
    console.log("DOM ready → binding UI");

    showStep(1);
    setTimeout(detectSDCards, 0);

    // ✅ Sidebar navigation
    document.querySelectorAll(".sidebar-item").forEach(item => {
        item.addEventListener("click", () => {
            const step = parseInt(item.dataset.step);
            if (!isNaN(step)) {
                console.log("Sidebar click → showStep", step);
                showStep(step);
            }
        });
    });

    // ✅ Thumbnail click (event delegation — survives re-render)
    const gallery = document.getElementById("thumbnailGallery");
    if (gallery) {
        gallery.addEventListener("click", e => {
            const img = e.target.closest("img[data-fullpath]");
            if (!img) return;

            const path = img.dataset.fullpath;
            openFullImage(path);
        });
    }

    bindLogStream();
});

function openFullImage(path) {
    if (!path) {
        console.warn("openFullImage: no path");
        return;
    }

    const url = `/api/full-image?path=${encodeURIComponent(path)}`;
    console.log("Opening full image:", url);

    window.location.href = url;
}


// ---- SD detection ----
setTimeout(detectSDCards, 0);

const analyzeBtn = document.getElementById("analyzeBtn");
if (analyzeBtn) {
    analyzeBtn.addEventListener("click", () => {
        console.log("Analyze clicked");
        analyzeCard();
    });
} else {
    console.warn("Analyze button not found");
}

document.getElementById("refreshSdBtn")
    ?.addEventListener("click", detectSDCards);

document.getElementById("rescanBtn")
    ?.addEventListener("click", detectSDCards);

// ---- Preview navigation ----
const btnNext = $("previewNext");
if (btnNext) {
    btnNext.onclick = () => {
        currentPreviewIndex = (currentPreviewIndex + 1) % thumbnails.length;
        updatePreviewImage();
    };
}

const btnPrev = $("previewPrev");
if (btnPrev) {
    btnPrev.onclick = () => {
        currentPreviewIndex =
            (currentPreviewIndex - 1 + thumbnails.length) % thumbnails.length;
        updatePreviewImage();
    };
}

// ---- Organize buttons ----
bindOrganizeEvents();
