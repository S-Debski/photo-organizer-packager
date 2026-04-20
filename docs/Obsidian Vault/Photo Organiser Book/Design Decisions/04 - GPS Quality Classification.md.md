---

type: design-decision

area: mapping

---

  

# GPS Quality Classification

  

This note documents how GPS data is classified and why.

  

---

  

## 🎯 Goal

  

Avoid false precision and clearly communicate GPS reliability to users.

  

---

  

## ✅ Classification Rules

  

### `none`

- No numeric GPSLatitude / GPSLongitude

- Common for cameras without GPS hardware

  

### `coarse`

- Coordinates exist but:

  - invalid refs (not N/S/E/W)

  - low precision

  - inferred or last‑known location

  

### `precise`

- Numeric lat/lon

- Valid refs (N/S/E/W)

- Reasonable coordinate range

  

---

  

## 📌 UX Mapping

  

| Quality | UX Behaviour |

|------|-------------|

| none | Informational message only |

| coarse | Map + warning |

| precise | Full interactive map |

  

---

  

## 📷 Real‑World Examples

  

- Sony NEX‑C3 → `none`

- Lumix TZ70 → `coarse` or `precise`

- Phones → usually `precise`

  

---

  

Related:

- [[Mapping & GPS Testing]]

``