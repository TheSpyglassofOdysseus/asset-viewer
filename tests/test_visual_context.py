import asyncio
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer import mcp_server, storage
from asset_viewer.app import scan_collection
from asset_viewer.visual_context import (
    VISUAL_PANEL_URI,
    get_visual_context,
    record_visual_review,
    visual_decision_panel_html,
)


class VisualContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("ASSET_VIEWER_HOME")
        self.old_public = os.environ.get("ASSET_VIEWER_PUBLIC_BASE_URL")
        os.environ["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ.pop("ASSET_VIEWER_PUBLIC_BASE_URL", None)
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()
        for index, name in enumerate(("reference.png", "rejected.png", "candidate.png"), start=1):
            path = self.images / name
            Image.new("RGB", (100 + index, 70 + index), (index * 30, 20, 40)).save(path)
            os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index))
        storage.add_collection(str(self.images), "FDI captures")
        scan_collection("fdi-captures", force=True)
        self.records = {row["rel"]: row for row in storage.catalog_records("fdi-captures")}
        ref_id = self.records["reference.png"]["asset_id"]
        common = {"source_project": "FDI", "extra": {"surface": "Quote Editor", "viewport": "412x915", "device": "mobile"}}
        storage.set_asset_metadata("fdi-captures", "reference.png", common | {"run_id": "run-ref", "git_commit": "111111111111", "extra": common["extra"]})
        storage.set_asset_metadata("fdi-captures", "rejected.png", common | {"run_id": "run-bad", "git_commit": "222222222222", "extra": common["extra"]})
        storage.set_asset_metadata(
            "fdi-captures",
            "candidate.png",
            common | {"run_id": "run-new", "git_commit": "333333333333", "parent_asset_id": ref_id, "extra": common["extra"]},
        )
        storage.set_review("fdi-captures", "reference.png", "approved", comment="Keep the clean command bar")
        storage.set_review("fdi-captures", "rejected.png", "rejected", comment="Right rail is too busy")

    def tearDown(self):
        if self.old_home is None:
            os.environ.pop("ASSET_VIEWER_HOME", None)
        else:
            os.environ["ASSET_VIEWER_HOME"] = self.old_home
        if self.old_public is None:
            os.environ.pop("ASSET_VIEWER_PUBLIC_BASE_URL", None)
        else:
            os.environ["ASSET_VIEWER_PUBLIC_BASE_URL"] = self.old_public
        self.tmp.cleanup()

    def test_context_reuses_prior_decisions_and_exact_provenance(self):
        context = get_visual_context(
            "fdi-captures",
            "Quote Editor",
            viewport="412x915",
            candidate="candidate.png",
            base_url="https://viewer.example.test",
        )
        self.assertEqual(context["candidate"]["rel"], "candidate.png")
        self.assertEqual(context["candidate"]["git_commit"], "333333333333")
        self.assertEqual(context["candidate"]["run_id"], "run-new")
        self.assertEqual(context["candidate"]["device"], "mobile")
        self.assertEqual(context["reference"]["rel"], "reference.png")
        self.assertEqual(context["reference"]["status"], "approved")
        self.assertTrue(context["candidate"]["preview_url"].startswith("https://viewer.example.test/asset/preview/"))
        self.assertIn("Right rail is too busy", {item["comment"] for item in context["prior_decisions"]})
        self.assertEqual(context["render_contract"]["max_primary_images"], 2)
        self.assertTrue(context["render_contract"]["uses_bounded_previews"])
        self.assertTrue(context["render_contract"]["project_size_independent"])

    def test_client_payload_bounds_annotations_and_history_text(self):
        asset_id = self.records["candidate.png"]["asset_id"]
        for index in range(8):
            storage.create_annotation(
                "fdi-captures", asset_id, "point", 0.1, 0.1, text=("note-%d " % index) + ("x" * 1200)
            )
        context = get_visual_context(
            "fdi-captures", "Quote Editor", viewport="412x915", candidate="candidate.png"
        )
        self.assertEqual(len(context["candidate"]["annotations"]), 6)
        self.assertTrue(all(len(item["text"]) <= 1000 for item in context["candidate"]["annotations"]))
        self.assertLessEqual(len(context["candidate"]["review_history"]), 4)
        self.assertLessEqual(len(context["prior_decisions"]), 6)

    def test_missing_surface_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "no present visual evidence"):
            get_visual_context("fdi-captures", "Does Not Exist")

    def test_review_write_requires_explicit_human_action_and_reuses_canonical_state(self):
        with self.assertRaisesRegex(ValueError, "explicit human/UI action"):
            record_visual_review("fdi-captures", "candidate.png", "approved", "Looks good")
        result = record_visual_review(
            "fdi-captures",
            "candidate.png",
            "maybe",
            "Typography still looks soft",
            explicit_human_action=True,
        )
        self.assertEqual(result["status"], "maybe")
        reviews = storage.review_manifest("fdi-captures")
        candidate = next(item for item in reviews["items"] if item["rel"] == "candidate.png")
        self.assertEqual(candidate["status"], "maybe")
        self.assertEqual(candidate["comment"], "Typography still looks soft")
        events = storage.review_events_since("fdi-captures", 0, 100)["events"]
        self.assertTrue(any(event["rel"] == "candidate.png" and event["new_status"] == "maybe" for event in events))

    def test_panel_is_bounded_and_uses_mcp_apps_bridge(self):
        source = visual_decision_panel_html()
        self.assertIn('request("tools/call"', source)
        self.assertIn("ui/notifications/tool-result", source)
        self.assertIn("record_visual_review", source)
        self.assertIn("explicit_human_action:true", source)
        self.assertNotIn("localStorage", source)
        self.assertNotIn("sessionStorage", source)
        self.assertEqual(source.count('createElement("img")'), 1)

    @unittest.skipUnless(importlib.util.find_spec("mcp"), "optional mcp SDK is not installed")
    def test_mcp_server_advertises_panel_resource_and_render_tool(self):
        server = mcp_server.create_mcp_server()
        tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
        self.assertIn("get_visual_context", tools)
        self.assertIn("render_visual_decision_panel", tools)
        self.assertIn("record_visual_review", tools)
        render_tool = tools["render_visual_decision_panel"]
        render_meta = render_tool.meta
        self.assertEqual(render_meta["ui"]["resourceUri"], VISUAL_PANEL_URI)
        self.assertEqual(render_meta["openai/outputTemplate"], VISUAL_PANEL_URI)
        self.assertEqual(render_tool.input_schema["required"], ["context"])
        self.assertTrue(tools["get_visual_context"].annotations.read_only_hint)
        self.assertFalse(tools["record_visual_review"].annotations.read_only_hint)
        self.assertTrue(tools["record_visual_review"].annotations.idempotent_hint)
        resources = {str(resource.uri): resource for resource in asyncio.run(server.list_resources())}
        resource = resources[VISUAL_PANEL_URI]
        self.assertEqual(resource.mime_type, "text/html;profile=mcp-app")
        self.assertIn("ui", resource.meta)
        contents = asyncio.run(server.read_resource(VISUAL_PANEL_URI))
        self.assertEqual(len(contents), 1)
        self.assertIn("Visual decision", contents[0].content)


if __name__ == "__main__":
    unittest.main()
