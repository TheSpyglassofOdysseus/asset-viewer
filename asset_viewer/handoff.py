from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .storage import review_manifest, safe_file, utc_now


def approved_handoff(collection: str) -> dict[str, Any]:
    manifest = review_manifest(collection, "approved", include_missing=False)
    items = []
    for item in manifest["items"]:
        source = safe_file(collection, str(item["rel"]))
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


def copy_approved_set(collection: str, destination: str, *, overwrite: bool = False) -> dict[str, Any]:
    payload = approved_handoff(collection)
    target_root = Path(destination).expanduser().resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    copied = []
    for item in payload["items"]:
        source = safe_file(collection, str(item["rel"]))
        if not source:
            continue
        target = (target_root / str(item["rel"])).resolve()
        if target_root not in target.parents:
            raise ValueError("approved-set destination escaped target root")
        if target.exists() and not overwrite:
            raise FileExistsError(f"approved-set target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(str(target.relative_to(target_root)))
    return payload | {"destination": str(target_root), "copied": copied}
