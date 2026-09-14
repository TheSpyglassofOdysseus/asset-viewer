from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .storage import file_sha256, review_manifest, safe_file, utc_now


def _verified_source(collection: str, item: dict[str, Any]) -> Path:
    rel = str(item["rel"])
    source = safe_file(collection, rel)
    expected = str(item.get("review_sha256") or "")
    if not source or not expected:
        raise ValueError(f"approved asset is unavailable or lacks a review fingerprint: {rel}")
    if file_sha256(source) != expected:
        raise ValueError(f"approved asset bytes changed since review: {rel}")
    return source


def approved_handoff(collection: str) -> dict[str, Any]:
    manifest = review_manifest(collection, "approved", include_missing=False)
    items = []
    for item in manifest["items"]:
        _verified_source(collection, item)
        items.append({
            "asset_id": item["asset_id"],
            "collection": collection,
            "rel": item["rel"],
            "sha256": item.get("review_sha256"),
            "reviewed_at": item.get("updated_at"),
            "comment": item.get("comment") or "",
            "annotations": item.get("annotations") or [],
            "family": item.get("family"),
            "provenance": item.get("provenance") or {},
        })
    return {
        "version": 1,
        "generated_at": utc_now(),
        "collection": collection,
        "count": len(items),
        "items": items,
    }


def _copy_verified(source: Path, target: Path, expected_sha256: str, *, overwrite: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(f"approved-set target already exists: {target}")
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.asset-viewer-", dir=target.parent)
    temp = Path(temp_name)
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as out, source.open("rb") as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                digest.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if digest.hexdigest() != expected_sha256:
            raise ValueError(f"approved asset bytes changed during handoff: {source.name}")
        shutil.copystat(source, temp, follow_symlinks=False)
        if overwrite:
            os.replace(temp, target)
        else:
            try:
                os.link(temp, target)
            except FileExistsError:
                raise FileExistsError(f"approved-set target already exists: {target}")
            temp.unlink()
    finally:
        temp.unlink(missing_ok=True)


def copy_approved_set(collection: str, destination: str, *, overwrite: bool = False) -> dict[str, Any]:
    payload = approved_handoff(collection)
    target_root = Path(destination).expanduser().resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    copied = []
    for item in payload["items"]:
        source = safe_file(collection, str(item["rel"]))
        if not source:
            raise ValueError(f"approved asset became unavailable during handoff: {item['rel']}")
        target = (target_root / str(item["rel"])).resolve()
        if target_root not in target.parents:
            raise ValueError("approved-set destination escaped target root")
        _copy_verified(source, target, str(item["sha256"]), overwrite=overwrite)
        copied.append(str(target.relative_to(target_root)))
    return payload | {"destination": str(target_root), "copied": copied}
