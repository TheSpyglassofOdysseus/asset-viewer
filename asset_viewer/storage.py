from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".svg"}
VALID_STATUSES = {"", "approved", "maybe", "rejected"}
_WRITE_LOCK = threading.RLock()
_DB_INIT_LOCK = threading.RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def data_dir() -> Path:
    override = os.environ.get("ASSET_VIEWER_HOME")
    root = Path(override).expanduser() if override else Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "asset-viewer"
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


def cache_dir() -> Path:
    override = os.environ.get("ASSET_VIEWER_CACHE")
    root = Path(override).expanduser() if override else Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "asset-viewer"
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    return root


def registry_path() -> Path:
    return data_dir() / "collections.json"


def database_path() -> Path:
    return data_dir() / "asset-viewer.db"


def legacy_reviews_path() -> Path:
    return data_dir() / "reviews.json"


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    with _WRITE_LOCK:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(fd)
        os.replace(tmp, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass


def _connect() -> sqlite3.Connection:
    path = database_path()
    with _DB_INIT_LOCK:
        conn = sqlite3.connect(path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assets (
                collection TEXT NOT NULL,
                rel TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT '' CHECK(status IN ('', 'approved', 'maybe', 'rejected')),
                comment TEXT NOT NULL DEFAULT '',
                first_seen_at TEXT NOT NULL,
                seen_at TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (collection, rel)
            );
            CREATE INDEX IF NOT EXISTS idx_assets_collection_status
                ON assets(collection, status);
            CREATE INDEX IF NOT EXISTS idx_assets_collection_seen
                ON assets(collection, seen_at);
            """
        )
        _migrate_legacy_reviews(conn)
        conn.commit()
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return conn


@contextmanager
def _connection():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_legacy_reviews(conn: sqlite3.Connection) -> None:
    done = conn.execute("SELECT value FROM meta WHERE key='legacy_reviews_migrated'").fetchone()
    if done:
        return
    legacy = legacy_reviews_path()
    payload = _load_json(legacy, {})
    now = utc_now()
    if isinstance(payload, dict):
        for collection, rows in payload.items():
            if not isinstance(rows, dict):
                continue
            for rel, status in rows.items():
                if status not in VALID_STATUSES or not status:
                    continue
                conn.execute(
                    """
                    INSERT INTO assets(collection, rel, status, comment, first_seen_at, seen_at, updated_at)
                    VALUES(?, ?, ?, '', ?, ?, ?)
                    ON CONFLICT(collection, rel) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at
                    """,
                    (str(collection), str(rel), str(status), now, now, now),
                )
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('legacy_reviews_migrated', ?)", (now,))
    if legacy.exists():
        migrated = legacy.with_name("reviews.json.migrated")
        try:
            legacy.replace(migrated)
        except OSError:
            pass


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower() or "collection"


def collections() -> list[dict[str, str]]:
    rows = _load_json(registry_path(), [])
    valid = []
    for row in rows if isinstance(rows, list) else []:
        try:
            path = Path(row["path"]).expanduser().resolve()
            if path.is_dir():
                valid.append({"slug": str(row["slug"]), "label": str(row["label"]), "path": str(path)})
        except (KeyError, TypeError, OSError):
            continue
    return valid


def add_collection(path: str, label: str | None = None) -> dict[str, str]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"not a directory: {resolved}")
    label = (label or resolved.name.replace("-", " ").replace("_", " ").title()).strip()
    if not label:
        raise ValueError("collection label must not be empty")
    rows = collections()
    existing = next((r for r in rows if Path(r["path"]) == resolved), None)
    used = {r["slug"] for r in rows if not existing or r["slug"] != existing["slug"]}
    slug = existing["slug"] if existing else slugify(label)
    base = slug
    n = 2
    while slug in used:
        slug = f"{base}-{n}"
        n += 1
    row = {"slug": slug, "label": label, "path": str(resolved)}
    rows = [r for r in rows if Path(r["path"]) != resolved]
    rows.append(row)
    rows.sort(key=lambda r: r["label"].lower())
    _atomic_json(registry_path(), rows)
    return row


def remove_collection(key: str) -> dict[str, str]:
    rows = collections()
    try:
        resolved_key = str(Path(key).expanduser().resolve())
    except OSError:
        resolved_key = key
    match = next((r for r in rows if r["slug"] == key or r["path"] == resolved_key), None)
    if not match:
        raise ValueError(f"collection not found: {key}")
    _atomic_json(registry_path(), [r for r in rows if r != match])
    return match


def root_for(slug: str) -> Path | None:
    row = next((r for r in collections() if r["slug"] == slug), None)
    return Path(row["path"]) if row else None


def safe_file(slug: str, relative: str) -> Path | None:
    root = root_for(slug)
    if not root:
        return None
    try:
        # SECURITY: `relative` may originate from an HTTP path. Resolve it first,
        # then enforce containment inside the registered root before any file is
        # opened or stat'ed. This also rejects symlinks that escape the root.
        path = (root / relative).resolve()  # lgtm[py/path-injection]
        if path == root or root not in path.parents or not path.is_file():  # lgtm[py/path-injection]
            return None
        if path.suffix.lower() not in IMAGE_EXTS:
            return None
        return path
    except OSError:
        return None


def ensure_assets(collection: str, relatives: Iterable[str]) -> None:
    unique = sorted({str(rel) for rel in relatives if rel})
    if not unique:
        return
    now = utc_now()
    with _connection() as conn:
        conn.executemany(
            """
            INSERT INTO assets(collection, rel, status, comment, first_seen_at, seen_at, updated_at)
            VALUES(?, ?, '', '', ?, NULL, ?)
            ON CONFLICT(collection, rel) DO NOTHING
            """,
            [(collection, rel, now, now) for rel in unique],
        )


def review_records(collection: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    query = "SELECT collection, rel, status, comment, first_seen_at, seen_at, updated_at FROM assets"
    args: tuple[Any, ...] = ()
    if collection is not None:
        query += " WHERE collection=?"
        args = (collection,)
    query += " ORDER BY collection, rel"
    out: dict[str, dict[str, dict[str, Any]]] = {}
    with _connection() as conn:
        for row in conn.execute(query, args):
            out.setdefault(row["collection"], {})[row["rel"]] = {
                "status": row["status"],
                "comment": row["comment"],
                "first_seen_at": row["first_seen_at"],
                "seen_at": row["seen_at"],
                "updated_at": row["updated_at"],
            }
    return out


def reviews() -> dict[str, dict[str, str]]:
    """Backward-compatible status-only view of review state."""
    records = review_records()
    return {
        collection: {rel: data["status"] for rel, data in rows.items() if data["status"]}
        for collection, rows in records.items()
    }


def set_review(collection: str, relative: str, status: str, comment: str | None = None, mark_seen: bool = True) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid review status: {status}")
    ensure_assets(collection, [relative])
    now = utc_now()
    with _connection() as conn:
        if comment is None:
            conn.execute(
                """
                UPDATE assets
                SET status=?, seen_at=CASE WHEN ? THEN COALESCE(seen_at, ?) ELSE seen_at END, updated_at=?
                WHERE collection=? AND rel=?
                """,
                (status, int(mark_seen), now, now, collection, relative),
            )
        else:
            conn.execute(
                """
                UPDATE assets
                SET status=?, comment=?, seen_at=CASE WHEN ? THEN COALESCE(seen_at, ?) ELSE seen_at END, updated_at=?
                WHERE collection=? AND rel=?
                """,
                (status, str(comment)[:10000], int(mark_seen), now, now, collection, relative),
            )


def set_reviews_batch(collection: str, relatives: Iterable[str], status: str) -> int:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid review status: {status}")
    unique = sorted({str(rel) for rel in relatives if rel})
    if not unique:
        return 0
    ensure_assets(collection, unique)
    now = utc_now()
    with _connection() as conn:
        conn.executemany(
            """
            UPDATE assets SET status=?, seen_at=COALESCE(seen_at, ?), updated_at=?
            WHERE collection=? AND rel=?
            """,
            [(status, now, now, collection, rel) for rel in unique],
        )
    return len(unique)


def set_comment(collection: str, relative: str, comment: str) -> None:
    ensure_assets(collection, [relative])
    now = utc_now()
    with _connection() as conn:
        conn.execute(
            "UPDATE assets SET comment=?, seen_at=COALESCE(seen_at, ?), updated_at=? WHERE collection=? AND rel=?",
            (str(comment)[:10000], now, now, collection, relative),
        )


def mark_seen(collection: str, relatives: Iterable[str]) -> int:
    unique = sorted({str(rel) for rel in relatives if rel})
    if not unique:
        return 0
    ensure_assets(collection, unique)
    now = utc_now()
    with _connection() as conn:
        conn.executemany(
            "UPDATE assets SET seen_at=COALESCE(seen_at, ?), updated_at=CASE WHEN seen_at IS NULL THEN ? ELSE updated_at END WHERE collection=? AND rel=?",
            [(now, now, collection, rel) for rel in unique],
        )
    return len(unique)


def review_manifest(collection: str | None = None, status: str | None = None) -> dict[str, Any]:
    if status is not None and status not in VALID_STATUSES | {"unreviewed", "new"}:
        raise ValueError(f"invalid manifest status: {status}")
    labels = {row["slug"]: row["label"] for row in collections()}
    query = "SELECT collection, rel, status, comment, first_seen_at, seen_at, updated_at FROM assets"
    clauses: list[str] = []
    args: list[Any] = []
    if collection:
        clauses.append("collection=?")
        args.append(collection)
    if status == "unreviewed":
        clauses.append("status=''")
    elif status == "new":
        clauses.append("seen_at IS NULL")
    elif status is not None:
        clauses.append("status=?")
        args.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY collection, rel"
    items = []
    with _connection() as conn:
        for row in conn.execute(query, tuple(args)):
            items.append({
                "collection": row["collection"],
                "collection_label": labels.get(row["collection"], row["collection"]),
                "rel": row["rel"],
                "status": row["status"],
                "comment": row["comment"],
                "first_seen_at": row["first_seen_at"],
                "seen_at": row["seen_at"],
                "updated_at": row["updated_at"],
            })
    counts = {"total": len(items), "approved": 0, "maybe": 0, "rejected": 0, "unreviewed": 0, "new": 0}
    for item in items:
        counts[item["status"] or "unreviewed"] += 1
        if item["seen_at"] is None:
            counts["new"] += 1
    return {"version": 1, "generated_at": utc_now(), "counts": counts, "items": items}


def thumb_path(source: Path) -> Path:
    stat = source.stat()
    key = hashlib.sha256(f"{source}:{stat.st_mtime_ns}:{stat.st_size}".encode()).hexdigest()
    return cache_dir() / f"{key}.jpg"
