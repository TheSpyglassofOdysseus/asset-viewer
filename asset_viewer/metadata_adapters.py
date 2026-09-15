from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .app import MAX_THUMBNAIL_SOURCE_BYTES, PREVIEW_PROCESS_TIMEOUT_SECONDS, PREVIEW_WORKER_MEMORY_BYTES, _run_isolated_worker
from .preview_worker import inspect_png_text_worker
from .storage import catalog_records, safe_file, set_asset_metadata

KNOWN_FIELDS = {"source_project", "tool", "agent", "model", "prompt", "seed", "run_id", "git_commit", "parent_asset_id"}
MAX_SIDECAR_BYTES = 256 * 1024


def _merge_metadata(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    base_extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
    incoming_extra = incoming.get("extra") if isinstance(incoming.get("extra"), dict) else {}
    for key, value in incoming.items():
        if key == "extra":
            continue
        if value not in (None, ""):
            result[key] = value
    result["extra"] = dict(base_extra) | dict(incoming_extra)
    return result


def normalize_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("metadata payload must be an object")
    result: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for key, value in raw.items():
        if key in KNOWN_FIELDS:
            result[key] = value
        elif key == "extra" and isinstance(value, dict):
            extra.update(value)
        else:
            extra[key] = value
    if extra:
        result["extra"] = extra
    return result


def read_sidecar(source: Path) -> dict[str, Any]:
    sidecar = source.with_name(source.name + ".asset-viewer.json")
    if not sidecar.is_file():
        return {}
    if sidecar.is_symlink():
        raise ValueError(f"metadata sidecar must not be a symlink: {sidecar.name}")
    if sidecar.stat().st_size > MAX_SIDECAR_BYTES:
        raise ValueError(f"metadata sidecar is too large: {sidecar.name}")
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid metadata sidecar {sidecar.name}: {exc}") from exc
    if not isinstance(payload, dict) or int(payload.get("version", 0)) != 1:
        raise ValueError(f"metadata sidecar {sidecar.name} must be a version 1 object")
    provenance = payload.get("provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError(f"metadata sidecar {sidecar.name} provenance must be an object")
    metadata = normalize_metadata(provenance)
    arbitrary = payload.get("metadata", {})
    if arbitrary is not None:
        if not isinstance(arbitrary, dict):
            raise ValueError(f"metadata sidecar {sidecar.name} metadata must be an object")
        metadata = _merge_metadata(metadata, {"extra": arbitrary})
    return metadata


def _a1111_metadata(parameters: str) -> dict[str, Any]:
    lines = parameters.splitlines()
    prompt_lines = []
    for line in lines:
        if line.startswith("Negative prompt:") or re.match(r"^Steps:\s*\d+", line):
            break
        prompt_lines.append(line)
    metadata: dict[str, Any] = {"tool": "automatic1111", "prompt": "\n".join(prompt_lines).strip()}
    seed = re.search(r"(?:^|,\s*)Seed:\s*([^,\n]+)", parameters)
    model = re.search(r"(?:^|,\s*)Model:\s*([^,\n]+)", parameters)
    if seed:
        metadata["seed"] = seed.group(1).strip()
    if model:
        metadata["model"] = model.group(1).strip()
    metadata["extra"] = {"automatic1111_parameters": parameters}
    return metadata


def png_text_metadata(source: Path) -> dict[str, Any]:
    payload = _run_isolated_worker(
        inspect_png_text_worker,
        (str(source), MAX_THUMBNAIL_SOURCE_BYTES, PREVIEW_WORKER_MEMORY_BYTES),
        PREVIEW_PROCESS_TIMEOUT_SECONDS,
    )
    if not payload.get("ok"):
        return {}
    info = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if not info:
        return {}
    if isinstance(info.get("parameters"), str) and info["parameters"].strip():
        return _a1111_metadata(info["parameters"])
    result: dict[str, Any] = {"extra": {"png_text": info}}
    if "workflow" in info or "prompt" in info:
        result["tool"] = "comfyui"
    for candidate in ("Description", "description", "Comment", "comment"):
        if isinstance(info.get(candidate), str) and info[candidate].strip():
            result["prompt"] = info[candidate].strip()
            break
    return result


def import_collection_metadata(collection: str, adapters: list[str], defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    imported = skipped = 0
    errors: list[dict[str, str]] = []
    defaults = normalize_metadata(defaults or {})
    for record in catalog_records(collection, present_only=True):
        source = safe_file(collection, record["rel"])
        if not source:
            skipped += 1
            continue
        metadata = dict(defaults)
        try:
            if "png_text" in adapters and source.suffix.lower() == ".png":
                metadata = _merge_metadata(metadata, png_text_metadata(source))
            if "sidecar" in adapters:
                metadata = _merge_metadata(metadata, read_sidecar(source))
            meaningful = any(value not in (None, "", {}) for value in metadata.values())
            if meaningful:
                set_asset_metadata(collection, record["asset_id"], metadata)
                imported += 1
            else:
                skipped += 1
        except (OSError, ValueError) as exc:
            errors.append({"rel": record["rel"], "error": str(exc)})
    return {"collection": collection, "imported": imported, "skipped": skipped, "errors": errors}
