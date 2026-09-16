from __future__ import annotations

from pathlib import Path
from typing import Any

from .app import scan_collection
from .metadata_adapters import import_collection_metadata
from .project_config import load_project_config
from .storage import add_collection


def sync_project(start: str | Path = ".", *, dry_run: bool = False) -> dict[str, Any]:
    config = load_project_config(start)
    results = []
    for declared in config["collections"]:
        result = {
            "relative_path": declared["relative_path"],
            "path": declared["path"],
            "label": declared["label"],
            "group": declared["group"],
            "available": declared["available"],
            "adapters": list(declared["adapters"]),
            "registered": False,
            "collection": None,
            "scan": None,
            "metadata": None,
        }
        if dry_run or not declared["available"]:
            results.append(result)
            continue
        row = add_collection(declared["path"], declared["label"], declared["group"])
        _, scan = scan_collection(row["slug"], force=True)
        metadata = import_collection_metadata(row["slug"], declared["adapters"], declared["metadata"])
        result.update({"registered": True, "collection": row["slug"], "scan": scan, "metadata": metadata})
        results.append(result)
    return {
        "version": 1,
        "project": config["project"],
        "root": config["root"],
        "config_path": config["config_path"],
        "dry_run": dry_run,
        "collections": results,
    }
