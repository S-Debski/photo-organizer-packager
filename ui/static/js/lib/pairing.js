// Role: JavaScript module (see Stability Contract)

// ====================================================================
// File: pairing.js
//
// Role:
//   Groups RAW and JPG files into logical image pairs
//
// Responsibilities:
//   - Extract base filenames from file/path
//   - Classify file types (RAW vs JPG)
//   - Pair files sharing same basename
//   - Return logical image records for UI + processing
//
// Notes:
//   - Works with backend JSON objects (not File objects)
//   - Uses file.path when file.name is unavailable
//   - Safe against undefined/null entries
//
// Author:
//   Steve Dębski
//
// Version:
//   v2.8 – RAW/JPG Pairing
// ====================================================================

const RAW_EXTENSIONS = [
  "CR2", "CR3", "NEF", "ARW", "RAF", "ORF", "RW2", "DNG"
];

// ✅ unified filename source

function getFullName(file) {
  if (!file) return "";
  if (typeof file === "string") return file;  // ✅ THIS MUST EXIST
  return file.name || file.path || "";
}


function getExtension(file) {
  const full = getFullName(file);
  if (!full) return "";

  const name = full.split(/[\\/]/).pop();
  return name.includes('.') ? name.split('.').pop() : "";
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

export function pairFiles(files) {
  const map = new Map();

  for (const file of files) {
    if (!file) continue;

    const base = getBaseName(file);
    if (!base) continue;

    if (!map.has(base)) {
      map.set(base, {
        baseName: base,
        jpg: null,
        raw: null,
        files: []
      });
    }

    const record = map.get(base);
    record.files.push(file);

    if (isJpg(file)) {
      record.jpg = file;
    } else if (isRaw(file)) {
      record.raw = file;
    }
  }

  return Array.from(map.values());
}