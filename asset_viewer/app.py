from __future__ import annotations

import json
import mimetypes
import shutil
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageOps

from .storage import IMAGE_EXTS, collections, reviews, safe_file, set_review, thumb_path, root_for

STATIC = Path(__file__).resolve().parent / "static"


def image_rows(slug: str) -> list[dict]:
    root = root_for(slug)
    if not root:
        return []
    review_data = reviews()
    out = []
    for path in root.rglob("*"):
        try:
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                continue
            rel = path.relative_to(root).as_posix()
            stat = path.stat()
            width = height = 0
            if path.suffix.lower() != ".svg":
                try:
                    with Image.open(path) as image:
                        width, height = image.size
                except Exception:
                    pass
            quoted = urllib.parse.quote(rel, safe="/")
            out.append({
                "collection": slug,
                "name": path.name,
                "rel": rel,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "width": width,
                "height": height,
                "status": review_data.get(slug, {}).get(rel, ""),
                "thumb": f"/asset/thumb/{slug}/{quoted}",
                "file": f"/asset/file/{slug}/{quoted}",
            })
        except OSError:
            continue
    out.sort(key=lambda row: (-row["mtime"], row["rel"].lower()))
    return out


def make_thumbnail(path: Path) -> bytes:
    destination = thumb_path(path)
    if destination.exists():
        return destination.read_bytes()
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((640, 480), Image.Resampling.LANCZOS)
        if image.mode not in ("RGB", "L"):
            background = Image.new("RGB", image.size, (17, 17, 17))
            if "A" in image.getbands():
                background.paste(image, mask=image.getchannel("A"))
            else:
                background.paste(image.convert("RGB"))
            image = background
        elif image.mode == "L":
            image = image.convert("RGB")
        image.save(destination, "JPEG", quality=82, optimize=True)
    return destination.read_bytes()


class AssetViewerHandler(BaseHTTPRequestHandler):
    server_version = "AssetViewer/0.1"

    def _send(self, status: int, content_type: str, body: str | bytes, extra: dict[str, str] | None = None) -> None:
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _send_path(self, status: int, content_type: str, path: Path, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        with path.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile, length=1024 * 1024)

    def _static(self, name: str, content_type: str) -> None:
        path = STATIC / name
        self._send_path(200, content_type, path) if path.is_file() else self._send(404, "text/plain; charset=utf-8", "Not found")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            return self._static("index.html", "text/html; charset=utf-8")
        if path == "/app.css":
            return self._static("app.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self._static("app.js", "application/javascript; charset=utf-8")
        if path == "/api/health":
            return self._send(200, "application/json", json.dumps({"ok": True, "service": "asset-viewer"}))
        if path == "/api/gallery":
            rows = collections()
            query = urllib.parse.parse_qs(parsed.query)
            active = (query.get("collection") or [rows[0]["slug"] if rows else ""])[0]
            public_rows = [{"slug": row["slug"], "label": row["label"]} for row in rows]
            return self._send(200, "application/json", json.dumps({"collections": public_rows, "active": active, "images": image_rows(active)}))
        if path.startswith("/asset/file/") or path.startswith("/asset/thumb/"):
            parts = path.split("/", 4)
            if len(parts) != 5:
                return self._send(404, "text/plain; charset=utf-8", "Not found")
            kind, slug, relative = parts[2], parts[3], urllib.parse.unquote(parts[4])
            source = safe_file(slug, relative)
            if not source:
                return self._send(404, "text/plain; charset=utf-8", "Not found")
            if kind == "thumb" and source.suffix.lower() != ".svg":
                try:
                    return self._send(200, "image/jpeg", make_thumbnail(source), {"Cache-Control": "public, max-age=86400"})
                except Exception:
                    return self._send(415, "text/plain; charset=utf-8", "Preview unavailable")
            content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            return self._send_path(200, content_type, source, {"Cache-Control": "private, max-age=3600"})
        return self._send(404, "text/plain; charset=utf-8", "Not found")

    def do_POST(self) -> None:
        if urllib.parse.urlparse(self.path).path != "/api/review":
            return self._send(404, "text/plain; charset=utf-8", "Not found")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 65536:
                raise ValueError("request too large")
            payload = json.loads(self.rfile.read(length) or b"{}")
            slug = str(payload.get("collection", ""))
            relative = str(payload.get("rel", ""))
            status = str(payload.get("status", ""))
            if status not in ("", "approved", "maybe", "rejected") or not safe_file(slug, relative):
                raise ValueError("invalid review")
            set_review(slug, relative, status)
            return self._send(200, "application/json", json.dumps({"ok": True, "status": status}))
        except Exception:
            return self._send(400, "application/json", json.dumps({"ok": False, "error": "bad request"}))

    def log_message(self, fmt: str, *args) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8160) -> None:
    server = ThreadingHTTPServer((host, port), AssetViewerHandler)
    print(f"Asset Viewer running at http://{host}:{port}")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
