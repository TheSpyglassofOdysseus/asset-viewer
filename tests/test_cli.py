import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer import storage


class CliWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("ASSET_VIEWER_HOME")
        self.old_cache = os.environ.get("ASSET_VIEWER_CACHE")
        self.env = os.environ.copy()
        self.env["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        self.env["ASSET_VIEWER_CACHE"] = str(Path(self.tmp.name) / "cache")
        os.environ["ASSET_VIEWER_HOME"] = self.env["ASSET_VIEWER_HOME"]
        os.environ["ASSET_VIEWER_CACHE"] = self.env["ASSET_VIEWER_CACHE"]
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()
        Image.new("RGB", (24, 24), (12, 34, 56)).save(self.images / "a.png")
        Image.new("RGB", (24, 24), (65, 43, 21)).save(self.images / "b.png")
        storage.add_collection(str(self.images), "Images")

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

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "asset_viewer", *args],
            cwd=Path(__file__).resolve().parents[1],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_pending_exit_code_and_completion(self):
        pending = self.run_cli("pending", "--collection", "images", "--json")
        self.assertEqual(pending.returncode, 2)
        payload = json.loads(pending.stdout)
        self.assertTrue(payload["pending"])
        storage.set_reviews_batch("images", ["a.png", "b.png"], "approved")
        complete = self.run_cli("complete", "images")
        self.assertEqual(complete.returncode, 0, complete.stderr)
        pending = self.run_cli("pending", "--collection", "images", "--json", "--no-scan")
        self.assertEqual(pending.returncode, 0)
        self.assertFalse(json.loads(pending.stdout)["pending"])

    def test_capabilities_json(self):
        result = self.run_cli("capabilities", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["protocol_version"], 1)
        self.assertTrue(payload["features"]["stable_asset_ids"])
        self.assertTrue(payload["features"]["event_feed"])

    def test_collection_url(self):
        result = self.run_cli("collection-url", "images", "--base-url", "https://viewer.example.test/base/")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "https://viewer.example.test/base/c/images")

    def test_asset_url_uses_stable_asset_id(self):
        from asset_viewer.app import scan_collection
        scan_collection("images", force=True)
        asset = storage.catalog_records("images")[0]
        result = self.run_cli("asset-url", "images", asset["rel"], "--base-url", "https://viewer.example.test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"https://viewer.example.test/c/images?asset={asset['asset_id']}")

    def test_events_and_wait_for_review_cli(self):
        storage.set_review("images", "a.png", "approved")
        events = self.run_cli("events", "--collection", "images", "--json")
        self.assertEqual(events.returncode, 0, events.stderr)
        payload = json.loads(events.stdout)
        self.assertEqual(payload["events"][0]["action"], "review")
        pending = self.run_cli("wait-for-review", "--collection", "images", "--timeout", "0", "--no-scan", "--json")
        self.assertEqual(pending.returncode, 2)
        storage.set_review("images", "b.png", "approved")
        storage.complete_collection_review("images")
        done = self.run_cli("wait-for-review", "--collection", "images", "--timeout", "0", "--no-scan", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse(json.loads(done.stdout)["pending"])

    def test_history_and_undo_cli(self):
        storage.set_review("images", "a.png", "maybe", comment="first")
        storage.set_review("images", "a.png", "approved", comment="second")
        history = self.run_cli("history", "images", "a.png", "--json")
        self.assertEqual(history.returncode, 0, history.stderr)
        self.assertEqual(len(json.loads(history.stdout)["events"]), 2)
        undo = self.run_cli("undo", "images", "a.png")
        self.assertEqual(undo.returncode, 0, undo.stderr)
        item = storage.review_manifest("images")["items"][0]
        self.assertEqual(item["status"], "maybe")
        self.assertEqual(item["comment"], "first")


if __name__ == "__main__":
    unittest.main()
