import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from asset_viewer import storage
from asset_viewer.activity import activity_feed
import asset_viewer.handoff as handoff_module
from asset_viewer.handoff import approved_handoff, copy_approved_set


class V08ContextHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("ASSET_VIEWER_HOME")
        self.old_cache = os.environ.get("ASSET_VIEWER_CACHE")
        os.environ["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ["ASSET_VIEWER_CACHE"] = str(Path(self.tmp.name) / "cache")
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()
        (self.images / "concept.png").write_bytes(b"asset-viewer-v08")
        storage.add_collection(str(self.images), "Concepts", group="Whetstone / Brand")
        storage.ensure_assets("concepts", ["concept.png"])

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

    def test_collection_group_is_navigation_metadata_only(self):
        rows = storage.collections()
        self.assertEqual(rows[0]["group"], "Whetstone / Brand")
        self.assertEqual(Path(rows[0]["path"]), self.images.resolve())

    def test_provenance_round_trip_and_partial_update(self):
        metadata = storage.set_asset_metadata("concepts", "concept.png", {
            "source_project": "Whetstone",
            "tool": "imagegen",
            "model": "gpt-image",
            "prompt": "A restrained primary logo",
            "run_id": "brand-007",
            "extra": {"brief": "primary-mark"},
        })
        self.assertEqual(metadata["source_project"], "Whetstone")
        updated = storage.set_asset_metadata("concepts", metadata["asset_id"], {"seed": "42"})
        self.assertEqual(updated["prompt"], "A restrained primary logo")
        self.assertEqual(updated["seed"], "42")
        self.assertEqual(updated["extra"], {"brief": "primary-mark"})
        item = storage.review_manifest("concepts")["items"][0]
        self.assertEqual(item["provenance"]["run_id"], "brand-007")

    def test_activity_reuses_durable_event_stream(self):
        storage.set_asset_metadata("concepts", "concept.png", {"model": "gpt-image"})
        storage.set_review("concepts", "concept.png", "maybe", comment="Keep composition")
        payload = activity_feed("concepts")
        summaries = [event["summary"] for event in payload["events"]]
        self.assertTrue(any("Provenance updated" in summary for summary in summaries))
        self.assertTrue(any("unreviewed → maybe" in summary for summary in summaries))

    def test_activity_default_returns_newest_slice(self):
        for index in range(8):
            storage.set_asset_metadata("concepts", "concept.png", {"run_id": f"run-{index}"})
        payload = activity_feed("concepts", limit=3)
        self.assertEqual([event["id"] for event in payload["events"]], [6, 7, 8])
        self.assertEqual(payload["last_event_id"], 8)

    def test_approved_handoff_is_exact_and_non_destructive(self):
        storage.set_asset_metadata("concepts", "concept.png", {"agent": "designer", "run_id": "r-8"})
        storage.set_review("concepts", "concept.png", "approved", comment="Use this one")
        payload = approved_handoff("concepts")
        self.assertEqual(payload["count"], 1)
        item = payload["items"][0]
        self.assertNotIn("source_root", payload)
        self.assertNotIn("source_path", item)
        self.assertNotIn(str(self.images.resolve()), str(payload))
        self.assertEqual(item["rel"], "concept.png")
        self.assertEqual(item["comment"], "Use this one")
        self.assertEqual(item["provenance"]["agent"], "designer")
        self.assertTrue(item["sha256"])
        destination = Path(self.tmp.name) / "approved"
        copied = copy_approved_set("concepts", str(destination))
        self.assertEqual(copied["copied"], ["concept.png"])
        self.assertEqual((destination / "concept.png").read_bytes(), b"asset-viewer-v08")
        self.assertEqual((self.images / "concept.png").read_bytes(), b"asset-viewer-v08")

    def test_handoff_fails_closed_if_approved_bytes_change(self):
        storage.set_review("concepts", "concept.png", "approved")
        (self.images / "concept.png").write_bytes(b"changed-after-review")
        with self.assertRaisesRegex(ValueError, "bytes changed since review"):
            approved_handoff("concepts")

    def test_copy_handoff_reverifies_bytes_while_copying(self):
        storage.set_review("concepts", "concept.png", "approved")
        real_handoff = handoff_module.approved_handoff

        def mutate_after_manifest(collection):
            payload = real_handoff(collection)
            (self.images / "concept.png").write_bytes(b"changed-after-manifest")
            return payload

        destination = Path(self.tmp.name) / "race-copy"
        with mock.patch("asset_viewer.handoff.approved_handoff", side_effect=mutate_after_manifest):
            with self.assertRaisesRegex(ValueError, "bytes changed during handoff"):
                copy_approved_set("concepts", str(destination))
        self.assertFalse((destination / "concept.png").exists())


if __name__ == "__main__":
    unittest.main()
