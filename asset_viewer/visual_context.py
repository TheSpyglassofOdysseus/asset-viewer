from __future__ import annotations

import os
import urllib.parse
from pathlib import Path
from typing import Any

from .storage import annotations_for_asset, catalog_records, review_history, set_review

VISUAL_PANEL_URI = "ui://asset-viewer/visual-decision-panel/v1.html"
_ALLOWED_REVIEW_STATUSES = {"approved", "maybe", "rejected"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _extra(record: dict[str, Any]) -> dict[str, Any]:
    provenance = record.get("provenance") or {}
    extra = provenance.get("extra") if isinstance(provenance, dict) else {}
    return extra if isinstance(extra, dict) else {}


def _surface(record: dict[str, Any]) -> str:
    return _text(_extra(record).get("surface"))


def _viewport(record: dict[str, Any]) -> str:
    return _text(_extra(record).get("viewport"))


def _device(record: dict[str, Any]) -> str:
    return _text(_extra(record).get("device"))


def _snippet(value: Any, limit: int = 1000) -> str:
    text = _text(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _bounded_annotations(collection: str, asset_id: str) -> list[dict[str, Any]]:
    rows = annotations_for_asset(collection, asset_id, include_stale=False)
    return [
        {
            "annotation_id": row["annotation_id"],
            "kind": row["kind"],
            "x": row["x"],
            "y": row["y"],
            "w": row["w"],
            "h": row["h"],
            "text": _snippet(row.get("text")),
        }
        for row in rows
        if not row.get("resolved")
    ][:6]


def _bounded_review_history(collection: str, rel: str) -> list[dict[str, Any]]:
    return [
        {
            "id": row["id"],
            "action": row["action"],
            "old_status": _text(row.get("old_status")),
            "new_status": _text(row.get("new_status")),
            "old_comment": _snippet(row.get("old_comment")),
            "new_comment": _snippet(row.get("new_comment")),
            "created_at": row.get("created_at"),
            "undone_at": row.get("undone_at"),
        }
        for row in review_history(collection, rel, limit=4)
    ]


def _matches(record: dict[str, Any], surface: str, viewport: str) -> bool:
    if _surface(record).casefold() != surface.casefold():
        return False
    return not viewport or _viewport(record).casefold() == viewport.casefold()


def _normalize_base_url(value: str = "") -> str:
    base = _text(value) or _text(os.environ.get("ASSET_VIEWER_PUBLIC_BASE_URL")) or "http://127.0.0.1:8160"
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute http(s) URL")
    if parsed.query or parsed.fragment:
        raise ValueError("base_url must not contain query or fragment components")
    return base.rstrip("/")


def _asset_urls(base_url: str, collection: str, rel: str, asset_id: str) -> dict[str, str]:
    quoted_rel = urllib.parse.quote(rel, safe="/")
    quoted_collection = urllib.parse.quote(collection, safe="")
    quoted_asset = urllib.parse.quote(asset_id, safe="")
    return {
        "preview_url": f"{base_url}/asset/preview/{quoted_collection}/{quoted_rel}",
        "asset_url": f"{base_url}/c/{quoted_collection}?asset={quoted_asset}",
    }


def _asset_summary(record: dict[str, Any], base_url: str, *, include_annotations: bool) -> dict[str, Any]:
    provenance = record.get("provenance") or {}
    asset_id = _text(record.get("asset_id"))
    collection = _text(record.get("collection"))
    rel = _text(record.get("rel"))
    payload: dict[str, Any] = {
        "asset_id": asset_id,
        "collection": collection,
        "rel": rel,
        "status": _text(record.get("status")),
        "comment": _text(record.get("comment")),
        "width": int(record.get("width") or 0),
        "height": int(record.get("height") or 0),
        "surface": _surface(record),
        "viewport": _viewport(record),
        "device": _device(record),
        "git_commit": _text(provenance.get("git_commit")) if isinstance(provenance, dict) else "",
        "run_id": _text(provenance.get("run_id")) if isinstance(provenance, dict) else "",
        "updated_at": record.get("updated_at"),
        **_asset_urls(base_url, collection, rel, asset_id),
    }
    if include_annotations:
        payload["annotations"] = _bounded_annotations(collection, asset_id)
        payload["review_history"] = _bounded_review_history(collection, rel)
    return payload


def get_visual_context(
    collection: str,
    surface: str,
    viewport: str = "",
    candidate: str = "",
    base_url: str = "",
) -> dict[str, Any]:
    """Return bounded visual decision context for one named product surface."""
    collection = _text(collection)
    surface = _text(surface)
    viewport = _text(viewport)
    candidate = _text(candidate)
    if not collection:
        raise ValueError("collection is required")
    if not surface:
        raise ValueError("surface is required")

    base = _normalize_base_url(base_url)
    records = [row for row in catalog_records(collection, present_only=True) if _matches(row, surface, viewport)]
    if not records:
        qualifier = f" / {viewport}" if viewport else ""
        raise ValueError(f"no present visual evidence for surface: {surface}{qualifier}")

    if candidate:
        chosen = next(
            (row for row in records if candidate in {_text(row.get("asset_id")), _text(row.get("rel"))}),
            None,
        )
        if chosen is None:
            raise ValueError("candidate is not present or does not match the requested surface/viewport")
    else:
        chosen = records[0]

    chosen_id = _text(chosen.get("asset_id"))
    provenance = chosen.get("provenance") or {}
    parent_id = _text(provenance.get("parent_asset_id")) if isinstance(provenance, dict) else ""
    approved = [
        row for row in records
        if _text(row.get("status")) == "approved" and _text(row.get("asset_id")) != chosen_id
    ]
    reference = next((row for row in approved if _text(row.get("asset_id")) == parent_id), None)
    if reference is None:
        reference = approved[0] if approved else None

    decisions = []
    for row in records:
        status = _text(row.get("status"))
        if not status:
            continue
        row_provenance = row.get("provenance") or {}
        decisions.append({
            "asset_id": _text(row.get("asset_id")),
            "rel": _text(row.get("rel")),
            "status": status,
            "comment": _snippet(row.get("comment")),
            "git_commit": _text(row_provenance.get("git_commit")) if isinstance(row_provenance, dict) else "",
            "run_id": _text(row_provenance.get("run_id")) if isinstance(row_provenance, dict) else "",
            "updated_at": row.get("updated_at"),
        })
        if len(decisions) >= 6:
            break

    return {
        "version": 1,
        "collection": collection,
        "surface": surface,
        "viewport": viewport,
        "candidate": _asset_summary(chosen, base, include_annotations=True),
        "reference": _asset_summary(reference, base, include_annotations=False) if reference else None,
        "prior_decisions": decisions,
        "viewer_url": f"{base}/c/{urllib.parse.quote(collection, safe='')}",
        "render_contract": {
            "max_primary_images": 2,
            "uses_bounded_previews": True,
            "full_resolution_eager_load": False,
            "project_size_independent": True,
        },
    }


def record_visual_review(
    collection: str,
    asset: str,
    status: str,
    comment: str | None = None,
    explicit_human_action: bool = False,
) -> dict[str, Any]:
    """Persist one human-authorized review decision in canonical Asset Viewer state."""
    collection = _text(collection)
    asset = _text(asset)
    status = _text(status)
    if not explicit_human_action:
        raise ValueError("review mutation requires explicit human/UI action")
    if status not in _ALLOWED_REVIEW_STATUSES:
        raise ValueError("status must be approved, maybe, or rejected")
    records = catalog_records(collection, present_only=True)
    target = next(
        (row for row in records if asset in {_text(row.get("asset_id")), _text(row.get("rel"))}),
        None,
    )
    if target is None:
        raise ValueError("asset not found or not present")
    rel = _text(target.get("rel"))
    set_review(collection, rel, status, comment=comment)
    refreshed = next(
        row for row in catalog_records(collection, present_only=True)
        if _text(row.get("asset_id")) == _text(target.get("asset_id"))
    )
    return {
        "version": 1,
        "asset_id": _text(refreshed.get("asset_id")),
        "collection": collection,
        "rel": rel,
        "status": _text(refreshed.get("status")),
        "comment": _text(refreshed.get("comment")),
        "updated_at": refreshed.get("updated_at"),
        "human_authorized": True,
    }


def visual_panel_resource_meta() -> dict[str, Any]:
    base = _normalize_base_url("")
    parsed = urllib.parse.urlsplit(base)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "ui": {
            "prefersBorder": True,
            "csp": {
                "resourceDomains": [origin],
                "connectDomains": [],
            },
        }
    }


def visual_decision_panel_html() -> str:
    path = Path(__file__).with_name("static") / "visual_decision_panel.html"
    return path.read_text(encoding="utf-8")
