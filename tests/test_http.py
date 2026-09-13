import base64
import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from PIL import Image

from asset_viewer.app import AssetViewerHandler, ThreadingHTTPServer
from asset_viewer.storage import add_collection


class HttpSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["ASSET_VIEWER_HOME"] = str(Path(self.tmp.name) / "data")
        os.environ["ASSET_VIEWER_CACHE"] = str(Path(self.tmp.name) / "cache")
        self.images = Path(self.tmp.name) / "images"
        self.images.mkdir()
        Image.new("RGB", (32, 32), (1, 2, 3)).save(self.images / "sample.png")
        Image.new("RGB", (32, 32), (4, 5, 6)).save(self.images / "second.png")
        (self.images / ".env").write_text("TOP_SECRET=1")
        add_collection(str(self.images), "Samples")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AssetViewerHandler)
        self.server.trusted_hosts = {"127.0.0.1", "localhost", "::1"}
        self.server.csrf_token = "test-csrf-token"
        self.server.auth_password = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        os.environ.pop("ASSET_VIEWER_HOME", None)
        os.environ.pop("ASSET_VIEWER_CACHE", None)
        self.tmp.cleanup()

    def request(self, method, path, *, host=None, origin=None, body=None, csrf=None, authorization=None, content_type="application/json"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        if origin is not None:
            headers["Origin"] = origin
        if body is not None:
            headers["Content-Type"] = content_type
        if csrf is not None:
            headers["X-Asset-Viewer-CSRF"] = csrf
        if authorization is not None:
            headers["Authorization"] = authorization
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        data = response.read()
        headers_out = dict(response.getheaders())
        conn.close()
        return response.status, headers_out, data

    def same_origin(self):
        return f"http://127.0.0.1:{self.port}"

    def test_non_image_cannot_be_fetched_by_guessed_url(self):
        status, _, body = self.request("GET", "/asset/file/samples/.env")
        self.assertEqual(status, 404)
        self.assertNotIn(b"TOP_SECRET", body)

    def test_host_header_is_enforced(self):
        status, _, _ = self.request("GET", "/api/health", host="attacker.example")
        self.assertEqual(status, 421)

    def test_review_rejects_cross_origin(self):
        payload = json.dumps({"collection": "samples", "rel": "sample.png", "status": "approved"})
        status, _, _ = self.request("POST", "/api/review", origin="https://attacker.example", body=payload, csrf="test-csrf-token")
        self.assertEqual(status, 403)

    def test_review_accepts_same_origin(self):
        payload = json.dumps({"collection": "samples", "rel": "sample.png", "status": "approved", "comment": "ship it"})
        status, _, body = self.request("POST", "/api/review", origin=self.same_origin(), body=payload, csrf="test-csrf-token")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])

    def test_review_rejects_missing_csrf(self):
        payload = json.dumps({"collection": "samples", "rel": "sample.png", "status": "approved"})
        status, _, _ = self.request("POST", "/api/review", origin=self.same_origin(), body=payload)
        self.assertEqual(status, 403)

    def test_review_rejects_wrong_content_type(self):
        payload = json.dumps({"collection": "samples", "rel": "sample.png", "status": "approved"})
        status, _, _ = self.request("POST", "/api/review", origin=self.same_origin(), body=payload, csrf="test-csrf-token", content_type="text/plain")
        self.assertEqual(status, 400)

    def test_batch_review_and_manifest_api(self):
        self.request("GET", "/api/gallery?collection=samples")
        payload = json.dumps({"collection": "samples", "rels": ["sample.png", "second.png"], "status": "maybe"})
        status, _, body = self.request("POST", "/api/review", origin=self.same_origin(), body=payload, csrf="test-csrf-token")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["changed"], 2)
        status, _, body = self.request("GET", "/api/reviews?collection=samples&status=maybe")
        manifest = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(manifest["counts"]["total"], 2)

    def test_seen_endpoint_changes_new_state(self):
        status, _, body = self.request("GET", "/api/gallery?collection=samples")
        self.assertEqual(status, 200)
        gallery = json.loads(body)
        self.assertTrue(all(item["is_new"] for item in gallery["images"]))
        payload = json.dumps({"collection": "samples", "rel": "sample.png"})
        status, _, _ = self.request("POST", "/api/seen", origin=self.same_origin(), body=payload, csrf="test-csrf-token")
        self.assertEqual(status, 200)
        _, _, body = self.request("GET", "/api/gallery?collection=samples")
        gallery = json.loads(body)
        sample = next(item for item in gallery["images"] if item["rel"] == "sample.png")
        self.assertFalse(sample["is_new"])

    def test_session_exposes_csrf_only_after_auth_guard(self):
        status, _, body = self.request("GET", "/api/session")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["csrf"], "test-csrf-token")

    def test_optional_basic_auth(self):
        self.server.auth_password = "secret"
        status, headers, _ = self.request("GET", "/")
        self.assertEqual(status, 401)
        self.assertIn("Basic", headers.get("WWW-Authenticate", ""))
        token = base64.b64encode(b"asset-viewer:secret").decode()
        status, _, _ = self.request("GET", "/", authorization=f"Basic {token}")
        self.assertEqual(status, 200)

    def test_stable_collection_url_serves_app(self):
        status, _, body = self.request("GET", "/c/samples")
        self.assertEqual(status, 200)
        self.assertIn(b"Asset Viewer", body)

    def test_svg_is_not_rendered_inline_and_thumb_is_raster(self):
        (self.images / "active.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        status, headers, body = self.request("GET", "/asset/file/samples/active.svg")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "application/octet-stream")
        self.assertTrue(headers.get("Content-Disposition", "").startswith("attachment;"))
        self.assertIn(b"<script>", body)
        status, headers, body = self.request("GET", "/asset/thumb/samples/active.svg")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "image/jpeg")
        self.assertNotIn(b"<script>", body)
        self.assertTrue(body.startswith(b"\xff\xd8"))

    def test_security_headers_present(self):
        status, headers, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("frame-ancestors 'none'", headers.get("Content-Security-Policy", ""))
        self.assertEqual(headers.get("Cross-Origin-Opener-Policy"), "same-origin")
        self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")


if __name__ == "__main__":
    unittest.main()
