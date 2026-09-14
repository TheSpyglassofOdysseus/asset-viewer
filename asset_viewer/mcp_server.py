from __future__ import annotations

import json
from typing import Any

from .app import capability_document, scan_collection
from .storage import (
    annotations_for_asset,
    catalog_records,
    catalog_state,
    collection_review_state,
    collections as registered_collections,
    families_for_collection,
    pending_summary,
    review_events_since,
    review_manifest,
)


def _scan(scope: str | None) -> None:
    rows = registered_collections()
    if scope:
        rows = [row for row in rows if row["slug"] == scope]
        if not rows:
            raise ValueError(f"collection not found: {scope}")
    for row in rows:
        scan_collection(row["slug"], force=True)


def list_collections() -> dict[str, Any]:
    items = []
    for row in registered_collections():
        slug = row["slug"]
        items.append({
            "slug": slug,
            "label": row["label"],
            "available": bool(row.get("available")),
            "catalog": catalog_state(slug),
            "review": collection_review_state(slug),
        })
    return {"version": 1, "collections": items}


def get_reviews(
    collection: str | None = None,
    status: str | None = None,
    present_only: bool = True,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return durable human review state without changing review decisions."""
    if refresh:
        _scan(collection)
    return review_manifest(collection, status, include_missing=not present_only)


def get_pending(collection: str | None = None, refresh: bool = False) -> dict[str, Any]:
    """Return whether human review is explicitly complete."""
    if refresh:
        _scan(collection)
    return pending_summary(collection)


def get_events(collection: str | None = None, after_id: int = 0, limit: int = 100) -> dict[str, Any]:
    """Read ordered review and filesystem events after a durable cursor."""
    return review_events_since(collection, max(0, int(after_id)), max(1, min(int(limit), 1000)))


def get_families(collection: str, present_only: bool = True) -> dict[str, Any]:
    """Return variant/version families and preferred members."""
    return {
        "version": 1,
        "collection": collection,
        "families": families_for_collection(collection, include_missing=not present_only),
    }


def get_annotations(collection: str, asset: str, include_stale: bool = False) -> dict[str, Any]:
    """Return point/region feedback for a stable asset id or relative path."""
    records = catalog_records(collection, present_only=False)
    record = next((row for row in records if row["asset_id"] == asset or row["rel"] == asset), None)
    if not record:
        raise ValueError(f"asset not found: {asset}")
    return {
        "version": 1,
        "collection": collection,
        "asset_id": record["asset_id"],
        "annotations": annotations_for_asset(collection, record["asset_id"], include_stale=include_stale),
    }


def get_collection_url(collection: str, base_url: str = "http://127.0.0.1:8160") -> str:
    """Return the stable browser handoff URL for a collection."""
    if not any(row["slug"] == collection for row in registered_collections()):
        raise ValueError(f"collection not found: {collection}")
    return base_url.rstrip("/") + "/c/" + collection


def get_asset_url(collection: str, asset: str, base_url: str = "http://127.0.0.1:8160") -> str:
    """Return a browser deep link using the durable asset UUID."""
    record = next(
        (row for row in catalog_records(collection, present_only=False) if row["asset_id"] == asset or row["rel"] == asset),
        None,
    )
    if not record:
        raise ValueError(f"asset not found: {asset}")
    return base_url.rstrip("/") + f"/c/{collection}?asset={record['asset_id']}"


def refresh_collections(collection: str | None = None) -> dict[str, Any]:
    """Run the normal bounded filesystem reconciliation and return catalog state."""
    _scan(collection)
    rows = registered_collections()
    if collection:
        rows = [row for row in rows if row["slug"] == collection]
    return {"version": 1, "collections": [catalog_state(row["slug"]) for row in rows]}


def create_mcp_server():
    try:
        from mcp.server import MCPServer
    except ImportError as exc:  # pragma: no cover - exercised by CLI integration
        raise RuntimeError('MCP support requires: pip install "local-asset-viewer[mcp]"') from exc

    server = MCPServer("Asset Viewer")
    server.tool()(list_collections)
    server.tool()(get_reviews)
    server.tool()(get_pending)
    server.tool()(get_events)
    server.tool()(get_families)
    server.tool()(get_annotations)
    server.tool()(get_collection_url)
    server.tool()(get_asset_url)
    server.tool()(refresh_collections)

    @server.resource("asset-viewer://capabilities")
    def capabilities_resource() -> str:
        return json.dumps(capability_document(), indent=2, sort_keys=True)

    @server.resource("asset-viewer://collections")
    def collections_resource() -> str:
        return json.dumps(list_collections(), indent=2, sort_keys=True)

    @server.resource("asset-viewer://pending")
    def pending_resource() -> str:
        return json.dumps(get_pending(), indent=2, sort_keys=True)

    return server


def run_mcp(
    transport: str = "stdio",
    *,
    host: str = "127.0.0.1",
    port: int = 8161,
) -> None:
    server = create_mcp_server()
    if transport == "stdio":
        server.run("stdio")
        return
    if transport != "streamable-http":
        raise ValueError("MCP transport must be stdio or streamable-http")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Asset Viewer MCP HTTP currently permits loopback binds only; use a trusted local/private bridge")
    server.run("streamable-http", host=host, port=port, stateless_http=True, json_response=True)


def main() -> None:
    run_mcp()


if __name__ == "__main__":
    main()
