"""Optional 100-character hierarchy is a non-destructive navigation index."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asset_viewer.character_roster import public_character_roster


class CharacterRosterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.roster = Path(self.temp.name) / "roster.json"
        self.characters = [
            {"id": f"CHR-{index:03}", "name": f"Character {index:03}", "faction": "Fictional Guild"}
            for index in range(1, 101)
        ]
        self.characters[0]["name"] = "Sir Aldric"
        self.characters[1]["name"] = "Marra Vell"
        self.characters[2]["name"] = "Prior Edrin"
        self.roster.write_text(json.dumps({"characters": self.characters}))
        self.env = patch.dict(os.environ, {"ASSET_VIEWER_CHARACTER_ROSTER_PATH": str(self.roster)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_one_hundred_characters_in_roster_order_even_without_assets(self):
        actual = public_character_roster([])
        self.assertEqual(len(actual), 100)
        self.assertEqual(actual[0]["id"], "CHR-001")
        self.assertEqual(actual[-1]["id"], "CHR-100")
        self.assertTrue(all(not row["collections"] for row in actual))

    def test_prior_edrin_revisions_are_collapsed_under_one_identity(self):
        rows = [
            {"slug": "chr-003-prior-edrin-flail-locked-v003", "label": "Flail lock"},
            {"slug": "chr-003-prior-edrin-v008-back-handle-corrected", "label": "Edrin back v008"},
            {"slug": "chr-002-marra-v002", "label": "Marra Vell v002"},
            {"slug": "chr-001-aldric", "label": "Aldric"},
            {"slug": "unrelated-studio-demo", "label": "Other project"},
        ]
        result = public_character_roster(rows)
        mapping = {row["id"]: row["collections"] for row in result}
        self.assertEqual(len(mapping["CHR-003"]), 2)
        self.assertIn("chr-003-prior-edrin-v008-back-handle-corrected", mapping["CHR-003"])
        self.assertEqual(mapping["CHR-002"], ["chr-002-marra-v002"])
        self.assertEqual(mapping["CHR-001"], ["chr-001-aldric"])
        self.assertFalse(any("unrelated" in slug for slugs in mapping.values() for slug in slugs))

    def test_legacy_names_may_match_but_other_projects_stay_unassigned(self):
        rows = [
            {"slug": "aldric-legs-armor", "label": "Aldric leg armor"},
            {"slug": "marra-vell-chr-002-source-art-v001", "label": "Marra source art"},
            {"slug": "not-my-assets", "label": "Restaurant Equipment"},
        ]
        result = public_character_roster(rows)
        self.assertIn("aldric-legs-armor", result[0]["collections"])
        self.assertIn("marra-vell-chr-002-source-art-v001", result[1]["collections"])
        self.assertFalse(any("not-my-assets" in row["collections"] for row in result))

    def test_disabled_and_invalid_roster_falls_back_to_normal_gallery(self):
        with patch.dict(os.environ, {"ASSET_VIEWER_CHARACTER_ROSTER_PATH": ""}):
            self.assertEqual(public_character_roster([]), [])
        self.roster.write_text("{ broken")
        self.assertEqual(public_character_roster([]), [])
        self.roster.write_text(json.dumps({"characters": [{"id": "X", "name": "<script>alert(1)</script>"}]}))
        self.assertEqual(public_character_roster([]), [])

    def test_duplicate_character_ids_ignored(self):
        self.characters.append({"id": "CHR-003", "name": "Duplicate Edrin"})
        self.roster.write_text(json.dumps({"characters": self.characters}))
        actual = public_character_roster([])
        self.assertEqual(len(actual), 100)


if __name__ == "__main__":
    unittest.main()
