import asyncio
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer import storage
from asset_viewer.app import scan_collection
from asset_viewer import mcp_server


class McpAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("ASSET_VIEWER_HOME")
        os.environ["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()
        Image.new("RGB", (30, 30), (9, 8, 7)).save(self.images / "asset.png")
        storage.add_collection(str(self.images), "Images")
        scan_collection("images", force=True)
        storage.set_review("images", "asset.png", "maybe", comment="Try one more pass")

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("ASSET_VIEWER_HOME", None)
        else:
            os.environ["ASSET_VIEWER_HOME"] = self.old_home
        self.tmp.cleanup()

    def test_read_only_protocol_tools_reuse_existing_review_contract(self):
        collections = mcp_server.list_collections()
        self.assertEqual(collections["collections"][0]["slug"], "images")
        reviews = mcp_server.get_reviews("images")
        self.assertEqual(reviews["items"][0]["status"], "maybe")
        self.assertEqual(reviews["items"][0]["comment"], "Try one more pass")
        pending = mcp_server.get_pending("images")
        self.assertTrue(pending["pending"])
        self.assertIn("?asset=", mcp_server.get_asset_url("images", "asset.png"))
        provenance = mcp_server.set_provenance("images", "asset.png", model="gpt-image", run_id="mcp-08")
        self.assertEqual(provenance["run_id"], "mcp-08")
        self.assertEqual(mcp_server.get_provenance("images", "asset.png")["model"], "gpt-image")
        self.assertTrue(any("Provenance updated" in event["summary"] for event in mcp_server.get_activity("images")["events"]))

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "optional mcp SDK is not installed")
    def test_mcp_v2_server_exposes_expected_tools(self):
        server = mcp_server.create_mcp_server()
        tools = asyncio.run(server.list_tools())
        names = {tool.name for tool in tools}
        self.assertTrue({"list_collections", "get_reviews", "get_pending", "get_events", "refresh_collections"} <= names)
        self.assertTrue({"get_activity", "get_provenance", "set_provenance", "get_approved_handoff", "inspect_project_config", "sync_project_config"} <= names)


if __name__ == "__main__":
    unittest.main()
