from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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

        subprocess.run(
            [sys.executable, "-m", "asset_viewer", "demo", "--path", str(root / "demo-assets")],
            check=True,
            env=env,
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
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            wait_for_server(base_url, process)
            page_errors: list[str] = []
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.on("pageerror", lambda error: page_errors.append(str(error)))

                response = page.goto(base_url, wait_until="networkidle")
                assert response is not None and response.ok, "initial gallery request failed"
                page.locator("#summary").wait_for(state="visible")
                page.wait_for_function("document.querySelector('#summary').textContent.includes('6 images')")

                assert page.title() == "Asset Viewer"
                assert page.locator("#collection").input_value() == "asset-viewer-demo"
                assert page.locator("#grid .card").count() == 6

                page.locator("#grid .card").first.click()
                page.locator("#modal").wait_for(state="visible")
                assert page.locator("#filename").inner_text().strip()

                page.locator("#reviewStatus").select_option("approved")
                page.wait_for_function(
                    "document.querySelector('#reviewDecision').textContent.toLowerCase().includes('approved')"
                )
                page.locator("#close").click()
                page.locator("#modal").wait_for(state="hidden")

                page.locator("#view").select_option("activity")
                page.locator("#activityView").wait_for(state="visible")
                page.wait_for_function("document.querySelectorAll('#activityList .activity-event').length > 0")

                assert not page_errors, f"browser page errors: {page_errors}"
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
