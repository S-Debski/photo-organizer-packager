// Role: JavaScript module (see Stability Contract)

// ====================================================================
// Photo Organizer main.js – v2.7.1 CLEAN RESET
// ====================================================================

// ====================================================================
// EVENT PRESETS + AUTO‑LEARN
// ====================================================================
const DEFAULT_EVENTS = [
    'Holiday','Birthday','Wedding','Sports','Family','Landscape'
];

let EVENT_PRESETS = [...DEFAULT_EVENTS];

const savedEvents = localStorage.getItem("customEvents");
if (savedEvents) EVENT_PRESETS.push(...JSON.parse(savedEvents));

// ====================================================================
// UTILITIES
// ====================================================================
function $(id) { return document.getElementById(id); }

function log(msg) {
    const area = $("log");
    if (!area) return;
    area.textContent += msg + "\n";
    area.scrollTop = area.scrollHeight;
}

function switchStep(step) {
    document.querySelectorAll('.wizard-step').forEach(s => s.classList.add('d-none'));
    const t = document.querySelector(`.wizard-step[data-step="${step}"]`);
    if (t) t.classList.remove('d-none');

    document.querySelectorAll('#wizardNav .sidebar-item')
        .forEach(a => {
            a.classList.remove('active');
            if (a.getAttribute('data-step') === String(step))
                a.classList.add('active');
        });
}

document.querySelectorAll('#wizardNav .sidebar-item')
    .forEach(link => link.addEventListener('click', () => switchStep(link.getAttribute('data-step'))));

// ====================================================================
// LOG STREAM (Step 7)
// ====================================================================
function startLogStream() {
    log("--- Connected to backend log stream ---");
    const es = new EventSource("/api/log-stream");
    es.onmessage = evt => log(evt.data);
}

document.querySelector('[data-step="7"]')
    ?.addEventListener("click", startLogStream);

// ====================================================================
// STEP 1 – SD Card Detection
// ====================================================================
async function fetchSDCards() {

    const sel = $('sdSelect');
    sel.innerHTML = '';

    // ✅ Show timer (counts up every second)
    let secs = 0;
    $('sdStatus').textContent = `⏳ Detecting SD card… ${secs}s`;

    const timer = setInterval(() => {
        secs++;
        $('sdStatus').textContent = `⏳ Detecting SD card… ${secs}s`;
    }, 1000);

    try {
        const res = await fetch('/api/sd-cards');
        const data = await res.json();

        clearInterval(timer);

        if (!data.success) {
            $('sdStatus').textContent = "⚠️ Error detecting SD card.";
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

        // ✅ SUCCESS MESSAGE
        $('sdStatus').textContent = `✅ SD card found in ${secs}s`;

        // ✅ OPTIONAL: Fade message after 3 seconds
        setTimeout(() => {
            $('sdStatus').textContent = "";
        }, 3000);

    } catch (err) {
        clearInterval(timer);
        $('sdStatus').textContent = "⚠️ Failed to detect SD card.";
        log("SD detection error: " + err);
    }
}
// ====================================================================
// STEP 2 – Analyze SD Card  ✅ CLEAN + FIXED
// ====================================================================
let analyzedFolders = [];

$('analyzeBtn')?.addEventListener('click', async () => {

    let sd = $('sdSelect').value;

    // ✅ Windows: ensure trailing slash
    if (sd && !sd.endsWith('\\')) sd = sd + '\\';

    const res = await fetch('/api/analyze-card', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ sd_card_path: sd })
    });

    const data = await res.json();

    if (!data.success) {
        log("Analyze error: " + data.error);
        return;
    }

    analyzedFolders = data.analysis.folders;
    renderAnalyzeFolders();
    switchStep(2);
});

function renderAnalyzeFolders() {
    const zone = $('foldersList');
    zone.innerHTML = '';

    analyzedFolders.forEach(f => {
        zone.innerHTML += `
            <div class="col-12 mb-2">
                <div class="p-2 border rounded bg-dark-subtle">
                    <b>${f.name}</b>
                    <span class="text-secondary">(${f.photo_count} photos)</span><br>
                    <small class="text-info">${f.path}</small><br>
                    <small class="text-warning">${f.camera_model || "Unknown"} — ${f.lens || "Unknown Lens"}</small>
                </div>
            </div>
        `;
    });
}

// ====================================================================
// STEP 3 – Camera + Lens Stats
// ====================================================================
let cameraStats = {};
let lensStats = {};

function gatherStats() {
    cameraStats = {};
    lensStats = {};

    analyzedFolders.forEach(f => {
        cameraStats[f.camera_model] =
            (cameraStats[f.camera_model] || 0) + f.photo_count;

        lensStats[f.lens] =
            (lensStats[f.lens] || 0) + f.photo_count;
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
    $('cameraStats').innerHTML =
        Object.entries(cameraStats)
            .map(([cam, count]) =>
                `<div class="list-group-item bg-dark-subtle text-light">${cam} (${count})</div>`
            ).join('');
}

function renderLensStats() {
    $('lensStats').innerHTML =
        Object.entries(lensStats)
            .map(([lens, count]) =>
                `<div class="list-group-item bg-dark-subtle text-light">${lens} (${count})</div>`
            ).join('');
}

let cameraChart, lensChart;

function renderCharts() {
    const camNames = Object.keys(cameraStats);
    const camCounts = Object.values(cameraStats);
    const lensNames = Object.keys(lensStats);
    const lensCounts = Object.values(lensStats);

    if (cameraChart) cameraChart.destroy();
    if (lensChart) lensChart.destroy();

    cameraChart = new Chart($('chartCameras'), {
        type: "bar",
        data: {
            labels: camNames,
            datasets: [{ label: "Photos per Camera", data: camCounts, backgroundColor: "#4dc9f6" }]
        },
        options: { responsive: true }
    });

    lensChart = new Chart($('chartLenses'), {
        type: "bar",
        data: {
            labels: lensNames,
            datasets: [{ label: "Photos per Lens", data: lensCounts, backgroundColor: "#f67019" }]
        },
        options: { responsive: true }
    });
}

// ====================================================================
// STEP 4 – Thumbnails (FINAL FIXED VERSION)
// ====================================================================
document.querySelector('[data-step="4"]')
    ?.addEventListener('click', renderThumbnails);

function renderThumbnails() {
    const g = document.getElementById('thumbnailGallery');
    g.innerHTML = '';

    // ✅ Prevent running before Analyze
    if (!analyzedFolders || analyzedFolders.length === 0) {
        g.innerHTML = "<div class='text-warning'>No thumbnails available yet. Please run Analyze first.</div>";
        return;
    }

    let html = '<div class="row g-2">';

    // ✅ Generate real & correct <img> elements
    analyzedFolders
        .flatMap(f => f.photos.slice(0, 50))
        .forEach(p => {
            const safe = encodeURIComponent(p);
            html += `
                <div class="col-2 mb-2">
                    <img src="/api/photo-proxy?path=${safe}"
                         class="thumb img-fluid"
                         draggable="false"
                         ondblclick="window.open('/api/full-image?path=${safe}')">
                </div>`;
        });

    html += '</div>';
    g.innerHTML = html;
}
// ====================================================================
// STEP 5 – Mapping
// ====================================================================
function buildCameraDropdown(selected='') {
    return `
        <select class='form-select form-select-sm cam-name'>
            <option value=''>Camera…</option>
            ${Object.keys(cameraStats).map(c => `<option ${c===selected?'selected':''}>${c}</option>`).join('')}
        </select>`;
}

function buildLensDropdown(selected='') {
    return `
        <select class='form-select form-select-sm lens-name'>
            <option value=''>Lens…</option>
            ${Object.keys(lensStats).map(l => `<option ${l===selected?'selected':''}>${l}</option>`).join('')}
        </select>`;
}

function buildEventDropdown(selected='') {
    return `
        <div class="d-flex gap-2">
            <select class="form-select form-select-sm event-name">
                <option value="">Event…</option>
                ${EVENT_PRESETS.map(e => `<option ${e===selected?'selected':''}>${e}</option>`).join('')}
            </select>
            <button type="button" class="btn btn-sm btn-outline-light add-event-btn">+ Add</button>
        </div>
    `;
}

document.querySelector('[data-step="5"]')
    ?.addEventListener('click', () => {
        renderMappingFolders();
        renderMappingPreview();
        renderApplyControls();
    });

function renderMappingFolders() {
    const zone = $('mappingFolderList');
    zone.innerHTML = '';

    analyzedFolders.forEach(f => {
        zone.innerHTML += `
            <div class='col-12 mb-2'>
              <div class='p-2 border rounded bg-dark-subtle mapping-card'>
                <label>
                  <input type='checkbox' class='folder-check' data-path='${f.path}'> ${f.name}
                </label>

                <div class='row mt-2'>
                    <div class='col-4'>${buildCameraDropdown(f.camera_model)}</div>
                    <div class='col-4'>${buildLensDropdown(f.lens)}</div>
                    <div class='col-4'>${buildEventDropdown()}</div>
                </div>

              </div>
            </div>`;
    });
}

document.addEventListener("change", () => {
    renderMappingPreview();
});

function renderMappingPreview() {
    const preview = $('mappingPreview');
    const rows = [];

    document.querySelectorAll('.folder-check').forEach(chk => {
        if (chk.checked) {
            const row  = chk.closest("div");

            rows.push(`
                <tr>
                    <td>${chk.dataset.path}</td>
                    <td>${row.querySelector(".cam-name").value}</td>
                    <td>${row.querySelector(".lens-name").value}</td>
                    <td>${row.querySelector(".event-name").value}</td>
                </tr>
            `);
        }
    });

    preview.innerHTML = rows.length
        ? `<table class='table table-dark table-sm'>
                <thead><tr><th>Folder</th><th>Camera</th><th>Lens</th><th>Event</th></tr></thead>
                <tbody>${rows.join('')}</tbody>
           </table>`
        : "<i>No selections</i>";
}

// ====================================================================
// ADD EVENT BUTTON
// ====================================================================
document.addEventListener('click', e => {
    if (e.target.classList.contains('add-event-btn')) {
        const modal = new bootstrap.Modal(document.getElementById('addEventModal'));
        $('newEventName').value = "";
        modal.show();
    }
});

$('addEventConfirm')?.addEventListener('click', () => {
    const name = $('newEventName').value.trim();
    if (!name) return;

    EVENT_PRESETS.push(name);

    const customEvents = EVENT_PRESETS.filter(e => !DEFAULT_EVENTS.includes(e));
    localStorage.setItem("customEvents", JSON.stringify(customEvents));

    renderMappingFolders();
    renderMappingPreview();

    const modal = bootstrap.Modal.getInstance(document.getElementById('addEventModal'));
    modal.hide();
});

// ====================================================================
// APPLY CAMERA/EVENT TO ALL (Step 5)
// ====================================================================
function renderApplyControls() {
    const zone = $("applyControls");
    zone.innerHTML = `
        <button class="btn btn-sm btn-info me-2" id="applyCameraAll">Camera → All</button>
        <button class="btn btn-sm btn-warning me-2" id="applyEventAll">Event → All</button>
    `;

    $('applyCameraAll').onclick = () => {
        const val = document.querySelector('.cam-name')?.value;
        if (!val) return;
        document.querySelectorAll('.cam-name').forEach(c => c.value = val);
        renderMappingPreview();
    };

    $('applyEventAll').onclick = () => {
        const val = document.querySelector('.event-name')?.value;
        if (!val) return;
        document.querySelectorAll('.event-name').forEach(c => c.value = val);
        renderMappingPreview();
    };
}

// ====================================================================
// STEP 6 — Organize Photos
// ====================================================================
$('organizeBtn')?.addEventListener('click', async () => {

    const selected = [...document.querySelectorAll('.folder-check:checked')];
    if (selected.length === 0) {
        alert("Please select at least one folder.");
        return;
    }

    let invalid = false;
    selected.forEach(chk => {
        const row = chk.closest("div");
        if (!row.querySelector(".cam-name").value ||
            !row.querySelector(".lens-name").value ||
            !row.querySelector(".event-name").value) {
            invalid = true;
        }
    });

    if (invalid) {
        alert("Some selected folders are missing Camera, Lens or Event.");
        return;
    }

    const sd = $('sdSelect').value;
    const mapping = [];

    selected.forEach(chk => {
        const row  = chk.closest("div");
        mapping.push({
            path: chk.dataset.path,
            camera_name: row.querySelector(".cam-name").value,
            lens_name: row.querySelector(".lens-name").value,
            event_name: row.querySelector(".event-name").value
        });
    });

    const res = await fetch('/api/organize', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ sd_card_path: sd, folder_mapping: mapping })
    });

    const data = await res.json();
    if (!data.success) {
        log("Organize error: " + data.error);
        return;
    }

    etaSamples = [];
    pollJobStatus();
});

// ====================================================================
// PROGRESS / ETA
// ====================================================================
let etaSamples = [];

function computeETA(progress, total) {
    if (progress === 0) return "...";

    const now = performance.now() / 1000;
    etaSamples.push({ progress, time: now });

    if (etaSamples.length > 10)
        etaSamples.shift();

    const a = etaSamples[0];
    const b = etaSamples[etaSamples.length - 1];

    const rate = (b.progress - a.progress) / (b.time - a.time);
    if (rate <= 0) return "...";

    const remaining = total - b.progress;
    const seconds = remaining / rate;

    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}m ${s}s`;
}

async function pollJobStatus() {
    const res = await fetch('/api/job-status');
    const data = await res.json();

    const pct = data.total > 0
        ? ((data.progress / data.total) * 100).toFixed(1)
        : 0;

    $('progressText').textContent =
        `${data.status} — ${data.progress}/${data.total} (${pct}%) — ETA ${computeETA(data.progress, data.total)}`;

    $('progressFill').style.width = `${pct}%`;

    if (data.status === 'copying')
        setTimeout(pollJobStatus, 500);
}

// ====================================================================
// STEP 6 — Open Pictures Folder
// ====================================================================
$('openPicturesBtn')?.addEventListener('click', async () => {
    await fetch('/api/pictures-open');
});