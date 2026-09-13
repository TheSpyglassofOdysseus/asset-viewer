import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer import storage
from asset_viewer.app import scan_collection


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("ASSET_VIEWER_HOME")
        self.old_cache = os.environ.get("ASSET_VIEWER_CACHE")
        os.environ["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ["ASSET_VIEWER_CACHE"] = str(Path(self.tmp.name) / "cache")
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()
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

    def make_image(self, name, color=(10, 20, 30)):
        path = self.images / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 48), color).save(path)
        return path

    def test_force_scan_creates_stable_asset_metadata(self):
        self.make_image("a.png")
        rows, meta = scan_collection("images", force=True)
        self.assertEqual(len(rows), 1)
        self.assertFalse(meta["cached"])
        self.assertEqual(meta["generation"], 1)
        row = rows[0]
        self.assertTrue(row["asset_id"])
        self.assertEqual(row["width"], 64)
        record = storage.catalog_records("images")[0]
        self.assertEqual(record["asset_id"], row["asset_id"])
        self.assertGreater(record["inode"], 0)
        self.assertGreater(record["mtime_ns"], 0)

    def test_same_filesystem_rename_preserves_identity_review_and_history(self):
        original = self.make_image("before.png")
        rows, _ = scan_collection("images", force=True)
        asset_id = rows[0]["asset_id"]
        storage.set_review("images", "before.png", "approved", comment="keep this one")
        original.rename(self.images / "after.png")

        rows, _ = scan_collection("images", force=True)
        self.assertEqual([row["rel"] for row in rows], ["after.png"])
        self.assertEqual(rows[0]["asset_id"], asset_id)
        self.assertEqual(rows[0]["status"], "approved")
        self.assertEqual(rows[0]["comment"], "keep this one")
        history = storage.review_history("images", "after.png")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["asset_id"], asset_id)
        undone = storage.undo_last_review("images", "after.png")
        self.assertEqual(undone["asset_id"], asset_id)
        self.assertEqual(storage.review_manifest("images")["items"][0]["status"], "")

    def test_deleted_asset_is_tombstoned_and_remains_in_manifest(self):
        path = self.make_image("gone.png")
        rows, _ = scan_collection("images", force=True)
        asset_id = rows[0]["asset_id"]
        storage.set_review("images", "gone.png", "approved")
        path.unlink()

        rows, meta = scan_collection("images", force=True)
        self.assertEqual(rows, [])
        self.assertEqual(meta["generation"], 2)
        manifest = storage.review_manifest("images")
        self.assertEqual(len(manifest["items"]), 1)
        self.assertEqual(manifest["items"][0]["asset_id"], asset_id)
        self.assertFalse(manifest["items"][0]["present"])
        self.assertEqual(manifest["counts"]["present"], 0)
        self.assertEqual(manifest["counts"]["missing"], 1)

    def test_content_replacement_invalidates_prior_review(self):
        path = self.make_image("replace.png", (10, 20, 30))
        rows, _ = scan_collection("images", force=True)
        asset_id = rows[0]["asset_id"]
        storage.set_review("images", "replace.png", "approved", comment="old content")
        Image.new("RGB", (80, 48), (90, 80, 70)).save(path)

        rows, meta = scan_collection("images", force=True)
        self.assertEqual(rows[0]["asset_id"], asset_id)
        self.assertEqual(rows[0]["status"], "")
        self.assertEqual(rows[0]["comment"], "")
        self.assertTrue(rows[0]["is_new"])
        self.assertEqual(meta["changed"], 1)
        history = storage.review_history("images", "replace.png")
        self.assertEqual(history[0]["action"], "content_changed")
        self.assertEqual(history[0]["old_status"], "approved")
        # A filesystem content change is a system integrity event, not a user
        # review action: undo must never resurrect approval for changed bytes.
        undone = storage.undo_last_review("images", "replace.png")
        self.assertIsNone(undone)
        self.assertEqual(storage.review_manifest("images")["items"][0]["status"], "")

    def test_review_fingerprint_detects_same_size_same_mtime_replacement(self):
        path = self.images / "fingerprint.bmp"
        Image.new("RGB", (64, 48), (10, 20, 30)).save(path)
        scan_collection("images", force=True)
        storage.set_review("images", "fingerprint.bmp", "approved")
        before = path.stat()
        manifest = storage.review_manifest("images")
        self.assertRegex(manifest["items"][0]["review_sha256"], r"^[0-9a-f]{64}$")

        Image.new("RGB", (64, 48), (90, 80, 70)).save(path)
        after_write = path.stat()
        self.assertEqual(before.st_size, after_write.st_size)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)

        rows, meta = scan_collection("images", force=True)
        self.assertEqual(meta["changed"], 1)
        self.assertEqual(rows[0]["status"], "")
        self.assertIsNone(storage.review_manifest("images")["items"][0]["review_sha256"])
        event = next(e for e in storage.review_events_since("images")["events"] if e["action"] == "content_changed")
        self.assertTrue(event["details"]["review_hash_mismatch"])

    def test_completed_review_becomes_stale_when_asset_is_deleted(self):
        path = self.make_image("approved.png")
        scan_collection("images", force=True)
        storage.set_review("images", "approved.png", "approved")
        self.assertTrue(storage.complete_collection_review("images")["complete"])
        path.unlink()
        scan_collection("images", force=True)
        state = storage.collection_review_state("images")
        self.assertTrue(state["stale"])
        self.assertTrue(state["pending"])
        self.assertEqual(state["total"], 0)

    def test_truncated_scan_cannot_be_marked_complete(self):
        discoveries = [
            {"rel": "a.png", "device": 1, "inode": 101, "size": 1, "mtime_ns": 1, "width": 1, "height": 1, "preview_error": None}
        ]
        storage.reconcile_catalog("images", discoveries, truncated=True, reason="scan_file_limit", elapsed_ms=1)
        storage.set_review("images", "a.png", "approved")
        state = storage.collection_review_state("images")
        self.assertTrue(state["scan_incomplete"])
        with self.assertRaisesRegex(ValueError, "scan is incomplete"):
            storage.complete_collection_review("images")

    def test_scan_does_not_index_symlink_to_image_outside_root(self):
        outside = Path(self.tmp.name) / "outside.png"
        Image.new("RGB", (64, 48), (99, 1, 2)).save(outside)
        link = self.images / "escape.png"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        rows, _ = scan_collection("images", force=True)
        self.assertEqual(rows, [])
        self.assertEqual(storage.catalog_records("images"), [])

    def test_unavailable_collection_is_retained_and_blocks_completion(self):
        path = self.make_image("mounted.png")
        scan_collection("images", force=True)
        storage.set_review("images", "mounted.png", "approved")
        storage.complete_collection_review("images")
        path.unlink()
        self.images.rmdir()

        configured = storage.collections()[0]
        self.assertFalse(configured["available"])
        self.assertIsNone(storage.root_for("images"))
        rows, meta = scan_collection("images", force=True)
        self.assertEqual(len(rows), 1)
        self.assertTrue(meta["truncated"])
        self.assertEqual(meta["reason"], "collection_unavailable")
        state = storage.collection_review_state("images")
        self.assertTrue(state["scan_incomplete"])
        self.assertTrue(state["pending"])

    def test_event_feed_includes_filesystem_lifecycle(self):
        path = self.make_image("life.png")
        scan_collection("images", force=True)
        renamed = self.images / "renamed.png"
        path.rename(renamed)
        scan_collection("images", force=True)
        Image.new("RGB", (80, 48), (40, 50, 60)).save(renamed)
        scan_collection("images", force=True)
        renamed.unlink()
        scan_collection("images", force=True)
        Image.new("RGB", (80, 48), (40, 50, 60)).save(renamed)
        scan_collection("images", force=True)

        feed = storage.review_events_since("images")
        actions = [event["action"] for event in feed["events"]]
        self.assertEqual(actions[:5], [
            "asset_added", "asset_renamed", "content_changed", "asset_missing", "asset_restored"
        ])
        rename = next(event for event in feed["events"] if event["action"] == "asset_renamed")
        self.assertEqual(rename["details"]["old_rel"], "life.png")
        self.assertEqual(rename["details"]["new_rel"], "renamed.png")

    def test_cached_gallery_read_does_not_discover_new_file_until_forced(self):
        self.make_image("a.png")
        first, first_meta = scan_collection("images", force=True)
        self.assertEqual(len(first), 1)
        self.make_image("b.png", (40, 50, 60))

        cached, cached_meta = scan_collection("images")
        self.assertEqual(len(cached), 1)
        self.assertTrue(cached_meta["cached"])
        self.assertEqual(cached_meta["generation"], first_meta["generation"])

        refreshed, refreshed_meta = scan_collection("images", force=True)
        self.assertEqual(len(refreshed), 2)
        self.assertFalse(refreshed_meta["cached"])
        self.assertEqual(refreshed_meta["generation"], first_meta["generation"] + 1)

    def test_truncated_reconcile_never_marks_unvisited_assets_missing(self):
        first = [
            {"rel": "a.png", "device": 1, "inode": 101, "size": 1, "mtime_ns": 1, "width": 1, "height": 1, "preview_error": None},
            {"rel": "b.png", "device": 1, "inode": 102, "size": 1, "mtime_ns": 1, "width": 1, "height": 1, "preview_error": None},
        ]
        storage.reconcile_catalog("images", first, truncated=False, reason=None, elapsed_ms=1)
        storage.reconcile_catalog("images", first[:1], truncated=True, reason="scan_file_limit", elapsed_ms=1)
        self.assertEqual(len(storage.catalog_records("images", present_only=True)), 2)
        storage.reconcile_catalog("images", first[:1], truncated=False, reason=None, elapsed_ms=1)
        self.assertEqual([row["rel"] for row in storage.catalog_records("images", present_only=True)], ["a.png"])
        missing = next(row for row in storage.catalog_records("images", present_only=False) if row["rel"] == "b.png")
        self.assertFalse(missing["present"])

    def test_spatial_annotations_follow_stable_identity_across_rename(self):
        path = self.make_image("annotated.png")
        rows, _ = scan_collection("images", force=True)
        asset_id = rows[0]["asset_id"]
        point = storage.create_annotation(
            "images", asset_id, "point", 0.25, 0.4, text="Move the mark left"
        )
        self.assertRegex(point["content_sha256"], r"^[0-9a-f]{64}$")
        region = storage.create_annotation(
            "images", asset_id, "region", 0.5, 0.2, w=0.3, h=0.4, text="Reduce this block"
        )
        self.assertEqual(point["kind"], "point")
        self.assertEqual(region["kind"], "region")
        self.assertEqual(len(storage.annotations_for_asset("images", asset_id)), 2)

        path.rename(self.images / "renamed.png")
        rows, _ = scan_collection("images", force=True)
        self.assertEqual(rows[0]["asset_id"], asset_id)
        annotations = storage.annotations_for_asset("images", asset_id)
        self.assertEqual([item["text"] for item in annotations], ["Move the mark left", "Reduce this block"])
        self.assertFalse(any(item["stale"] for item in annotations))

    def test_content_change_marks_spatial_annotations_stale(self):
        path = self.make_image("stale.png")
        rows, _ = scan_collection("images", force=True)
        asset_id = rows[0]["asset_id"]
        annotation = storage.create_annotation("images", asset_id, "point", 0.5, 0.5, text="Original detail")
        Image.new("RGB", (80, 48), (99, 88, 77)).save(path)
        scan_collection("images", force=True)
        refreshed = storage.annotations_for_asset("images", asset_id)
        self.assertEqual(refreshed[0]["annotation_id"], annotation["annotation_id"])
        self.assertTrue(refreshed[0]["stale"])
        manifest = storage.review_manifest("images")
        self.assertTrue(manifest["items"][0]["annotations"][0]["stale"])

    def test_annotation_fingerprint_detects_same_size_same_mtime_replacement(self):
        path = self.images / "annotation-fingerprint.bmp"
        Image.new("RGB", (64, 48), (10, 20, 30)).save(path)
        rows, _ = scan_collection("images", force=True)
        asset_id = rows[0]["asset_id"]
        created = storage.create_annotation("images", asset_id, "point", 0.4, 0.5, text="This exact pixel area")
        before = path.stat()

        Image.new("RGB", (64, 48), (90, 80, 70)).save(path)
        self.assertEqual(before.st_size, path.stat().st_size)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        rows, meta = scan_collection("images", force=True)
        self.assertEqual(meta["changed"], 1)
        annotations = storage.annotations_for_asset("images", asset_id)
        self.assertEqual(annotations[0]["annotation_id"], created["annotation_id"])
        self.assertTrue(annotations[0]["stale"])
        event = next(e for e in storage.review_events_since("images")["events"] if e["action"] == "content_changed")
        self.assertTrue(event["details"]["annotation_hash_mismatch"])

    def test_annotation_update_delete_and_validation(self):
        self.make_image("notes.png")
        rows, _ = scan_collection("images", force=True)
        asset_id = rows[0]["asset_id"]
        with self.assertRaisesRegex(ValueError, "outside"):
            storage.create_annotation("images", asset_id, "region", 0.9, 0.9, w=0.2, h=0.2)
        created = storage.create_annotation("images", asset_id, "point", 0.1, 0.2, text="first")
        updated = storage.update_annotation("images", created["annotation_id"], text="done", resolved=True)
        self.assertEqual(updated["text"], "done")
        self.assertTrue(updated["resolved"])
        events = storage.review_events_since("images")["events"]
        self.assertIn("annotation_created", [event["action"] for event in events])
        self.assertIn("annotation_updated", [event["action"] for event in events])
        deleted = storage.delete_annotation("images", created["annotation_id"])
        self.assertEqual(deleted["annotation_id"], created["annotation_id"])
        self.assertEqual(storage.annotations_for_asset("images", asset_id), [])

    def test_catalog_handles_large_synthetic_collection_without_path_scans(self):
        discoveries = [
            {"rel": f"frames/{i:04d}.png", "device": 1, "inode": 1000 + i, "size": 2048 + i, "mtime_ns": 1_000_000 + i, "width": 1024, "height": 768, "preview_error": None}
            for i in range(1000)
        ]
        storage.reconcile_catalog("images", discoveries, truncated=False, reason=None, elapsed_ms=12)
        rows = storage.catalog_records("images")
        self.assertEqual(len(rows), 1000)
        self.assertEqual(len({row["asset_id"] for row in rows}), 1000)
        self.assertEqual(storage.catalog_state("images")["generation"], 1)


class CatalogMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("ASSET_VIEWER_HOME")
        self.old_cache = os.environ.get("ASSET_VIEWER_CACHE")
        os.environ["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ["ASSET_VIEWER_CACHE"] = str(Path(self.tmp.name) / "cache")
        Path(os.environ["ASSET_VIEWER_HOME"]).mkdir(parents=True)
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()
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

    def test_v03_assets_schema_migrates_in_place(self):
        db = storage.database_path()
        conn = sqlite3.connect(db)
        conn.execute(
            """
            CREATE TABLE assets (
                collection TEXT NOT NULL,
                rel TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '',
                comment TEXT NOT NULL DEFAULT '',
                first_seen_at TEXT NOT NULL,
                seen_at TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (collection, rel)
            )
            """
        )
        conn.execute(
            "INSERT INTO assets VALUES('images','legacy.png','approved','legacy note','2026-01-01','2026-01-02','2026-01-03')"
        )
        conn.commit()
        conn.close()

        records = storage.catalog_records("images", present_only=False)
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["asset_id"])
        self.assertEqual(records[0]["status"], "approved")
        self.assertEqual(records[0]["comment"], "legacy note")
        self.assertTrue(records[0]["present"])


if __name__ == "__main__":
    unittest.main()
