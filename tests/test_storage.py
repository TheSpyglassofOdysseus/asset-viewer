import os
import tempfile
import unittest
from pathlib import Path

from asset_viewer import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("ASSET_VIEWER_HOME")
        self.old_cache = os.environ.get("ASSET_VIEWER_CACHE")
        os.environ["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ["ASSET_VIEWER_CACHE"] = str(Path(self.tmp.name) / "cache")
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()

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

    def test_add_list_remove_collection(self):
        row = storage.add_collection(str(self.images), "My Images")
        self.assertEqual(row["slug"], "my-images")
        self.assertEqual(len(storage.collections()), 1)
        removed = storage.remove_collection("my-images")
        self.assertEqual(removed["label"], "My Images")
        self.assertEqual(storage.collections(), [])

    def test_safe_file_blocks_traversal(self):
        storage.add_collection(str(self.images), "Images")
        inside = self.images / "inside.png"
        inside.write_bytes(b"not-an-image")
        outside = Path(self.tmp.name) / "outside.txt"
        outside.write_text("secret")
        self.assertEqual(storage.safe_file("images", "inside.png"), inside.resolve())
        self.assertIsNone(storage.safe_file("images", "../outside.txt"))

    def test_review_round_trip(self):
        storage.add_collection(str(self.images), "Images")
        storage.set_review("images", "frame.png", "approved")
        self.assertEqual(storage.reviews()["images"]["frame.png"], "approved")
        storage.set_review("images", "frame.png", "")
        self.assertNotIn("frame.png", storage.reviews()["images"])


if __name__ == "__main__":
    unittest.main()
