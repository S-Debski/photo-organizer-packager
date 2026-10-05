// Role: JavaScript module (see Stability Contract)

// ====================================================================
// File: pairing.js
//
// Role:
//   Groups RAW and JPG files into logical image pairs
//
// Responsibilities:
//   - Extract base filenames from file paths
//   - Classify file types (RAW vs JPG)
//   - Pair files sharing same basename AND same directory
//   - Return logical image records for UI + processing
//
// Notes:
//   - Works with path strings returned by /api/thumbs
//   - Pairing is folder-scoped: DSCF9233.RAF in /Medburn will NOT
//     pair with DSCF9233.JPG in /USB even if stems match
//   - Safe against undefined/null entries
//
// Version:
//   v3.0 – folder-scoped pairing
// ====================================================================

const RAW_EXTENSIONS = [
  "CR2", "CR3", "NEF", "ARW", "RAF", "ORF", "RW2", "DNG"
];

// ── Helpers ──────────────────────────────────────────────────────────

function getFullName(file) {
  if (!file) return "";
  if (typeof file === "string") return file;
  return file.name || file.path || "";
}

function getExtension(file) {
  const full = getFullName(file);
  if (!full) return "";
  const name = full.split(/[\\/]/).pop();
  return name.includes(".") ? name.split(".").pop() : "";
}

function getDir(file) {
  const full = getFullName(file);
  if (!full) return "";
  const parts = full.replace(/\\/g, "/").split("/");
  parts.pop();
  return parts.join("/").toLowerCase();
}

export function isRaw(file) {
  return RAW_EXTENSIONS.includes(getExtension(file).toUpperCase());
}

export function isJpg(file) {
  const ext = getExtension(file).toUpperCase();
  return ext === "JPG" || ext === "JPEG";
}

export function getBaseName(file) {
  const full = getFullName(file);
  if (!full) return null;
  const name = full.split(/[\\/]/).pop();
  return name.replace(/\.[^/.]+$/, "");
}

// ── Main export ───────────────────────────────────────────────────────
//
// Key change from v2.8: map key is "dir::stem" not just "stem".
// This prevents cross-folder pairing when two folders on the same
// card share file stems (e.g. Medburn/DSCF9233.RAF + USB/DSCF9233.JPG).
//
export function pairFiles(files) {
  const map = new Map();

  for (const file of files) {
    if (!file) continue;

    const base = getBaseName(file);
    if (!base) continue;

    const dir = getDir(file);
    const key = `${dir}::${base.toUpperCase()}`;   // folder-scoped key

    if (!map.has(key)) {
      map.set(key, {
        baseName: base,
        jpg: null,
        raw: null,
        files: []
      });
    }

    const record = map.get(key);
    record.files.push(file);

    if (isJpg(file)) {
      record.jpg = file;
    } else if (isRaw(file)) {
      record.raw = file;
    }
  }

  return Array.from(map.values());
}