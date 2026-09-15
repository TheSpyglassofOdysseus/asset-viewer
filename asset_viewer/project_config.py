from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 CI
    import tomli as tomllib

CONFIG_NAME = ".asset-viewer.toml"


def find_project_config(start: str | Path = ".") -> Path | None:
    candidate = Path(start).expanduser().resolve()
    if candidate.is_file():
        if candidate.name == CONFIG_NAME:
            return candidate
        candidate = candidate.parent
    for root in (candidate, *candidate.parents):
        config = root / CONFIG_NAME
        if config.is_file():
            return config
    return None


def _clean_metadata(value: Any, *, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a TOML table")
    return dict(value)


def load_project_config(start: str | Path = ".") -> dict[str, Any]:
    config_path = find_project_config(start)
    if not config_path:
        raise ValueError(f"{CONFIG_NAME} not found from {Path(start).expanduser()}")
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid {CONFIG_NAME}: {exc}") from exc
    allowed_top = {"version", "project", "group", "metadata", "collections"}
    unknown_top = set(payload) - allowed_top
    if unknown_top:
        raise ValueError("unsupported project config key(s): " + ", ".join(sorted(unknown_top)))
    if int(payload.get("version", 0)) != 1:
        raise ValueError(f"{CONFIG_NAME} version must be 1")
    project = str(payload.get("project") or config_path.parent.name).strip()
    if not project:
        raise ValueError("project name must not be empty")
    rows = payload.get("collections")
    if not isinstance(rows, list) or not rows:
        raise ValueError("project config requires at least one [[collections]] entry")
    defaults = _clean_metadata(payload.get("metadata"), field="metadata")
    normalized = []
    root = config_path.parent.resolve()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"collections entry {index} must be a TOML table")
        allowed_collection = {"path", "label", "group", "adapters", "metadata"}
        unknown_collection = set(row) - allowed_collection
        if unknown_collection:
            raise ValueError(f"collections entry {index} has unsupported key(s): " + ", ".join(sorted(unknown_collection)))
        raw_path = str(row.get("path") or "").strip()
        if not raw_path:
            raise ValueError(f"collections entry {index} requires path")
        relative = Path(raw_path)
        if relative.is_absolute() or any(part in {"..", ""} for part in relative.parts):
            raise ValueError(f"collections entry {index} path must be a project-relative path")
        resolved = (root / relative).resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"collections entry {index} escapes the project root")
        label = str(row.get("label") or relative.name.replace("-", " ").replace("_", " ").title()).strip()
        if not label:
            raise ValueError(f"collections entry {index} label must not be empty")
        group = str(row.get("group") or payload.get("group") or project).strip()
        adapters_raw = row.get("adapters", ["sidecar", "png_text"])
        if not isinstance(adapters_raw, list) or not all(isinstance(item, str) for item in adapters_raw):
            raise ValueError(f"collections entry {index} adapters must be a string array")
        adapters = list(dict.fromkeys(item.strip() for item in adapters_raw if item.strip()))
        unsupported = set(adapters) - {"sidecar", "png_text"}
        if unsupported:
            raise ValueError("unsupported metadata adapter(s): " + ", ".join(sorted(unsupported)))
        metadata = defaults | _clean_metadata(row.get("metadata"), field=f"collections[{index}].metadata")
        metadata.setdefault("source_project", project)
        normalized.append({
            "path": str(resolved),
            "relative_path": relative.as_posix(),
            "label": label,
            "group": group,
            "adapters": adapters,
            "metadata": metadata,
            "available": resolved.is_dir(),
        })
    return {
        "version": 1,
        "project": project,
        "root": str(root),
        "config_path": str(config_path),
        "collections": normalized,
    }
