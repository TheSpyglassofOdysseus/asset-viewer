import io
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer.app import make_thumbnail, scan_collection
from asset_viewer.storage import add_collection, safe_file


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
class VideoAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        os.environ["ASSET_VIEWER_HOME"] = str(root / "data")
        os.environ["ASSET_VIEWER_CACHE"] = str(root / "cache")
        self.media = root / "media"
        self.media.mkdir()
        self.video = self.media / "sample.mp4"
        subprocess.run(
            [
                shutil.which("ffmpeg") or "ffmpeg",
                "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=0x245fbd:s=320x180:d=1.2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-y", str(self.video),
            ],
            check=True,
            timeout=15,
        )
        self.collection = add_collection(str(self.media), "Videos")

    def tearDown(self):
        self.tmp.cleanup()

    def test_video_is_catalogued_and_gets_jpeg_poster(self):
        rows, _ = scan_collection(self.collection["slug"], force=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["media_type"], "video")
        source = safe_file(self.collection["slug"], "sample.mp4")
        self.assertIsNotNone(source)
        poster = make_thumbnail(source)
        with Image.open(io.BytesIO(poster)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (640, 360))


if __name__ == "__main__":
    unittest.main()
