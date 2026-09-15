import tempfile
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer.demo_assets import DEMO_FILES, LEGACY_DEMO_FILES, create_demo


class DemoAssetsTests(unittest.TestCase):
    def test_demo_is_coherent_and_idempotent_without_touching_unrelated_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            keep = root / "keep-me.txt"
            keep.write_text("unrelated")
            for name in LEGACY_DEMO_FILES:
                (root / name).write_text("legacy")

            create_demo(root)
            create_demo(root)

            self.assertEqual(keep.read_text(), "unrelated")
            self.assertTrue(all(not (root / name).exists() for name in LEGACY_DEMO_FILES))
            self.assertEqual({path.name for path in root.glob("*.png")}, set(DEMO_FILES))
            for name in DEMO_FILES:
                with Image.open(root / name) as image:
                    self.assertGreaterEqual(image.width, 1000)
                    self.assertGreaterEqual(image.height, 600)
                    image.verify()


if __name__ == "__main__":
    unittest.main()
