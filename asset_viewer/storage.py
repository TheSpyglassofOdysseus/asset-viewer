from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".bmp", ".svg"}


def data_dir() -> Path:
    override = os.environ.get("ASSET_VIEWER_HOME")
    root = Path(override).expanduser() if override else Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "asset-viewer"
    root.mkdir(parents=True, exist_ok=True)
    return root


def cache_dir() -> Path:
    override = os.environ.get("ASSET_VIEWER_CACHE")
    root = Path(override).expanduser() if override else Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "asset-viewer"
    root.mkdir(parents=True, exist_ok=True)
    return root


def registry_path() -> Path:
    return data_dir() / "collections.json"


def reviews_path() -> Path:
    return data_dir() / "reviews.json"


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


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
    label = label or resolved.name.replace("-", " ").replace("_", " ").title()
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
    match = next((r for r in rows if r["slug"] == key or r["path"] == str(Path(key).expanduser().resolve())), None)
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
        path = (root / relative).resolve()
        if path == root or root not in path.parents or not path.is_file():
            return None
        return path
    except OSError:
        return None


def reviews() -> dict[str, dict[str, str]]:
    data = _load_json(reviews_path(), {})
    return data if isinstance(data, dict) else {}


def set_review(slug: str, relative: str, status: str) -> None:
    data = reviews()
    data.setdefault(slug, {})
    if status:
        data[slug][relative] = status
    else:
        data[slug].pop(relative, None)
    _atomic_json(reviews_path(), data)


def thumb_path(source: Path) -> Path:
    stat = source.stat()
    key = hashlib.sha256(f"{source}:{stat.st_mtime_ns}:{stat.st_size}".encode()).hexdigest()
    return cache_dir() / f"{key}.jpg"
