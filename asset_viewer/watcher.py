from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .storage import IMAGE_EXTS, collections

LOGGER = logging.getLogger("asset_viewer.watcher")
ScanCallback = Callable[[str, bool], object]


def _is_relevant(path: str | None) -> bool:
    if not path:
        return False
    return Path(path).suffix.lower() in IMAGE_EXTS


class _CollectionEventHandler(FileSystemEventHandler):
    def __init__(self, slug: str, notify: Callable[[str], None]) -> None:
        self.slug = slug
        self.notify = notify

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            # Directory moves/removals can change many assets at once.
            if event.event_type in {"moved", "deleted"}:
                self.notify(self.slug)
            return
        destination = getattr(event, "dest_path", None)
        if _is_relevant(event.src_path) or _is_relevant(destination):
            self.notify(self.slug)


class CollectionWatcher:
    """Filesystem event accelerator with periodic full reconciliation fallback.

    Watch events never mutate the catalog directly. They only request a normal
    bounded scan, so the existing reconciliation logic remains authoritative.
    """

    def __init__(
        self,
        scan_callback: ScanCallback,
        *,
        debounce_seconds: float = 0.75,
        reconcile_interval: float = 60.0,
        registry_interval: float = 5.0,
    ) -> None:
        self.scan_callback = scan_callback
        self.debounce_seconds = max(0.05, float(debounce_seconds))
        self.reconcile_interval = max(1.0, float(reconcile_interval))
        self.registry_interval = max(0.5, float(registry_interval))
        self.observer = Observer()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._scheduled: dict[str, tuple[str, object]] = {}
        self._pending: dict[str, float] = {}
        self._last_reconcile: dict[str, float] = {}

    def _notify(self, slug: str) -> None:
        with self._lock:
            self._pending[slug] = time.monotonic() + self.debounce_seconds

    def _sync_registry(self) -> None:
        rows = {row["slug"]: row for row in collections() if row.get("available")}
        with self._lock:
            for slug, (path, watch) in list(self._scheduled.items()):
                row = rows.get(slug)
                if not row or str(row["path"]) != path:
                    try:
                        self.observer.unschedule(watch)
                    except Exception:  # watchdog backends vary during shutdown
                        LOGGER.debug("unable to unschedule watcher slug=%s", slug, exc_info=True)
                    self._scheduled.pop(slug, None)
                    self._pending.pop(slug, None)
                    self._last_reconcile.pop(slug, None)

            for slug, row in rows.items():
                path = str(row["path"])
                if slug in self._scheduled:
                    continue
                handler = _CollectionEventHandler(slug, self._notify)
                try:
                    watch = self.observer.schedule(handler, path, recursive=True)
                except OSError:
                    LOGGER.warning("unable to watch collection slug=%s path=%s", slug, path, exc_info=True)
                    continue
                self._scheduled[slug] = (path, watch)
                self._last_reconcile.setdefault(slug, 0.0)
                LOGGER.info("watching collection slug=%s path=%s", slug, path)

    def _scan(self, slug: str, reason: str) -> None:
        try:
            self.scan_callback(slug, True)
            self._last_reconcile[slug] = time.monotonic()
            LOGGER.debug("watcher reconciliation complete slug=%s reason=%s", slug, reason)
        except Exception:
            LOGGER.exception("watcher reconciliation failed slug=%s reason=%s", slug, reason)

    def _run(self) -> None:
        next_registry_sync = 0.0
        while not self._stop.wait(0.1):
            now = time.monotonic()
            if now >= next_registry_sync:
                self._sync_registry()
                next_registry_sync = now + self.registry_interval

            due: list[tuple[str, str]] = []
            with self._lock:
                for slug, deadline in list(self._pending.items()):
                    if now >= deadline:
                        self._pending.pop(slug, None)
                        due.append((slug, "filesystem_event"))
                for slug in self._scheduled:
                    if now - self._last_reconcile.get(slug, 0.0) >= self.reconcile_interval:
                        if slug not in {item[0] for item in due}:
                            due.append((slug, "periodic_fallback"))
            for slug, reason in due:
                if self._stop.is_set():
                    break
                self._scan(slug, reason)

    def start(self) -> CollectionWatcher:
        if self._thread and self._thread.is_alive():
            return self
        self._sync_registry()
        self.observer.start()
        self._thread = threading.Thread(target=self._run, name="asset-viewer-watcher", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        try:
            self.observer.stop()
        finally:
            self.observer.join(timeout=5.0)
            if self._thread:
                self._thread.join(timeout=5.0)


def start_collection_watcher(
    scan_callback: ScanCallback,
    *,
    debounce_seconds: float = 0.75,
    reconcile_interval: float = 60.0,
) -> CollectionWatcher:
    return CollectionWatcher(
        scan_callback,
        debounce_seconds=debounce_seconds,
        reconcile_interval=reconcile_interval,
    ).start()
