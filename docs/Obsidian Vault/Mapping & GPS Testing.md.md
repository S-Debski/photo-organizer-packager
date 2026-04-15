---

type: testing

scope: mapping

---

  

# Mapping & GPS Testing

  

This note captures **expected Mapping behaviour** across different camera types and GPS qualities.

  

---

  

## 📷 Cameras Tested

  

- Sony NEX‑C3 — no GPS

- Panasonic Lumix TZ70 — mixed GPS

- (Planned) Modern GPS‑enabled camera / phone

  

---

  

## ✅ Expected Behaviour

  

### No GPS (`quality: none`)

- Show informational message

- No precise markers

- Map is optional context only

  

### Coarse GPS (`quality: coarse`)

- Show map with warning

- Broad region‑level view

- No implication of street accuracy

  

### Precise GPS (`quality: precise`)

- Tight clustering

- Fit bounds to points

- Street‑level zoom possible

  

---

  

## 🧪 Tests to Run

  

- [ ] Folder with only non‑GPS photos

- [ ] Folder with mixed GPS quality

- [ ] Folder with fully precise GPS

- [ ] Switching folders updates map correctly

  

---

  

Related:

- [[GPS Quality Classification]]

- [[Why Mapping Is Informational]]