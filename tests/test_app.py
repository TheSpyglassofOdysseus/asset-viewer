import os
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer.app import _run_isolated_worker, host_is_trusted, image_rows, make_thumbnail, origin_matches_host, serve
from asset_viewer.storage import add_collection


def sleeping_worker(seconds, sender):
    time.sleep(seconds)
    sender.send({"ok": True})
    sender.close()



class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ["ASSET_VIEWER_CACHE"] = str(Path(self.tmp.name) / "cache")
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()
        Image.new("RGB", (1200, 800), (20, 30, 40)).save(self.images / "sample.png")
        add_collection(str(self.images), "Samples")

    def tearDown(self):
        os.environ.pop("ASSET_VIEWER_HOME", None)
        os.environ.pop("ASSET_VIEWER_CACHE", None)
        self.tmp.cleanup()

    def test_gallery_includes_select_all_control(self):
        html = (Path(__file__).parents[1] / "asset_viewer" / "static" / "index.html").read_text()
        js = (Path(__file__).parents[1] / "asset_viewer" / "static" / "app.js").read_text()
        self.assertIn('id="selectAll"', html)
        self.assertIn("function selectAllVisible()", js)
        self.assertIn('id="reviewDecision"', html)
        self.assertIn("function renderReviewDecision(asset)", js)
        self.assertIn("decision-active", js)

    def test_image_discovery(self):
        rows = image_rows("samples")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "sample.png")
        self.assertEqual(rows[0]["width"], 1200)

    def test_thumbnail_generation(self):
        blob = make_thumbnail(self.images / "sample.png")
        self.assertGreater(len(blob), 100)

    def test_isolated_worker_timeout_fails_closed(self):
        payload = _run_isolated_worker(sleeping_worker, (1.0,), 0.05)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "worker timeout")

    def test_host_validation(self):
        trusted = {"127.0.0.1", "localhost", "::1", "gallery.example.com"}
        self.assertTrue(host_is_trusted("127.0.0.1:8160", trusted))
        self.assertTrue(host_is_trusted("gallery.example.com", trusted))
        self.assertFalse(host_is_trusted("attacker.example", trusted))
        self.assertFalse(host_is_trusted(None, trusted))

    def test_origin_validation(self):
        self.assertTrue(origin_matches_host("http://127.0.0.1:8160", "127.0.0.1:8160"))
        self.assertTrue(origin_matches_host("https://gallery.example.com", "gallery.example.com"))
        self.assertFalse(origin_matches_host("https://attacker.example", "gallery.example.com"))
        self.assertTrue(origin_matches_host(None, "gallery.example.com"))
        self.assertFalse(origin_matches_host("null", "gallery.example.com"))

    def test_non_loopback_bind_requires_trusted_host(self):
        with self.assertRaises(ValueError):
            serve("0.0.0.0", 0, [])

    def test_non_loopback_bind_requires_auth_or_explicit_boundary_override(self):
        with self.assertRaisesRegex(ValueError, "require ASSET_VIEWER_PASSWORD"):
            serve("0.0.0.0", 0, ["gallery.example.com"])


if __name__ == "__main__":
    unittest.main()
