from __future__ import annotations

from typing import Any

from .storage import recent_review_events, review_events_since


def _status_label(value: str) -> str:
    return value or "unreviewed"


def event_summary(event: dict[str, Any]) -> str:
    action = str(event.get("action") or "event")
    rel = str(event.get("rel") or "").strip()
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    subject = rel or str(details.get("name") or details.get("family_id") or "collection")
    if action in {"review", "batch"}:
        return f"{subject}: {_status_label(str(event.get('old_status') or ''))} → {_status_label(str(event.get('new_status') or ''))}"
    if action == "comment":
        return f"Review note updated for {subject}"
    if action == "asset_added":
        return f"New asset appeared: {subject}"
    if action == "asset_renamed":
        return f"Asset renamed: {details.get('old_rel', subject)} → {details.get('new_rel', subject)}"
    if action == "asset_changed":
        return f"Asset changed and needs review: {subject}"
    if action == "asset_missing":
        return f"Asset missing: {subject}"
    if action == "asset_restored":
        return f"Asset restored: {subject}"
    if action == "collection_complete":
        return "Collection review completed"
    if action == "collection_reopen":
        return "Collection review reopened"
    if action == "metadata_updated":
        fields = ", ".join(details.get("fields") or [])
        return f"Provenance updated for {subject}" + (f" ({fields})" if fields else "")
    if action.startswith("family_"):
        return action.replace("_", " ").capitalize() + (f": {subject}" if subject else "")
    if action.startswith("annotation_"):
        return action.replace("_", " ").capitalize() + (f": {subject}" if subject else "")
    return action.replace("_", " ").capitalize() + (f": {subject}" if subject else "")


def activity_feed(collection: str | None = None, after_id: int = 0, limit: int = 200) -> dict[str, Any]:
    payload = review_events_since(collection, after_id, limit) if after_id else recent_review_events(collection, limit)
    payload["events"] = [event | {"summary": event_summary(event)} for event in payload["events"]]
    return payload
