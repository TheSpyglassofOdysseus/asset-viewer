from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from playwright.sync_api import sync_playwright


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_until(description: str, condition: Callable[[], bool], timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if condition():
                return
        except Exception as exc:  # transient browser/navigation state
            last_error = exc
        time.sleep(0.1)
    detail = f"; last error: {last_error}" if last_error else ""
    raise AssertionError(f"Timed out waiting for {description}{detail}")


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30.0) as response:
        assert response.status == 200, f"GET {url} returned {response.status}"
        payload = json.load(response)
    assert isinstance(payload, dict), f"GET {url} did not return a JSON object"
    return payload


def wait_for_server(base_url: str, process: subprocess.Popen[str], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"Asset Viewer exited before startup (code {process.returncode}):\n{output}")
        try:
            with urllib.request.urlopen(f"{base_url}/api/session", timeout=1.0) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.2)
    raise RuntimeError("Asset Viewer did not become ready before the browser smoke-test timeout")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="asset-viewer-browser-smoke-") as temp_dir:
        root = Path(temp_dir)
        env = os.environ.copy()
        env["ASSET_VIEWER_HOME"] = str(root / "data")
        env["ASSET_VIEWER_CACHE"] = str(root / "cache")

        # Run the product outside the repository checkout. In release CI this
        # prevents the source tree from shadowing the cleanly installed wheel.
        subprocess.run(
            [sys.executable, "-m", "asset_viewer", "demo", "--path", str(root / "demo-assets")],
            check=True,
            env=env,
            cwd=root,
            capture_output=True,
            text=True,
        )

        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "asset_viewer",
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-watch",
                "--log-level",
                "WARNING",
            ],
            env=env,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            wait_for_server(base_url, process)

            # Prove the documented demo -> serve path populates the catalog on
            # the first normal gallery request before exercising the browser UI.
            gallery = get_json(f"{base_url}/api/gallery")
            assert gallery.get("active") == "asset-viewer-demo", gallery
            assert len(gallery.get("images") or []) == 6, gallery
            assert not (gallery.get("scan") or {}).get("truncated"), gallery.get("scan")

            page_errors: list[str] = []
            console_errors: list[str] = []
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.on(
                    "console",
                    lambda message: console_errors.append(message.text) if message.type == "error" else None,
                )

                response = page.goto(base_url, wait_until="domcontentloaded")
                assert response is not None and response.ok, "initial gallery request failed"
                page.locator("#summary").wait_for(state="visible")
                try:
                    wait_until(
                        "six demo images to render",
                        lambda: page.locator("#grid .card").count() == 6,
                    )
                except AssertionError as exc:
                    summary = page.locator("#summary").text_content()
                    raise AssertionError(
                        f"{exc}; summary={summary!r}; page_errors={page_errors!r}; console_errors={console_errors!r}"
                    ) from exc

                assert page.title() == "Asset Viewer"
                assert page.locator("#collection").input_value() == "asset-viewer-demo"
                summary = (page.locator("#summary").text_content() or "").strip()
                assert summary and summary.lower() != "loading…", summary

                page.locator("#grid .card").first.click()
                page.locator("#modal").wait_for(state="visible")
                assert page.locator("#filename").inner_text().strip()

                with page.expect_response(
                    lambda response: urllib.parse.urlsplit(response.url).path == "/api/review"
                    and response.request.method == "POST",
                    timeout=15_000,
                ) as review_response_info:
                    page.locator("#reviewStatus").select_option("approved")
                review_response = review_response_info.value
                assert review_response.ok, f"review mutation returned HTTP {review_response.status}"
                wait_until(
                    "approved status selector",
                    lambda: page.locator("#reviewStatus").input_value() == "approved",
                )

                reviews = get_json(f"{base_url}/api/reviews?collection=asset-viewer-demo&present=1")
                approved = [item for item in reviews.get("items", []) if item.get("status") == "approved"]
                assert len(approved) == 1, reviews

                page.locator("#close").click()
                page.locator("#modal").wait_for(state="hidden")

                page.locator("#view").select_option("activity")
                page.locator("#activityView").wait_for(state="visible")
                wait_until(
                    "review event to appear in Activity",
                    lambda: page.locator("#activityList .activity-event").count() > 0,
                )

                assert not page_errors, f"browser page errors: {page_errors}"
                assert not console_errors, f"browser console errors: {console_errors}"

                # Exercise the ChatGPT/MCP Apps inline panel independently of
                # a public image origin. Tool-result `_meta` is widget-only, so
                # private/tunneled deployments hydrate exactly two bounded
                # previews without placing image bytes in structuredContent.
                from asset_viewer.visual_context import visual_decision_panel_html

                panel_errors: list[str] = []
                panel_console_errors: list[str] = []
                panel = browser.new_page(viewport={"width": 390, "height": 844})
                panel.on("pageerror", lambda error: panel_errors.append(str(error)))
                panel.on(
                    "console",
                    lambda message: panel_console_errors.append(message.text) if message.type == "error" else None,
                )
                preview = (
                    "data:image/jpeg;base64,"
                    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
                    "2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
                    "wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAEf/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAABB//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPxB//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPxB//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxB//9k="
                )
                candidate_id = "candidate-private"
                reference_id = "reference-private"
                panel_context = {
                    "collection": "fdi-visual-audit-2026-09-14",
                    "surface": "Quote Workbook",
                    "viewport": "390x844",
                    "viewer_url": "https://viewer.invalid/c/fdi-visual-audit-2026-09-14",
                    "render_contract": {"max_primary_images": 2},
                    "candidate": {
                        "asset_id": candidate_id, "rel": "candidate.png", "status": "",
                        "preview_url": "http://127.0.0.1:9/unreachable-candidate.jpg",
                        "annotations": [], "review_history": [],
                    },
                    "reference": {
                        "asset_id": reference_id, "rel": "reference.png", "status": "approved",
                        "preview_url": "http://127.0.0.1:9/unreachable-reference.jpg",
                        "annotations": [], "review_history": [],
                    },
                    "prior_decisions": [],
                }
                hidden_meta = {
                    "assetViewer": {
                        "previewDataByAssetId": {candidate_id: preview, reference_id: preview},
                        "previewCount": 2,
                    }
                }
                panel_bootstrap = (
                    "<script>window.openai = { toolOutput: " + json.dumps(panel_context) + ", "
                    "toolResponseMetadata: { mcp_tool_result: { _meta: " + json.dumps(hidden_meta) + " } } };</script>"
                )
                panel_html = visual_decision_panel_html().replace("<head>", "<head>" + panel_bootstrap, 1)
                panel.set_content(panel_html, wait_until="domcontentloaded")
                panel.locator("#candidateFrame img").wait_for(state="visible")
                panel.locator("#referenceFrame img").wait_for(state="visible")
                assert panel.locator("#candidateFrame img").get_attribute("src").startswith("data:image/jpeg;base64,")
                assert panel.locator("#referenceFrame img").get_attribute("src").startswith("data:image/jpeg;base64,")
                approve_box = panel.locator('button[data-status="approved"]').bounding_box()
                assert approve_box and approve_box["y"] + approve_box["height"] <= 844, approve_box
                assert not panel_errors, f"panel page errors: {panel_errors}"
                assert not panel_console_errors, f"panel console errors: {panel_console_errors}"
                panel.close()
                browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
