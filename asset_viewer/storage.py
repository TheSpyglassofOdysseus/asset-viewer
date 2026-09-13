from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".svg"}
VALID_STATUSES = {"", "approved", "maybe", "rejected"}
_WRITE_LOCK = threading.RLock()
_DB_INIT_LOCK = threading.RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


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
            CREATE TABLE IF NOT EXISTS review_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection TEXT NOT NULL,
                rel TEXT NOT NULL,
                action TEXT NOT NULL,
                old_status TEXT NOT NULL DEFAULT '',
                new_status TEXT NOT NULL DEFAULT '',
                old_comment TEXT NOT NULL DEFAULT '',
                new_comment TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                undone_at TEXT,
                details TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_review_events_asset
                ON review_events(collection, rel, id DESC);
            CREATE TABLE IF NOT EXISTS collection_state (
                collection TEXT PRIMARY KEY,
                completed_at TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS catalog_state (
                collection TEXT PRIMARY KEY,
                generation INTEGER NOT NULL DEFAULT 0,
                last_scan_at TEXT,
                changed_at TEXT,
                truncated INTEGER NOT NULL DEFAULT 0,
                reason TEXT,
                elapsed_ms INTEGER NOT NULL DEFAULT 0,
                added INTEGER NOT NULL DEFAULT 0,
                changed INTEGER NOT NULL DEFAULT 0,
                removed INTEGER NOT NULL DEFAULT 0,
                renamed INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        _migrate_legacy_reviews(conn)
        _ensure_catalog_schema(conn)
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


def _ensure_catalog_schema(conn: sqlite3.Connection) -> None:
    asset_columns = {row["name"] for row in conn.execute("PRAGMA table_info(assets)")}
    additions = {
        "asset_id": "TEXT",
        "device": "INTEGER",
        "inode": "INTEGER",
        "size": "INTEGER",
        "mtime_ns": "INTEGER",
        "width": "INTEGER",
        "height": "INTEGER",
        "preview_error": "TEXT",
        "present": "INTEGER NOT NULL DEFAULT 1",
        "scan_generation": "INTEGER NOT NULL DEFAULT 0",
        "content_changed_at": "TEXT",
        "missing_at": "TEXT",
        "review_sha256": "TEXT",
    }
    for name, declaration in additions.items():
        if name not in asset_columns:
            conn.execute(f"ALTER TABLE assets ADD COLUMN {name} {declaration}")
    for row in conn.execute("SELECT rowid FROM assets WHERE asset_id IS NULL OR asset_id='' ").fetchall():
        conn.execute("UPDATE assets SET asset_id=? WHERE rowid=?", (str(uuid.uuid4()), row["rowid"]))
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_asset_id ON assets(asset_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_collection_present ON assets(collection, present, rel)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_collection_inode ON assets(collection, device, inode)")

    event_columns = {row["name"] for row in conn.execute("PRAGMA table_info(review_events)")}
    if "asset_id" not in event_columns:
        conn.execute("ALTER TABLE review_events ADD COLUMN asset_id TEXT")
    if "details" not in event_columns:
        conn.execute("ALTER TABLE review_events ADD COLUMN details TEXT NOT NULL DEFAULT '{}'")
    conn.execute(
        """
        UPDATE review_events
        SET asset_id=(
            SELECT assets.asset_id FROM assets
            WHERE assets.collection=review_events.collection AND assets.rel=review_events.rel
        )
        WHERE asset_id IS NULL
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_review_events_asset_id ON review_events(asset_id, id DESC)")

    state_columns = {row["name"] for row in conn.execute("PRAGMA table_info(catalog_state)")}
    state_additions = {
        "changed_at": "TEXT",
        "added": "INTEGER NOT NULL DEFAULT 0",
        "changed": "INTEGER NOT NULL DEFAULT 0",
        "removed": "INTEGER NOT NULL DEFAULT 0",
        "renamed": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, declaration in state_additions.items():
        if name not in state_columns:
            conn.execute(f"ALTER TABLE catalog_state ADD COLUMN {name} {declaration}")


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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collections() -> list[dict[str, Any]]:
    """Return configured collections, including temporarily unavailable paths."""
    rows = _load_json(registry_path(), [])
    valid: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        try:
            path = Path(row["path"]).expanduser().resolve()
            valid.append({
                "slug": str(row["slug"]),
                "label": str(row["label"]),
                "path": str(path),
                "available": path.is_dir(),
            })
        except (KeyError, TypeError, OSError):
            continue
    return valid


def add_collection(path: str, label: str | None = None) -> dict[str, Any]:
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
    row = {"slug": slug, "label": label, "path": str(resolved), "available": True}
    rows = [r for r in rows if Path(r["path"]) != resolved]
    rows.append(row)
    rows.sort(key=lambda r: r["label"].lower())
    _atomic_json(registry_path(), [{"slug": r["slug"], "label": r["label"], "path": r["path"]} for r in rows])
    return row


def remove_collection(key: str) -> dict[str, Any]:
    rows = collections()
    try:
        resolved_key = str(Path(key).expanduser().resolve())
    except OSError:
        resolved_key = key
    match = next((r for r in rows if r["slug"] == key or r["path"] == resolved_key), None)
    if not match:
        raise ValueError(f"collection not found: {key}")
    kept = [r for r in rows if r != match]
    _atomic_json(registry_path(), [{"slug": r["slug"], "label": r["label"], "path": r["path"]} for r in kept])
    return match


def root_for(slug: str) -> Path | None:
    row = next((r for r in collections() if r["slug"] == slug), None)
    if not row or not row.get("available"):
        return None
    return Path(row["path"])


def asset_rel(collection: str, asset_id: str) -> str | None:
    if not asset_id:
        return None
    with _connection() as conn:
        row = conn.execute(
            "SELECT rel FROM assets WHERE collection=? AND asset_id=? AND present=1",
            (collection, asset_id),
        ).fetchone()
    return str(row["rel"]) if row else None


def safe_file(slug: str, relative: str) -> Path | None:
    root = root_for(slug)
    if not root:
        return None
    try:
        # SECURITY: reject absolute/traversal components before joining, then
        # resolve and enforce containment. Symlinks that escape the root fail
        # the post-resolution parent check.
        relative_path = Path(relative)
        if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
            return None
        if relative_path.suffix.lower() not in IMAGE_EXTS:
            return None
        path = (root / relative_path).resolve()
        if path == root or root not in path.parents or not path.is_file():
            return None
        return path
    except (OSError, ValueError):
        return None


def ensure_assets(collection: str, relatives: Iterable[str]) -> None:
    unique = sorted({str(rel) for rel in relatives if rel})
    if not unique:
        return
    now = utc_now()
    with _connection() as conn:
        for rel in unique:
            conn.execute(
                """
                INSERT INTO assets(
                    collection, rel, status, comment, first_seen_at, seen_at, updated_at, asset_id, present
                ) VALUES(?, ?, '', '', ?, NULL, ?, ?, 1)
                ON CONFLICT(collection, rel) DO UPDATE SET present=1
                """,
                (collection, rel, now, now, str(uuid.uuid4())),
            )


def catalog_state(collection: str) -> dict[str, Any]:
    with _connection() as conn:
        row = conn.execute(
            """
            SELECT generation, last_scan_at, changed_at, truncated, reason, elapsed_ms,
                   added, changed, removed, renamed
            FROM catalog_state WHERE collection=?
            """,
            (collection,),
        ).fetchone()
    if not row:
        return {
            "collection": collection, "generation": 0, "last_scan_at": None, "changed_at": None,
            "truncated": False, "reason": None, "elapsed_ms": 0,
            "added": 0, "changed": 0, "removed": 0, "renamed": 0,
        }
    return {
        "collection": collection,
        "generation": int(row["generation"]),
        "last_scan_at": row["last_scan_at"],
        "changed_at": row["changed_at"],
        "truncated": bool(row["truncated"]),
        "reason": row["reason"],
        "elapsed_ms": int(row["elapsed_ms"] or 0),
        "added": int(row["added"] or 0),
        "changed": int(row["changed"] or 0),
        "removed": int(row["removed"] or 0),
        "renamed": int(row["renamed"] or 0),
    }

def catalog_records(collection: str, present_only: bool = True) -> list[dict[str, Any]]:
    query = """
        SELECT asset_id, collection, rel, status, comment, first_seen_at, seen_at, updated_at,
               device, inode, size, mtime_ns, width, height, preview_error, present, scan_generation,
               content_changed_at, missing_at, review_sha256
        FROM assets WHERE collection=?
    """
    args: list[Any] = [collection]
    if present_only:
        query += " AND present=1"
    query += " ORDER BY COALESCE(mtime_ns, 0) DESC, rel COLLATE NOCASE"
    with _connection() as conn:
        return [dict(row) for row in conn.execute(query, tuple(args))]


def _record_system_event(
    conn: sqlite3.Connection, collection: str, rel: str, asset_id: str | None,
    action: str, now: str, details: dict[str, Any] | None = None,
    *, old_status: str = "", new_status: str = "", old_comment: str = "", new_comment: str = "",
) -> None:
    conn.execute(
        """INSERT INTO review_events(
            collection, rel, action, old_status, new_status, old_comment, new_comment, created_at, asset_id, details
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (collection, rel, action, old_status, new_status, old_comment, new_comment, now, asset_id,
         json.dumps(details or {}, separators=(",", ":"), sort_keys=True)),
    )


def reconcile_catalog(
    collection: str,
    discoveries: Iterable[dict[str, Any]],
    *,
    truncated: bool,
    reason: str | None,
    elapsed_ms: int,
) -> dict[str, Any]:
    """Reconcile a filesystem scan into the durable catalog.

    Review state follows stable asset IDs across same-filesystem renames. A
    content replacement at an existing path invalidates the old decision, and
    a truncated scan never marks unseen rows missing.
    """
    now = utc_now()
    rows = list(discoveries)
    discovered_rels = {str(item["rel"]) for item in rows}
    added = changed = removed = renamed = restored = 0
    with _connection() as conn:
        previous_state = conn.execute(
            "SELECT generation, changed_at FROM catalog_state WHERE collection=?", (collection,)
        ).fetchone()
        generation = int(previous_state["generation"] if previous_state else 0) + 1
        existing = conn.execute("SELECT * FROM assets WHERE collection=?", (collection,)).fetchall()
        by_rel = {row["rel"]: row for row in existing}
        by_identity: dict[tuple[int, int], list[sqlite3.Row]] = {}
        for row in existing:
            if row["device"] and row["inode"]:
                by_identity.setdefault((int(row["device"]), int(row["inode"])), []).append(row)
        used_ids: set[str] = set()

        for item in rows:
            rel = str(item["rel"])
            device = int(item.get("device") or 0)
            inode = int(item.get("inode") or 0)
            size = int(item.get("size") or 0)
            mtime_ns = int(item.get("mtime_ns") or 0)
            target = by_rel.get(rel)
            renamed_from: str | None = None
            if target is None and device and inode:
                candidates = [
                    row for row in by_identity.get((device, inode), [])
                    if row["asset_id"] not in used_ids and row["rel"] not in discovered_rels
                ]
                if len(candidates) == 1:
                    target = candidates[0]
                    renamed_from = str(target["rel"])
                    conn.execute("UPDATE assets SET rel=? WHERE asset_id=?", (rel, target["asset_id"]))
                    conn.execute(
                        "UPDATE review_events SET rel=?, asset_id=COALESCE(asset_id, ?) WHERE collection=? AND rel=?",
                        (rel, target["asset_id"], collection, renamed_from),
                    )
                    _record_system_event(conn, collection, rel, str(target["asset_id"]), "asset_renamed", now, {"old_rel": renamed_from, "new_rel": rel})
                    renamed += 1

            if target is None:
                asset_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO assets(
                        collection, rel, status, comment, first_seen_at, seen_at, updated_at, asset_id,
                        device, inode, size, mtime_ns, width, height, preview_error, present, scan_generation,
                        content_changed_at, missing_at
                    ) VALUES(?, ?, '', '', ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, NULL)
                    """,
                    (collection, rel, now, now, asset_id, device or None, inode or None, size, mtime_ns,
                     item.get("width"), item.get("height"), item.get("preview_error"), generation, now),
                )
                _record_system_event(conn, collection, rel, asset_id, "asset_added", now)
                added += 1
                used_ids.add(asset_id)
                continue

            asset_id = str(target["asset_id"])
            used_ids.add(asset_id)
            was_present = bool(target["present"])
            metadata_known = target["size"] is not None and target["mtime_ns"] is not None
            content_changed = metadata_known and (int(target["size"]) != size or int(target["mtime_ns"]) != mtime_ns)
            if not was_present:
                _record_system_event(conn, collection, rel, asset_id, "asset_restored", now)
                restored += 1
            if content_changed:
                old_status = str(target["status"] or "")
                old_comment = str(target["comment"] or "")
                conn.execute(
                    """
                    UPDATE assets SET status='', comment='', seen_at=NULL, updated_at=?, content_changed_at=?, review_sha256=NULL
                    WHERE asset_id=?
                    """,
                    (now, now, asset_id),
                )
                _record_system_event(
                    conn, collection, rel, asset_id, "content_changed", now,
                    {"old_size": target["size"], "new_size": size, "old_mtime_ns": target["mtime_ns"], "new_mtime_ns": mtime_ns},
                    old_status=old_status, new_status="", old_comment=old_comment, new_comment="",
                )
                changed += 1
            conn.execute(
                """
                UPDATE assets SET device=?, inode=?, size=?, mtime_ns=?, width=?, height=?, preview_error=?,
                                  present=1, scan_generation=?, missing_at=NULL
                WHERE asset_id=?
                """,
                (device or None, inode or None, size, mtime_ns, item.get("width"), item.get("height"),
                 item.get("preview_error"), generation, asset_id),
            )

        if not truncated:
            missing_rows = conn.execute(
                "SELECT asset_id, rel FROM assets WHERE collection=? AND present=1 AND scan_generation<>?",
                (collection, generation),
            ).fetchall()
            removed = len(missing_rows)
            if missing_rows:
                conn.executemany(
                    "UPDATE assets SET present=0, missing_at=? WHERE asset_id=?",
                    [(now, row["asset_id"]) for row in missing_rows],
                )
                for row in missing_rows:
                    _record_system_event(conn, collection, row["rel"], row["asset_id"], "asset_missing", now)

        meaningful_change = bool(added or changed or removed or restored)
        changed_at = now if meaningful_change else (previous_state["changed_at"] if previous_state else None)
        conn.execute(
            """
            INSERT INTO catalog_state(
                collection, generation, last_scan_at, changed_at, truncated, reason, elapsed_ms,
                added, changed, removed, renamed
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(collection) DO UPDATE SET
                generation=excluded.generation, last_scan_at=excluded.last_scan_at, changed_at=excluded.changed_at,
                truncated=excluded.truncated, reason=excluded.reason, elapsed_ms=excluded.elapsed_ms,
                added=excluded.added, changed=excluded.changed, removed=excluded.removed, renamed=excluded.renamed
            """,
            (collection, generation, now, changed_at, int(truncated), reason, int(elapsed_ms),
             added + restored, changed, removed, renamed),
        )
    return catalog_state(collection)

def review_records(collection: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    query = "SELECT asset_id, collection, rel, status, comment, first_seen_at, seen_at, updated_at, present, size, mtime_ns, width, height, content_changed_at, missing_at, review_sha256 FROM assets"
    args: tuple[Any, ...] = ()
    if collection is not None:
        query += " WHERE collection=?"
        args = (collection,)
    query += " ORDER BY collection, rel"
    out: dict[str, dict[str, dict[str, Any]]] = {}
    with _connection() as conn:
        for row in conn.execute(query, args):
            out.setdefault(row["collection"], {})[row["rel"]] = {
                "asset_id": row["asset_id"],
                "status": row["status"],
                "comment": row["comment"],
                "first_seen_at": row["first_seen_at"],
                "seen_at": row["seen_at"],
                "updated_at": row["updated_at"],
                "present": bool(row["present"]),
                "size": row["size"],
                "mtime_ns": row["mtime_ns"],
                "width": row["width"],
                "height": row["height"],
                "review_sha256": row["review_sha256"],
                "content_changed_at": row["content_changed_at"],
                "missing_at": row["missing_at"],
                "review_sha256": row["review_sha256"],
            }
    return out


def reviews() -> dict[str, dict[str, str]]:
    """Backward-compatible status-only view of review state."""
    records = review_records()
    return {
        collection: {rel: data["status"] for rel, data in rows.items() if data["status"] and data.get("present", True)}
        for collection, rows in records.items()
    }


def _record_review_event(
    conn: sqlite3.Connection,
    collection: str,
    relative: str,
    action: str,
    old_status: str,
    new_status: str,
    old_comment: str,
    new_comment: str,
    now: str,
    force: bool = False,
) -> None:
    if not force and old_status == new_status and old_comment == new_comment:
        return
    asset = conn.execute(
        "SELECT asset_id FROM assets WHERE collection=? AND rel=?", (collection, relative)
    ).fetchone()
    asset_id = asset["asset_id"] if asset else None
    conn.execute(
        """
        INSERT INTO review_events(
            collection, rel, action, old_status, new_status, old_comment, new_comment, created_at, asset_id
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (collection, relative, action, old_status, new_status, old_comment, new_comment, now, asset_id),
    )


def review_history(collection: str, relative: str, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with _connection() as conn:
        asset = conn.execute(
            "SELECT asset_id FROM assets WHERE collection=? AND rel=?", (collection, relative)
        ).fetchone()
        if asset:
            rows = conn.execute(
                """
                SELECT id, action, old_status, new_status, old_comment, new_comment, created_at, undone_at, asset_id, details
                FROM review_events
                WHERE (asset_id=? OR (asset_id IS NULL AND collection=? AND rel=?))
                  AND action IN ('review', 'batch', 'comment', 'content_changed')
                ORDER BY id DESC LIMIT ?
                """,
                (asset["asset_id"], collection, relative, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, action, old_status, new_status, old_comment, new_comment, created_at, undone_at, asset_id, details
                FROM review_events WHERE collection=? AND rel=?
                  AND action IN ('review', 'batch', 'comment', 'content_changed')
                ORDER BY id DESC LIMIT ?
                """,
                (collection, relative, limit),
            ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        try:
            item["details"] = json.loads(item.get("details") or "{}")
        except (TypeError, json.JSONDecodeError):
            item["details"] = {}
        out.append(item)
    return out


def undo_last_review(collection: str, relative: str) -> dict[str, Any] | None:
    now = utc_now()
    source = safe_file(collection, relative)
    with _connection() as conn:
        asset = conn.execute(
            "SELECT asset_id FROM assets WHERE collection=? AND rel=?", (collection, relative)
        ).fetchone()
        if not asset:
            return None
        event = conn.execute(
            """
            SELECT id, old_status, old_comment, new_status, new_comment
            FROM review_events
            WHERE (asset_id=? OR (asset_id IS NULL AND collection=? AND rel=?))
              AND action IN ('review', 'batch', 'comment') AND undone_at IS NULL
              AND id > COALESCE((SELECT MAX(id) FROM review_events WHERE asset_id=? AND action='content_changed'), 0)
            ORDER BY id DESC LIMIT 1
            """,
            (asset["asset_id"], collection, relative, asset["asset_id"]),
        ).fetchone()
        if not event:
            return None
        conn.execute(
            "UPDATE assets SET status=?, comment=?, review_sha256=?, updated_at=? WHERE asset_id=?",
            (event["old_status"], event["old_comment"], file_sha256(source) if event["old_status"] and source else None, now, asset["asset_id"]),
        )
        conn.execute("UPDATE review_events SET undone_at=? WHERE id=?", (now, event["id"]))
        return {
            "event_id": event["id"],
            "asset_id": asset["asset_id"],
            "status": event["old_status"],
            "comment": event["old_comment"],
            "undone_at": now,
        }


def set_review(collection: str, relative: str, status: str, comment: str | None = None, mark_seen: bool = True) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid review status: {status}")
    source = safe_file(collection, relative)
    review_sha256 = file_sha256(source) if status and source else None
    ensure_assets(collection, [relative])
    now = utc_now()
    with _connection() as conn:
        current = conn.execute(
            "SELECT status, comment FROM assets WHERE collection=? AND rel=?", (collection, relative)
        ).fetchone()
        if not current:
            raise ValueError("asset review state not found")
        old_status, old_comment = current["status"], current["comment"]
        new_comment = old_comment if comment is None else str(comment)[:10000]
        conn.execute(
            """
            UPDATE assets
            SET status=?, comment=?, review_sha256=?, seen_at=CASE WHEN ? THEN COALESCE(seen_at, ?) ELSE seen_at END, updated_at=?
            WHERE collection=? AND rel=?
            """,
            (status, new_comment, review_sha256, int(mark_seen), now, now, collection, relative),
        )
        _record_review_event(conn, collection, relative, "review", old_status, status, old_comment, new_comment, now)


def set_reviews_batch(collection: str, relatives: Iterable[str], status: str) -> int:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid review status: {status}")
    unique = sorted({str(rel) for rel in relatives if rel})
    if not unique:
        return 0
    review_hashes = {}
    if status:
        for rel in unique:
            source = safe_file(collection, rel)
            review_hashes[rel] = file_sha256(source) if source else None
    ensure_assets(collection, unique)
    now = utc_now()
    changed = 0
    with _connection() as conn:
        for rel in unique:
            current = conn.execute(
                "SELECT status, comment FROM assets WHERE collection=? AND rel=?", (collection, rel)
            ).fetchone()
            if not current:
                continue
            conn.execute(
                "UPDATE assets SET status=?, review_sha256=?, seen_at=COALESCE(seen_at, ?), updated_at=? WHERE collection=? AND rel=?",
                (status, review_hashes.get(rel) if status else None, now, now, collection, rel),
            )
            _record_review_event(
                conn, collection, rel, "batch", current["status"], status, current["comment"], current["comment"], now
            )
            changed += 1
    return changed


def set_comment(collection: str, relative: str, comment: str) -> None:
    ensure_assets(collection, [relative])
    now = utc_now()
    new_comment = str(comment)[:10000]
    with _connection() as conn:
        current = conn.execute(
            "SELECT status, comment FROM assets WHERE collection=? AND rel=?", (collection, relative)
        ).fetchone()
        if not current:
            raise ValueError("asset review state not found")
        conn.execute(
            "UPDATE assets SET comment=?, seen_at=COALESCE(seen_at, ?), updated_at=? WHERE collection=? AND rel=?",
            (new_comment, now, now, collection, relative),
        )
        _record_review_event(
            conn, collection, relative, "comment", current["status"], current["status"], current["comment"], new_comment, now
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


def review_events_since(collection: str | None = None, after_id: int = 0, limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(int(limit), 500))
    after_id = max(0, int(after_id))
    rows: list[dict[str, Any]] = []
    with _connection() as conn:
        if collection:
            cursor = conn.execute(
                """
                SELECT id, collection, rel, asset_id, action, old_status, new_status,
                       old_comment, new_comment, created_at, undone_at, details
                FROM review_events
                WHERE id>? AND collection=?
                ORDER BY id ASC LIMIT ?
                """,
                (after_id, collection, limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, collection, rel, asset_id, action, old_status, new_status,
                       old_comment, new_comment, created_at, undone_at, details
                FROM review_events
                WHERE id>?
                ORDER BY id ASC LIMIT ?
                """,
                (after_id, limit),
            )
        for row in cursor:
            item = dict(row)
            try:
                item["details"] = json.loads(item.get("details") or "{}")
            except (TypeError, json.JSONDecodeError):
                item["details"] = {}
            rows.append(item)
        newest = conn.execute("SELECT COALESCE(MAX(id), 0) AS value FROM review_events").fetchone()["value"]
    return {
        "version": 1,
        "generated_at": utc_now(),
        "after_id": after_id,
        "last_event_id": int(rows[-1]["id"] if rows else after_id),
        "newest_event_id": int(newest or 0),
        "events": rows,
    }

def _record_collection_event(conn: sqlite3.Connection, collection: str, action: str, now: str) -> None:
    conn.execute(
        """
        INSERT INTO review_events(
            collection, rel, action, old_status, new_status, old_comment, new_comment, created_at, asset_id
        ) VALUES(?, '', ?, '', '', '', '', ?, NULL)
        """,
        (collection, action, now),
    )


def verify_review_fingerprints(collection: str, *, bind_missing: bool = False) -> int:
    """Invalidate decisions whose current bytes no longer match the reviewed bytes."""
    now = utc_now()
    with _connection() as conn:
        rows = conn.execute(
            "SELECT asset_id, rel, status, comment, review_sha256 FROM assets WHERE collection=? AND present=1 AND status<>''",
            (collection,),
        ).fetchall()
    mismatches: list[tuple[sqlite3.Row, str]] = []
    bindings: list[tuple[str, str]] = []
    for row in rows:
        source = safe_file(collection, row["rel"])
        if not source:
            raise ValueError(f"reviewed asset unavailable; rescan required: {row['rel']}")
        current = file_sha256(source)
        expected = row["review_sha256"]
        if not expected:
            if bind_missing:
                bindings.append((current, row["asset_id"]))
            continue
        if not hmac.compare_digest(str(expected), current):
            mismatches.append((row, current))
    if not bindings and not mismatches:
        return 0
    with _connection() as conn:
        for digest, asset_id in bindings:
            conn.execute("UPDATE assets SET review_sha256=? WHERE asset_id=?", (digest, asset_id))
        for row, current in mismatches:
            conn.execute(
                "UPDATE assets SET status='', comment='', review_sha256=NULL, seen_at=NULL, updated_at=?, content_changed_at=? WHERE asset_id=?",
                (now, now, row["asset_id"]),
            )
            _record_system_event(
                conn, collection, row["rel"], row["asset_id"], "content_changed", now,
                {"reason": "review_sha256_mismatch", "observed_sha256": current},
                old_status=row["status"], new_status="", old_comment=row["comment"], new_comment="",
            )
    return len(mismatches)


def collection_review_state(collection: str) -> dict[str, Any]:
    with _connection() as conn:
        state = conn.execute(
            "SELECT completed_at, updated_at FROM collection_state WHERE collection=?", (collection,)
        ).fetchone()
        counts = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status='' THEN 1 ELSE 0 END) AS unreviewed,
                   SUM(CASE WHEN seen_at IS NULL THEN 1 ELSE 0 END) AS new_count,
                   MAX(COALESCE(content_changed_at, first_seen_at)) AS newest_content
            FROM assets WHERE collection=? AND present=1
            """,
            (collection,),
        ).fetchone()
        scan = conn.execute(
            "SELECT last_scan_at, changed_at, truncated, reason FROM catalog_state WHERE collection=?",
            (collection,),
        ).fetchone()
    completed_at = state["completed_at"] if state else None
    total = int(counts["total"] or 0)
    unreviewed = int(counts["unreviewed"] or 0)
    new_count = int(counts["new_count"] or 0)
    newest_content = counts["newest_content"]
    changed_at = scan["changed_at"] if scan else None
    scan_incomplete = bool(scan and scan["truncated"])
    stale = bool(completed_at and (
        (newest_content and newest_content > completed_at) or (changed_at and changed_at > completed_at)
    ))
    complete = bool(completed_at and total > 0 and unreviewed == 0 and not stale and not scan_incomplete)
    return {
        "collection": collection,
        "completed_at": completed_at,
        "updated_at": state["updated_at"] if state else None,
        "total": total,
        "unreviewed": unreviewed,
        "new": new_count,
        "empty": total == 0,
        "stale": stale,
        "scan_incomplete": scan_incomplete,
        "scan_reason": scan["reason"] if scan else None,
        "last_scan_at": scan["last_scan_at"] if scan else None,
        "complete": complete,
        "pending": not complete,
    }

def complete_collection_review(collection: str) -> dict[str, Any]:
    verify_review_fingerprints(collection, bind_missing=True)
    state = collection_review_state(collection)
    if state["scan_incomplete"]:
        raise ValueError(f"latest collection scan is incomplete ({state['scan_reason'] or 'unknown reason'})")
    if state["total"] == 0:
        raise ValueError("collection has no present assets to review")
    if state["unreviewed"]:
        raise ValueError(f"collection has {state['unreviewed']} unreviewed asset(s)")
    now = utc_now()
    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO collection_state(collection, completed_at, updated_at) VALUES(?, ?, ?)
            ON CONFLICT(collection) DO UPDATE SET completed_at=excluded.completed_at, updated_at=excluded.updated_at
            """,
            (collection, now, now),
        )
        _record_collection_event(conn, collection, "collection_complete", now)
    return collection_review_state(collection)


def reopen_collection_review(collection: str) -> dict[str, Any]:
    now = utc_now()
    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO collection_state(collection, completed_at, updated_at) VALUES(?, NULL, ?)
            ON CONFLICT(collection) DO UPDATE SET completed_at=NULL, updated_at=excluded.updated_at
            """,
            (collection, now),
        )
        _record_collection_event(conn, collection, "collection_reopen", now)
    return collection_review_state(collection)


def pending_summary(collection: str | None = None) -> dict[str, Any]:
    rows = collections()
    if collection:
        rows = [row for row in rows if row["slug"] == collection]
        if not rows:
            raise ValueError(f"collection not found: {collection}")
    states = [collection_review_state(row["slug"]) | {"label": row["label"]} for row in rows]
    return {
        "version": 1,
        "generated_at": utc_now(),
        "pending": any(state["pending"] for state in states),
        "collections": states,
    }


def review_manifest(collection: str | None = None, status: str | None = None, include_missing: bool = True) -> dict[str, Any]:
    if status is not None and status not in VALID_STATUSES | {"unreviewed", "new"}:
        raise ValueError(f"invalid manifest status: {status}")
    labels = {row["slug"]: row["label"] for row in collections()}
    query = "SELECT asset_id, collection, rel, status, comment, first_seen_at, seen_at, updated_at, present, size, mtime_ns, width, height, content_changed_at, missing_at, review_sha256 FROM assets"
    clauses: list[str] = []
    args: list[Any] = []
    if not include_missing:
        clauses.append("present=1")
    if collection:
        clauses.append("collection=?")
        args.append(collection)
    if status == "unreviewed":
        clauses.append("status=''")
    elif status == "new":
        clauses.append("seen_at IS NULL")
        clauses.append("present=1")
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
                "asset_id": row["asset_id"],
                "collection": row["collection"],
                "collection_label": labels.get(row["collection"], row["collection"]),
                "rel": row["rel"],
                "status": row["status"],
                "comment": row["comment"],
                "first_seen_at": row["first_seen_at"],
                "seen_at": row["seen_at"],
                "updated_at": row["updated_at"],
                "present": bool(row["present"]),
                "size": row["size"],
                "mtime_ns": row["mtime_ns"],
                "width": row["width"],
                "height": row["height"],
            })
    counts = {"total": len(items), "present": 0, "missing": 0, "approved": 0, "maybe": 0, "rejected": 0, "unreviewed": 0, "new": 0}
    for item in items:
        counts["present" if item["present"] else "missing"] += 1
        counts[item["status"] or "unreviewed"] += 1
        if item["present"] and item["seen_at"] is None:
            counts["new"] += 1
    return {"version": 1, "generated_at": utc_now(), "counts": counts, "items": items}


def _render_cache_path(source: Path, purpose: str) -> Path:
    stat = source.stat()
    key = hashlib.sha256(f"{purpose}:{source}:{stat.st_mtime_ns}:{stat.st_size}".encode()).hexdigest()
    return cache_dir() / f"{purpose}-{key}.jpg"


def thumb_path(source: Path) -> Path:
    return _render_cache_path(source, "thumb")


def preview_path(source: Path) -> Path:
    return _render_cache_path(source, "preview")
