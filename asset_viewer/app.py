from __future__ import annotations

import base64
import binascii
import hmac
import json
import logging
import mimetypes
import os
import secrets
import shutil
import time
import urllib.parse
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageOps

from . import __version__
from .storage import (
    IMAGE_EXTS,
    collection_review_state,
    collections,
    complete_collection_review,
    ensure_assets,
    mark_seen,
    pending_summary,
    reopen_collection_review,
    review_history,
    review_manifest,
    review_records,
    root_for,
    safe_file,
    set_comment,
    set_review,
    set_reviews_batch,
    thumb_path,
    undo_last_review,
)

STATIC = Path(__file__).resolve().parent / "static"
LOGGER = logging.getLogger("asset_viewer")
BASE_CSP = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


MAX_SCAN_FILES = _env_int("ASSET_VIEWER_MAX_SCAN_FILES", 50_000)
MAX_SCAN_SECONDS = _env_int("ASSET_VIEWER_MAX_SCAN_SECONDS", 10)
MAX_THUMBNAIL_SOURCE_BYTES = _env_int("ASSET_VIEWER_MAX_THUMBNAIL_BYTES", 250 * 1024 * 1024)
MAX_IMAGE_PIXELS = _env_int("ASSET_VIEWER_MAX_IMAGE_PIXELS", 50_000_000)
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _host_name(value: str) -> str | None:
    try:
        return urllib.parse.urlsplit("//" + value).hostname
    except ValueError:
        return None


def host_is_trusted(value: str | None, trusted_hosts: set[str]) -> bool:
    if not value:
        return False
    host = _host_name(value)
    return bool(host and host.lower().rstrip(".") in trusted_hosts)


def origin_matches_host(origin: str | None, host: str | None) -> bool:
    if not origin:
        return True
    if not host:
        return False
    try:
        return urllib.parse.urlsplit(origin).netloc.lower() == host.lower()
    except ValueError:
        return False


def _safe_dimension(path: Path) -> tuple[int, int, str | None]:
    if path.suffix.lower() == ".svg":
        return 0, 0, "SVG preview is intentionally raster-placeholder only"
    try:
        stat = path.stat()
        if stat.st_size > MAX_THUMBNAIL_SOURCE_BYTES:
            return 0, 0, "file exceeds preview size limit"
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                width, height = image.size
                if width * height > MAX_IMAGE_PIXELS:
                    return 0, 0, "image exceeds preview pixel limit"
                return width, height, None
    except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        LOGGER.warning("preview metadata unavailable for %s: %s", path, exc)
        return 0, 0, "preview metadata unavailable"


def scan_collection(slug: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = root_for(slug)
    if not root:
        return [], {"truncated": False, "reason": None, "elapsed_ms": 0}
    started = time.monotonic()
    found: list[tuple[Path, str, os.stat_result, int, int, str | None]] = []
    truncated = False
    reason = None
    visited = 0
    try:
        iterator = root.rglob("*")
        for path in iterator:
            if time.monotonic() - started > MAX_SCAN_SECONDS:
                truncated, reason = True, "scan_time_limit"
                break
            try:
                if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                    continue
                visited += 1
                if visited > MAX_SCAN_FILES:
                    truncated, reason = True, "scan_file_limit"
                    break
                rel = path.relative_to(root).as_posix()
                stat = path.stat()
                width, height, preview_error = _safe_dimension(path)
                found.append((path, rel, stat, width, height, preview_error))
            except OSError as exc:
                LOGGER.warning("skipping unreadable asset %s: %s", path, exc)
    except OSError as exc:
        LOGGER.warning("collection scan failed for %s: %s", slug, exc)

    ensure_assets(slug, [rel for _, rel, *_ in found])
    records = review_records(slug).get(slug, {})
    rows: list[dict[str, Any]] = []
    for path, rel, stat, width, height, preview_error in found:
        quoted = urllib.parse.quote(rel, safe="/")
        review = records.get(rel, {})
        rows.append({
            "collection": slug,
            "name": path.name,
            "rel": rel,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "width": width,
            "height": height,
            "status": review.get("status", ""),
            "comment": review.get("comment", ""),
            "is_new": review.get("seen_at") is None,
            "first_seen_at": review.get("first_seen_at"),
            "seen_at": review.get("seen_at"),
            "updated_at": review.get("updated_at"),
            "preview_error": preview_error,
            "thumb": f"/asset/thumb/{slug}/{quoted}",
            "file": f"/asset/file/{slug}/{quoted}",
        })
    rows.sort(key=lambda row: (-row["mtime"], row["rel"].lower()))
    elapsed_ms = round((time.monotonic() - started) * 1000)
    if truncated:
        LOGGER.warning("collection scan truncated slug=%s reason=%s images=%s elapsed_ms=%s", slug, reason, len(rows), elapsed_ms)
    return rows, {"truncated": truncated, "reason": reason, "elapsed_ms": elapsed_ms}


def image_rows(slug: str) -> list[dict[str, Any]]:
    return scan_collection(slug)[0]


def _placeholder_thumbnail(path: Path, reason: str) -> bytes:
    destination = thumb_path(path)
    if destination.exists():
        return destination.read_bytes()
    image = Image.new("RGB", (640, 480), (18, 20, 24))
    draw = ImageDraw.Draw(image)
    label = "SVG" if path.suffix.lower() == ".svg" else "PREVIEW"
    draw.rounded_rectangle((42, 42, 598, 438), radius=22, outline=(78, 85, 98), width=3)
    draw.text((70, 76), label, fill=(235, 238, 243))
    draw.text((70, 225), path.name[:72], fill=(235, 238, 243))
    draw.text((70, 260), reason[:88], fill=(145, 151, 163))
    image.save(destination, "JPEG", quality=82, optimize=True)
    return destination.read_bytes()


def make_thumbnail(path: Path) -> bytes:
    if path.suffix.lower() == ".svg":
        return _placeholder_thumbnail(path, "Safe placeholder — open original downloads the SVG")
    destination = thumb_path(path)
    if destination.exists():
        return destination.read_bytes()
    # `path` is supplied only after `safe_file()` containment validation.
    if path.stat().st_size > MAX_THUMBNAIL_SOURCE_BYTES:
        return _placeholder_thumbnail(path, "Preview skipped: file exceeds configured size limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    return _placeholder_thumbnail(path, "Preview skipped: image exceeds configured pixel limit")
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
    except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        LOGGER.warning("thumbnail generation failed for %s: %s", path, exc)
        return _placeholder_thumbnail(path, "Preview unavailable: invalid or unsupported image")


class AssetViewerHandler(BaseHTTPRequestHandler):
    server_version = f"AssetViewer/{__version__}"
    sys_version = ""

    def _trusted_request(self) -> bool:
        trusted = getattr(self.server, "trusted_hosts", LOOPBACK_HOSTS)
        if host_is_trusted(self.headers.get("Host"), trusted):
            return True
        self._send(421, "text/plain; charset=utf-8", "Untrusted Host header")
        return False

    def _authenticated_request(self) -> bool:
        password = getattr(self.server, "auth_password", None)
        if not password:
            return True
        header = self.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
                username, supplied = decoded.split(":", 1)
                if hmac.compare_digest(username, "asset-viewer") and hmac.compare_digest(supplied, password):
                    return True
            except (ValueError, UnicodeDecodeError, binascii.Error):
                pass
        self._send(401, "text/plain; charset=utf-8", "Authentication required", {"WWW-Authenticate": 'Basic realm="Asset Viewer", charset="UTF-8"'})
        return False

    def _guard(self) -> bool:
        return self._trusted_request() and self._authenticated_request()

    def _csrf_valid(self) -> bool:
        token = self.headers.get("X-Asset-Viewer-CSRF", "")
        expected = getattr(self.server, "csrf_token", "")
        if not token or not hmac.compare_digest(token, expected):
            return False
        return origin_matches_host(self.headers.get("Origin"), self.headers.get("Host"))

    def _security_headers(self) -> dict[str, str]:
        return {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": BASE_CSP,
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }

    def _send(self, status: int, content_type: str, body: str | bytes, extra: dict[str, str] | None = None) -> None:
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in self._security_headers().items():
            self.send_header(key, value)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_json(self, status: int, payload: Any, extra: dict[str, str] | None = None) -> None:
        headers = {"Cache-Control": "no-store"}
        headers.update(extra or {})
        self._send(status, "application/json; charset=utf-8", json.dumps(payload, separators=(",", ":")), headers)

    def _send_path(self, status: int, content_type: str, path: Path, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        for key, value in self._security_headers().items():
            self.send_header(key, value)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            # Callers pass packaged static files or a `safe_file()`-validated asset.
            with path.open("rb") as handle:
                shutil.copyfileobj(handle, self.wfile, length=1024 * 1024)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _static(self, name: str, content_type: str) -> None:
        path = STATIC / name
        self._send_path(200, content_type, path, {"Cache-Control": "public, max-age=300"}) if path.is_file() else self._send(404, "text/plain; charset=utf-8", "Not found")

    def _read_json(self, maximum: int = 256 * 1024) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > maximum:
            raise ValueError("request too large")
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ValueError("content type must be application/json")
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def do_GET(self) -> None:
        if not self._trusted_request():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            return self._send_json(200, {"ok": True, "service": "asset-viewer", "version": __version__})
        if not self._authenticated_request():
            return
        if path in ("/", "/index.html") or path.startswith("/c/"):
            return self._static("index.html", "text/html; charset=utf-8")
        if path == "/app.css":
            return self._static("app.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self._static("app.js", "application/javascript; charset=utf-8")
        if path == "/api/session":
            return self._send_json(200, {"csrf": getattr(self.server, "csrf_token", ""), "version": __version__})
        if path == "/api/gallery":
            rows = collections()
            query = urllib.parse.parse_qs(parsed.query)
            active = (query.get("collection") or [rows[0]["slug"] if rows else ""])[0]
            if active and not any(row["slug"] == active for row in rows):
                return self._send_json(404, {"error": "collection not found"})
            public_rows = [{"slug": row["slug"], "label": row["label"]} for row in rows]
            images, scan = scan_collection(active) if active else ([], {"truncated": False, "reason": None, "elapsed_ms": 0})
            review_state = collection_review_state(active) if active else None
            return self._send_json(200, {"collections": public_rows, "active": active, "images": images, "scan": scan, "review_state": review_state})
        if path == "/api/reviews":
            query = urllib.parse.parse_qs(parsed.query)
            collection = (query.get("collection") or [None])[0]
            status = (query.get("status") or [None])[0]
            try:
                return self._send_json(200, review_manifest(collection, status))
            except ValueError as exc:
                return self._send_json(400, {"error": str(exc)})
        if path == "/api/pending":
            query = urllib.parse.parse_qs(parsed.query)
            collection = (query.get("collection") or [None])[0]
            try:
                return self._send_json(200, pending_summary(collection))
            except ValueError as exc:
                return self._send_json(400, {"error": str(exc)})
        if path == "/api/review-history":
            query = urllib.parse.parse_qs(parsed.query)
            collection = (query.get("collection") or [""])[0]
            rel = (query.get("rel") or [""])[0]
            if not root_for(collection) or not rel:
                return self._send_json(400, {"error": "collection and rel are required"})
            return self._send_json(200, {"collection": collection, "rel": rel, "events": review_history(collection, rel)})
        if path.startswith("/asset/file/") or path.startswith("/asset/thumb/"):
            parts = path.split("/", 4)
            if len(parts) != 5:
                return self._send(404, "text/plain; charset=utf-8", "Not found")
            kind, slug, relative = parts[2], parts[3], urllib.parse.unquote(parts[4])
            source = safe_file(slug, relative)
            if not source:
                return self._send(404, "text/plain; charset=utf-8", "Not found")
            if kind == "thumb":
                return self._send(200, "image/jpeg", make_thumbnail(source), {"Cache-Control": "public, max-age=86400"})
            if source.suffix.lower() == ".svg":
                filename = urllib.parse.quote(source.name, safe="")
                return self._send_path(200, "application/octet-stream", source, {"Cache-Control": "private, max-age=3600", "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"})
            content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            return self._send_path(200, content_type, source, {"Cache-Control": "private, max-age=3600"})
        return self._send(404, "text/plain; charset=utf-8", "Not found")

    def do_POST(self) -> None:
        if not self._guard():
            return
        if not self._csrf_valid():
            return self._send_json(403, {"error": "CSRF validation failed"})
        path = urllib.parse.urlparse(self.path).path
        try:
            payload = self._read_json()
            slug = str(payload.get("collection", ""))
            if not root_for(slug):
                raise ValueError("collection not found")
            if path == "/api/review":
                if isinstance(payload.get("rels"), list):
                    rels = [str(rel) for rel in payload["rels"]]
                    if not rels or len(rels) > 500:
                        raise ValueError("batch must contain 1-500 assets")
                    if any(not safe_file(slug, rel) for rel in rels):
                        raise ValueError("one or more assets are invalid")
                    status = str(payload.get("status", ""))
                    changed = set_reviews_batch(slug, rels, status)
                    return self._send_json(200, {"ok": True, "changed": changed, "status": status})
                rel = str(payload.get("rel", ""))
                if not safe_file(slug, rel):
                    raise ValueError("asset not found")
                status = str(payload.get("status", ""))
                comment = payload.get("comment")
                if comment is not None and not isinstance(comment, str):
                    raise ValueError("comment must be a string")
                set_review(slug, rel, status, comment)
                return self._send_json(200, {"ok": True, "status": status})
            if path == "/api/comment":
                rel = str(payload.get("rel", ""))
                comment = payload.get("comment", "")
                if not safe_file(slug, rel) or not isinstance(comment, str):
                    raise ValueError("invalid comment request")
                set_comment(slug, rel, comment)
                return self._send_json(200, {"ok": True})
            if path == "/api/seen":
                rels = payload.get("rels")
                if not isinstance(rels, list):
                    rels = [payload.get("rel")]
                rels = [str(rel) for rel in rels if rel]
                if not rels or len(rels) > 500 or any(not safe_file(slug, rel) for rel in rels):
                    raise ValueError("invalid seen request")
                changed = mark_seen(slug, rels)
                return self._send_json(200, {"ok": True, "changed": changed})
            if path == "/api/complete":
                state = complete_collection_review(slug)
                return self._send_json(200, {"ok": True, "review_state": state})
            if path == "/api/reopen":
                state = reopen_collection_review(slug)
                return self._send_json(200, {"ok": True, "review_state": state})
            if path == "/api/undo":
                rel = str(payload.get("rel", ""))
                if not safe_file(slug, rel):
                    raise ValueError("asset not found")
                result = undo_last_review(slug, rel)
                if not result:
                    raise ValueError("no review change to undo")
                return self._send_json(200, {"ok": True, "result": result})
            return self._send_json(404, {"error": "not found"})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            LOGGER.warning("bad request path=%s client=%s error=%s", path, self.client_address[0], exc)
            return self._send_json(400, {"ok": False, "error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.client_address[0], fmt % args)


def serve(
    host: str = "127.0.0.1",
    port: int = 8160,
    trusted_hosts: list[str] | None = None,
    auth_password: str | None = None,
    log_level: str = "INFO",
) -> None:
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    normalized = {h.lower().rstrip(".") for h in (trusted_hosts or []) if h}
    if host in LOOPBACK_HOSTS:
        normalized |= LOOPBACK_HOSTS
    elif not normalized:
        raise ValueError("non-loopback binds require at least one --trusted-host")
    server = ThreadingHTTPServer((host, port), AssetViewerHandler)
    server.trusted_hosts = normalized
    server.csrf_token = secrets.token_urlsafe(32)
    server.auth_password = auth_password or os.environ.get("ASSET_VIEWER_PASSWORD")
    LOGGER.info("Asset Viewer %s running at http://%s:%s auth=%s", __version__, host, port, "enabled" if server.auth_password else "disabled")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
