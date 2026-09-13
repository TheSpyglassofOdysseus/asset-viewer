import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer.app import image_rows, make_thumbnail
from asset_viewer.storage import add_collection


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

    def test_image_discovery(self):
        rows = image_rows("samples")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "sample.png")
        self.assertEqual(rows[0]["width"], 1200)

    def test_thumbnail_generation(self):
        blob = make_thumbnail(self.images / "sample.png")
        self.assertGreater(len(blob), 100)


if __name__ == "__main__":
    unittest.main()
