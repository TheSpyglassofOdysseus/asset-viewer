import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer import storage
from asset_viewer.app import scan_collection
from asset_viewer.report import render_review_report


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("ASSET_VIEWER_HOME")
        self.old_cache = os.environ.get("ASSET_VIEWER_CACHE")
        os.environ["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ["ASSET_VIEWER_CACHE"] = str(Path(self.tmp.name) / "cache")
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()
        Image.new("RGB", (40, 30), (12, 34, 56)).save(self.images / "one.png")
        storage.add_collection(str(self.images), "Images")
        scan_collection("images", force=True)
        storage.set_review("images", "one.png", "approved", comment="Ship <this> version")

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("ASSET_VIEWER_HOME", None)
        else:
            os.environ["ASSET_VIEWER_HOME"] = self.old_home
        if self.old_cache is None:
            os.environ.pop("ASSET_VIEWER_CACHE", None)
        else:
            os.environ["ASSET_VIEWER_CACHE"] = self.old_cache
        self.tmp.cleanup()

    def test_markdown_report_contains_human_summary(self):
        report = render_review_report(storage.review_manifest("images"), format="markdown")
        self.assertIn("# Asset Viewer Review Report", report)
        self.assertIn("Approved: 1", report)
        self.assertIn("one.png — Approved", report)
        self.assertIn("Ship <this> version", report)

    def test_html_report_escapes_review_text(self):
        report = render_review_report(storage.review_manifest("images"), format="html", embed_images=False)
        self.assertIn("Approved", report)
        self.assertIn("Ship &lt;this&gt; version", report)
        self.assertNotIn("Ship <this> version", report)
        self.assertIn("@media print", report)


if __name__ == "__main__":
    unittest.main()
