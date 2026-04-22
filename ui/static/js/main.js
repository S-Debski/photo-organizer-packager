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
    document.querySelectorAll('.wizard-step')
        .forEach(s => s.classList.add('d-none'));

    const t = document.querySelector(`.wizard-step[data-step="${step}"]`);
    if (t) t.classList.remove('d-none');
// ✅ Ensure Step 3 stats are rendered whenever Step 3 is shown
    if (step === 3 && analyzedFolders.length > 0) {
        gatherStats();
        renderCameraStats();
        renderLensStats();

        // ✅ Defer chart rendering until layout is complete
        requestAnimationFrame(() => {
            renderCharts();
        });
    }

    // ✅ Bind Pre‑Import inputs ONLY when Step 6 is shown
    if (step === 6) {
        clearGlobalStatus();   // ✅ clear once user reaches Organize
        const titleInput = $('session-title');
        const dateInput  = $('session-date');

        if (titleInput && !titleInput.dataset.bound) {
            titleInput.addEventListener("input", updateSessionMeta);
            titleInput.dataset.bound = "true";
        }

        if (dateInput && !dateInput.dataset.bound) {
            dateInput.addEventListener("change", updateSessionMeta);
            dateInput.dataset.bound = "true";
        }
    }

    document.querySelectorAll('#wizardNav .sidebar-item')
        .forEach(a => {
            a.classList.remove('active');
            if (a.getAttribute('data-step') === String(step))
                a.classList.add('active');
        });
}

document.querySelectorAll('#wizardNav .sidebar-item')
    .forEach(link =>
        link.addEventListener('click', () =>
            switchStep(link.getAttribute('data-step'))
        )
    );

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

    // ✅ ALWAYS-visible, user-facing explanation
    $('sdStatus').innerHTML = `
        ⏳ <strong>Detecting cards…</strong><br>
        This can take a moment depending on your card reader and system.
        <span class="ms-1 text-muted">(0s)</span>
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

        $('sdStatus').textContent = `✅ Cards detected in ${secs}s (reader / system dependent)`;
// ✅ Give the user time to see completion before anything else happens
        setTimeout(() => {
            // Do nothing here yet — just allow UI to breathe
        }, 800);

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
// Then transitions directly to Pre‑Import (Step 6)
// ====================================================================
let analyzedFolders = [];
let analyzeInProgress = false;

$('analyzeBtn')?.addEventListener('click', async () => {

    if (analyzeInProgress) {
        showAnalyzeStatus("⏳ Analyzing card… no need to click again.");
        showGlobalStatus("⏳ Analyzing card… no need to click again.");
        return;
    }

    analyzeInProgress = true;

    showAnalyzeStatus("⏳ Analyzing card… this may take a moment.");
    showGlobalStatus("⏳ Analyzing card… this may take a moment.");

    const btn = $('analyzeBtn');
    if (btn) btn.disabled = true;

    try {
        let sd = $('sdSelect').value;
        if (sd && !sd.endsWith('\\')) sd += '\\';

        const res = await fetch('/api/analyze-card', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ sd_card_path: sd })
        });

        const data = await res.json();

        if (!data.success) {
            log("Analyze error: " + data.error);
            showAnalyzeStatus("⚠️ Analysis failed. Please try again.");
            clearGlobalStatus();
            return;
        }

        analyzedFolders = data.analysis.folders;
        renderAnalyzeFolders();

        const titleInput = $('session-title');
        const dateInput  = $('session-date');

        if (data.session) {
            if (titleInput) titleInput.value = data.session.title || '';
            if (dateInput)  dateInput.value  = data.session.shoot_date || '';
        }

        clearAnalyzeStatus();
        switchStep(6);

    } finally {
        analyzeInProgress = false;
        if (btn) btn.disabled = false;
    }
});
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
// STEP 4 – Thumbnails
// ====================================================================
document.querySelector('[data-step="4"]')
    ?.addEventListener('click', renderThumbnails);

function renderThumbnails() {
    const g = $('thumbnailGallery');
    g.innerHTML = '';

    if (!analyzedFolders.length) {
        g.innerHTML = "<div class='text-warning'>Run Analyze first.</div>";
        return;
    }

    let html = '<div class="row g-2">';
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
// (unchanged from your current implementation)


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
    $('sdStatus').textContent = "Click Refresh to detect cards.";
});
