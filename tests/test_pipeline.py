# Role: Test suite (see Stability Contract)
"""
End-to-end checks for the ingest pipeline: EXIF scan, sessions/culling,
import, GPS write-back and thumbnails.

    python -m unittest discover -s tests -v

Builds a throwaway "card" (DCIM/100TEST with JPG/RAW pairs) in a temp
folder. Tests that need ExifTool are skipped when it is not installed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from photo_core.ctx.context import AppContext  # noqa: E402
from photo_core.exif.reader import resolve_exiftool_cmd, NO_WINDOW  # noqa: E402
import backend.api_server as srv  # noqa: E402

EXIFTOOL = resolve_exiftool_cmd()
needs_exiftool = unittest.skipUnless(EXIFTOOL, "ExifTool not installed")


def _exiftool(*args):
    return subprocess.run([EXIFTOOL, *args], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)


def make_card(root: Path) -> Path:
    """DCIM/100TEST: 0001 RAW+JPG (GPS), 0002 RAW+JPG, 0003 JPG, 0004 RAW only."""
    src = root / "card" / "DCIM" / "100TEST"
    src.mkdir(parents=True)
    for i, colour in enumerate(["red", "green", "blue"], start=1):
        Image.new("RGB", (1200, 800), colour).save(src / f"DSCF000{i}.JPG", quality=90)
    # Stand-in RAWs: copies of JPEGs (exiftool reads them; previews come
    # from the embedded-preview path, which fails cleanly)
    shutil.copy(src / "DSCF0001.JPG", src / "DSCF0001.RAF")
    shutil.copy(src / "DSCF0002.JPG", src / "DSCF0002.RAF")
    shutil.copy(src / "DSCF0003.JPG", src / "DSCF0004.RAF")
    (src / "DSCF0001.RAF.xmp").write_text("<x:xmpmeta/>")
    if EXIFTOOL:
        _exiftool("-q", "-overwrite_original", "-Make=FUJIFILM", "-Model=X-T5",
                  "-DateTimeOriginal=2026:06:01 10:00:00", "-GPSLatitude=54.9783",
                  "-GPSLatitudeRef=N", "-GPSLongitude=1.6178",
                  "-GPSLongitudeRef=W", str(src / "DSCF0001.JPG"))
    return src


class PipelineTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="po-test-"))
        cls.src = make_card(cls.tmp)
        cls.ctx = AppContext()
        cls.ctx.cache_dir = str(cls.tmp / "cache")
        cls.ctx.sessions_root = str(cls.tmp / "sessions")
        os.makedirs(cls.ctx.sessions_root)
        srv.ctx = cls.ctx
        cls.ctx.state.update(current_sd_root=str(cls.tmp / "card"),
                             current_active_folder=str(cls.src),
                             copy_complete=True)
        cls.client = srv.app.test_client()
        cls.src_bytes = {p: p.read_bytes() for p in cls.src.iterdir()}

    @classmethod
    def tearDownClass(cls):
        cls.ctx.shutdown_event.set()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def post(self, url, **body):
        return self.client.post(url, json=body).get_json()

    # -- EXIF scan ------------------------------------------------------------

    @needs_exiftool
    def test_01_scanner_produces_records_with_gps(self):
        from workers.exif_scanner import exif_scanner_worker
        threading.Thread(target=exif_scanner_worker, args=(self.ctx,),
                         daemon=True).start()
        for _ in range(60):
            if self.ctx.state.get("exif_records"):
                break
            time.sleep(0.25)
        records = {Path(r["path"]).name: r for r in self.ctx.state.get("exif_records", [])}
        self.assertEqual(len(records), 6, "every JPG/RAW should produce a record")
        rec = records["DSCF0001.JPG"]
        self.assertEqual(rec["camera_model"], "FUJIFILM X-T5")
        self.assertAlmostEqual(rec["gps"][0], 54.9783, places=4)
        self.assertAlmostEqual(rec["gps"][1], -1.6178, places=4)

        gps = self.post("/api/gps-data")
        self.assertEqual([Path(p["path"]).name for p in gps["points"]], ["DSCF0001.JPG"])

    def test_02_analyze_card(self):
        r = self.post("/api/analyze-card", sd_card_path=str(self.tmp / "card") + os.sep)
        folders = r["analysis"]["folders"]
        self.assertEqual([f["name"] for f in folders], ["100TEST"])
        self.assertEqual(r["analysis"]["counts"], {"total": 6, "raw": 3, "jpg": 3})

    def test_04_plain_folder_without_dcim(self):
        # e.g. a folder on a NAS: photos directly inside, plus a sub-folder
        plain = self.tmp / "Exports" / "Wylam ride"
        (plain / "picks").mkdir(parents=True)
        Image.new("RGB", (400, 300), "red").save(plain / "A.JPG")
        Image.new("RGB", (400, 300), "blue").save(plain / "picks" / "B.JPG")
        r = self.post("/api/analyze-card", sd_card_path=str(plain))
        names = [f["name"] for f in r["analysis"]["folders"]]
        self.assertEqual(names, ["Wylam ride", "picks"])

    def test_03_analyze_empty_card(self):
        empty = self.tmp / "empty"
        (empty / "DCIM").mkdir(parents=True)
        r = self.post("/api/analyze-card", sd_card_path=str(empty) + os.sep)
        self.assertEqual(r["analysis"]["counts"]["total"], 0)

    # -- Sessions / culling ---------------------------------------------------

    def test_10_session_cull_and_resume(self):
        r = self.post("/api/session/create", source_folder=str(self.src), session_name="100TEST")
        self.assertTrue(r["success"])
        self.assertEqual(self.client.get("/api/session/status").get_json()["total_assets"], 4)

        self.post("/api/session/select", asset_id="DSCF0001", decision="keep")
        self.post("/api/session/select", asset_id="DSCF0002", decision="reject")
        self.post("/api/session/select", asset_id="DSCF0004", decision="keep")
        self.post("/api/session/select", asset_id="DSCF0004", decision=None)

        self.post("/api/session/close")
        r = self.post("/api/session/create", source_folder=str(self.src), session_name="100TEST")
        self.assertTrue(r["resumed"])
        self.assertEqual(r["decisions"], {"DSCF0001": "keep", "DSCF0002": "reject"})
        st = self.client.get("/api/session/status").get_json()
        self.assertEqual((st["selected"], st["rejected"], st["unculled"]), (1, 1, 2))

    def test_11_new_card_in_same_slot_starts_fresh(self):
        slot = self.tmp / "slot" / "DCIM" / "100_FUJI"
        slot.mkdir(parents=True)

        def insert_card(colour, size):
            for p in slot.iterdir():
                p.unlink()
            for i in (1, 2, 3):
                Image.new("RGB", size, colour).save(slot / f"DSCF000{i}.JPG", quality=90)

        insert_card("red", (800, 600))
        self.post("/api/session/create", source_folder=str(slot), session_name="100_FUJI")
        self.post("/api/session/select", asset_id="DSCF0001", decision="reject")
        self.post("/api/locations", folders=[str(slot)], lat=54.9, lon=-1.8)

        # Same card again → resumes, location still there
        self.post("/api/session/close")
        again = self.post("/api/session/create", source_folder=str(slot), session_name="100_FUJI")
        self.assertTrue(again["resumed"])
        self.assertEqual(again["decisions"], {"DSCF0001": "reject"})

        # Different card, same path and names, different photos → fresh
        insert_card("blue", (1600, 1200))
        self.post("/api/session/close")
        other = self.post("/api/session/create", source_folder=str(slot), session_name="100_FUJI")
        self.assertFalse(other["resumed"])
        self.assertEqual(other["decisions"], {})
        locs = self.client.get("/api/locations", query_string={"folder": str(slot)}).get_json()
        self.assertEqual(locs["locations"], {})
        self.post("/api/session/close")

    # -- Import ---------------------------------------------------------------

    def test_20_kept_import_needs_keepers(self):
        r = self.post("/api/organize", source=str(self.src),
                      destination=str(self.tmp / "dest-empty"), mode="kept", kept_paths=[])
        self.assertFalse(r["success"])

    @needs_exiftool
    def test_21_kept_import_with_partners_and_gps(self):
        dest = self.tmp / "dest"
        r = self.post("/api/organize", source=str(self.src), destination=str(dest),
                      mode="kept", kept_paths=[str(self.src / "DSCF0002.JPG")],
                      gps=[{"path": str(self.src / "DSCF0002.JPG"), "lat": 51.5, "lon": -0.12}])
        self.assertTrue(r["success"], r)
        out = sorted(os.listdir(r["destination"]))
        self.assertEqual(out, ["DSCF0002.JPG", "DSCF0002.RAF"])
        self.assertEqual(r["gps_written"], 1)

        tags = json.loads(_exiftool("-json", "-n", "-G1", "-GPS:all",
                                    os.path.join(r["destination"], "DSCF0002.JPG")).stdout)[0]
        self.assertEqual(tags["GPS:GPSLongitudeRef"], "W")
        self.assertAlmostEqual(tags["GPS:GPSLongitude"], 0.12)

    def test_22_import_all_skips_existing(self):
        dest = self.tmp / "dest-all"
        first = self.post("/api/organize", source=str(self.src), destination=str(dest), mode="all")
        again = self.post("/api/organize", source=str(self.src), destination=str(dest), mode="all")
        self.assertEqual(first["count"], 7)   # 6 images + .xmp sidecar
        self.assertEqual((again["count"], again["skipped"]), (0, 7))

    def test_23_write_gps_never_touches_source(self):
        r = self.post("/api/write-gps", files=[str(self.src / "DSCF0003.JPG")], lat=1, lon=2)
        self.assertEqual((r["deferred"], r["updated"]), (1, 0))

    # -- Shoot title / folder layout (design 08/09) ------------------------------

    def test_24_preview_matches_import_folder(self):
        dest = self.tmp / "library"
        body = dict(source=str(self.src), destination=str(dest), title="Wylam: Bike/Ride",
                    shoot_date="2026-10-10", template="{YYYY}/{MM}/{DD} - {title}")
        preview = self.post("/api/pre-import/preview", **body)
        self.assertTrue(preview["success"], preview)
        expected = dest / "2026" / "10" / "10 - Wylam- Bike-Ride"   # title sanitised
        self.assertEqual(Path(preview["path"]), expected)
        self.assertFalse(dest.exists(), "preview must not create folders")

        r = self.post("/api/organize", mode="kept",
                      kept_paths=[str(self.src / "DSCF0003.JPG")], **body)
        self.assertTrue(r["success"], r)
        self.assertEqual(Path(r["destination"]), expected)

    def test_25_destination_inside_source_is_refused(self):
        inside = self.src / "export"
        r = self.post("/api/organize", source=str(self.src), destination=str(inside),
                      mode="all", title="Test", shoot_date="2026-10-10")
        self.assertFalse(r["success"])
        self.assertFalse(inside.exists(), "nothing may be created on refusal")

    @needs_exiftool
    def test_26_location_goes_to_every_copy(self):
        dest = self.tmp / "dest-loc"
        r = self.post("/api/organize", source=str(self.src), destination=str(dest),
                      mode="kept", kept_paths=[str(self.src / "DSCF0002.JPG"),
                                               str(self.src / "DSCF0004.RAF")],
                      location={"lat": 54.9616, "lon": -1.8617})
        self.assertTrue(r["success"], r)
        self.assertEqual((r["gps_written"], r["sidecars_written"]), (1, 2))
        out = Path(r["destination"])
        for name in ("DSCF0002.xmp", "DSCF0004.xmp"):
            pos = _exiftool("-n", "-s3", "-Composite:GPSPosition", str(out / name)).stdout.split()
            self.assertAlmostEqual(float(pos[1]), -1.8617, places=4, msg=name)
        self.assertFalse(any(p.suffix == ".part" for p in out.iterdir()))

    def test_27_same_name_different_file_is_not_overwritten(self):
        dest = self.tmp / "dest-conflict"
        first = self.post("/api/organize", source=str(self.src), destination=str(dest), mode="all")
        victim = Path(first["destination"]) / "DSCF0003.JPG"
        victim.write_bytes(b"a different photo with the same name")
        again = self.post("/api/organize", source=str(self.src), destination=str(dest), mode="all")
        self.assertEqual(again["conflicts"], ["DSCF0003.JPG"])
        self.assertFalse(again["all_copied"])
        self.assertEqual(victim.read_bytes(), b"a different photo with the same name")

    def test_29_saved_places(self):
        first = self.client.get("/api/places").get_json()["places"]
        self.assertIn("Butley Village Hall", [p["name"] for p in first])

        self.post("/api/places", name="Wylam Station", lat=54.9757, lon=-1.8206)
        self.post("/api/places", name="wylam station", lat=54.9760, lon=-1.8210)  # replace, any case
        places = self.client.get("/api/places").get_json()["places"]
        wylam = [p for p in places if p["name"].lower() == "wylam station"]
        self.assertEqual(len(wylam), 1)
        self.assertAlmostEqual(wylam[0]["lat"], 54.9760)

        self.post("/api/places", name="Wylam Station", delete=True)
        names = [p["name"] for p in self.client.get("/api/places").get_json()["places"]]
        self.assertNotIn("Wylam Station", names)
        self.assertIn("Butley Village Hall", names)

    def test_28_locations_survive_restart(self):
        folder = str(self.src)
        self.post("/api/locations", folders=[folder], lat=54.96, lon=-1.86)
        got = self.client.get("/api/locations", query_string={"folder": folder}).get_json()
        self.assertEqual(got["locations"][folder], {"lat": 54.96, "lon": -1.86})
        self.assertTrue(os.path.isfile(os.path.join(self.ctx.sessions_root, "locations.json")))
        self.post("/api/locations", folders=[folder], clear=True)
        got = self.client.get("/api/locations", query_string={"folder": folder}).get_json()
        self.assertEqual(got["locations"], {})

    # -- Send to Pixel (stand-in adb) ------------------------------------------

    def _fake_adb(self):
        phone = self.tmp / "phone"
        phone.mkdir(exist_ok=True)
        helper = Path(__file__).with_name("fake_adb.py")
        if os.name == "nt":
            wrapper = self.tmp / "adb.cmd"
            wrapper.write_text(f'@"{sys.executable}" "{helper}" %*\r\n')
        else:
            wrapper = self.tmp / "adb"
            wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{helper}" "$@"\n')
            wrapper.chmod(0o755)
        os.environ["PHOTO_ORGANIZER_ADB"] = str(wrapper)
        os.environ["FAKE_PHONE_ROOT"] = str(phone)
        return phone

    def test_40_pixel_send(self):
        from photo_core.export import pixel
        phone = self._fake_adb()
        try:
            status = self.client.get("/api/pixel/status").get_json()
            self.assertEqual([(d["model"], d["state"]) for d in status["devices"]],
                             [("Pixel XL", "device")])

            shoot = self.tmp / "shoot"
            shoot.mkdir()
            shutil.copy(self.src / "DSCF0001.JPG", shoot / "DSCF0001.JPG")
            shutil.copy(self.src / "DSCF0002.JPG", shoot / "DSCF0002.JPG")
            shutil.copy(self.src / "DSCF0001.RAF", shoot / "DSCF0001.RAF")
            adb = pixel.resolve_adb()

            first = pixel.send_folder(adb, "FA6AX0301234", str(shoot))       # JPG only
            on_phone = phone / "sdcard" / "DCIM" / "PhotoOrganizer"
            self.assertEqual((first["sent"], first["skipped"]), (2, 0))
            self.assertEqual(sorted(os.listdir(on_phone)), ["DSCF0001.JPG", "DSCF0002.JPG"])

            again = pixel.send_folder(adb, "FA6AX0301234", str(shoot))
            self.assertEqual((again["sent"], again["skipped"]), (0, 2), "re-sending must not duplicate")

            other = self.tmp / "other-card"
            other.mkdir()
            shutil.copy(self.src / "DSCF0003.JPG", other / "DSCF0001.JPG")    # same name, other photo
            clash = pixel.send_folder(adb, "FA6AX0301234", str(other))
            self.assertEqual(clash["sent"], 1)
            self.assertIn("DSCF0001_2.JPG", os.listdir(on_phone))
            self.assertEqual((on_phone / "DSCF0001.JPG").read_bytes(), (shoot / "DSCF0001.JPG").read_bytes())

            scans = (phone / "scans.log").read_text().split()
            self.assertEqual(len(scans), 3)
            self.assertTrue(all(s.startswith("file:///sdcard/DCIM/PhotoOrganizer/") for s in scans))
        finally:
            os.environ.pop("PHOTO_ORGANIZER_ADB", None)

    # -- Thumbnails -----------------------------------------------------------

    def test_30_thumbnail_is_small_and_cached(self):
        url = f"/api/thumb?path={self.src / 'DSCF0003.JPG'}&size=grid"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        im = Image.open(__import__("io").BytesIO(r.data))
        self.assertLessEqual(max(im.size), 320)
        cached = os.listdir(os.path.join(self.ctx.cache_dir, "thumbs"))
        self.assertEqual(len(cached), 1)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(len(os.listdir(os.path.join(self.ctx.cache_dir, "thumbs"))), 1)

    def test_31_thumbs_list_is_not_capped(self):
        files = self.client.post("/api/thumbs", json={"folder": str(self.src)}).get_json()
        self.assertEqual(len(files), 6)

    # -- Safety ---------------------------------------------------------------

    def test_90_source_card_unchanged(self):
        now = {p: p.read_bytes() for p in self.src.iterdir()}
        self.assertEqual(now, self.src_bytes)

    def test_91_no_cors_headers(self):
        r = self.client.get("/api/session/status", headers={"Origin": "https://evil.example"})
        self.assertNotIn("Access-Control-Allow-Origin", r.headers)


if __name__ == "__main__":
    unittest.main()
