// ====================================================================
// Photo Organizer main.js – v2.8.0
//
// Main UI controller for the Wizard workflow.
// Handles:
//   - SD card detection
//   - Analyze → session defaults
//   - Pre‑Import editing (title / date)
//   - Mapping and Organize orchestration
//
// NOTE:
// This file intentionally binds UI logic lazily as steps become active.
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
    document.querySelectorAll('.wizard-step')
        .forEach(s => s.classList.add('d-none'));

    const t = document.querySelector(`.wizard-step[data-step="${step}"]`);
    if (t) t.classList.remove('d-none');

// ✅ Bind Pre‑Import inputs ONLY when Step 6 is shown
// Avoids null references and duplicate event handlers
    if (step === 6) {
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

        $('sdStatus').textContent = `✅ SD card found in ${secs}s`;

    } catch (err) {
        clearInterval(timer);
        $('sdStatus').textContent = "⚠️ Failed to detect SD card.";
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

$('analyzeBtn')?.addEventListener('click', async () => {

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
        return;
    }

    analyzedFolders = data.analysis.folders;
    renderAnalyzeFolders();

    // ✅ Populate Pre‑Import defaults from Analyze response
    const titleInput = $('session-title');
    const dateInput  = $('session-date');

    if (data.session) {
        if (titleInput) titleInput.value = data.session.title || '';
        if (dateInput)  dateInput.value  = data.session.shoot_date || '';
    }

    // ✅ Jump directly to Pre‑Import (defaults are now ready)

    switchStep(6);
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
      </div>`;
    });
}

// ====================================================================
// Pre‑Import: Editable session metadata
// Sends user edits (title / date) to backend state.
// Preview updates are handled elsewhere.
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

// ====================================================================
// STEP 6 – Pre‑Import & Organize
// User confirms session metadata and mapping,
// then explicitly starts the Organize operation.
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
        const row = chk.closest("div");
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

    pollJobStatus();
});

// ====================================================================
// INITIALIZE WIZARD
// ====================================================================
document.addEventListener("DOMContentLoaded", () => {
    fetchSDCards();
    $('sdStatus').textContent = "⏳ Detecting SD card… 0s";
});