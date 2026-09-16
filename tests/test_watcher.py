import os
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer import storage
from asset_viewer.watcher import CollectionWatcher


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("ASSET_VIEWER_HOME")
        os.environ["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()
        storage.add_collection(str(self.images), "Images")

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("ASSET_VIEWER_HOME", None)
        else:
            os.environ["ASSET_VIEWER_HOME"] = self.old_home
        self.tmp.cleanup()

    def test_read_only_open_does_not_request_reconciliation(self):
        image = self.images / "existing.png"
        Image.new("RGB", (20, 20), (4, 5, 6)).save(image)
        calls = []

        def scan(slug, force):
            calls.append((slug, force, time.monotonic()))

        watcher = CollectionWatcher(scan, debounce_seconds=0.1, reconcile_interval=3600, registry_interval=0.1)
        watcher.start()
        try:
            deadline = time.monotonic() + 3
            while not calls and time.monotonic() < deadline:
                time.sleep(0.05)
            calls.clear()  # discard the initial correctness reconciliation
            image.read_bytes()
            time.sleep(0.5)
            self.assertEqual(calls, [], "read-only file access triggered reconciliation")
        finally:
            watcher.stop()

    def test_filesystem_event_requests_reconciliation(self):
        calls = []

        def scan(slug, force):
            calls.append((slug, force, time.monotonic()))

        watcher = CollectionWatcher(scan, debounce_seconds=0.1, reconcile_interval=3600, registry_interval=0.1)
        watcher.start()
        try:
            deadline = time.monotonic() + 3
            while not calls and time.monotonic() < deadline:
                time.sleep(0.05)
            calls.clear()  # discard the initial correctness reconciliation
            Image.new("RGB", (20, 20), (1, 2, 3)).save(self.images / "new.png")
            deadline = time.monotonic() + 5
            while not calls and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(calls, "filesystem event did not trigger reconciliation")
            self.assertEqual(calls[-1][0], "images")
            self.assertTrue(calls[-1][1])
        finally:
            watcher.stop()


if __name__ == "__main__":
    unittest.main()
