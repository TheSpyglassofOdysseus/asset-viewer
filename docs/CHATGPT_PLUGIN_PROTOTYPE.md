# ChatGPT Visual Decision Panel prototype

This prototype implements the Phase 1 experiment from `RFC_CHATGPT_PLUGIN_ARCHITECTURE.md`.
It is intentionally private/local-first and does not authorize public hosting or multi-tenant storage.

## What it proves

The MCP surface can retrieve visual decision memory for one named product surface, hand a bounded result to an inline MCP Apps UI, and persist one explicit human review decision through Asset Viewer's existing review state.

The flow is deliberately decoupled:

1. `get_visual_context` returns candidate/reference evidence plus compact decision history.
2. `render_visual_decision_panel` accepts that result and attaches the inline UI resource.
3. The UI may call `record_visual_review` only after the reviewer clicks Approve, Maybe, or Reject.
4. `record_visual_review` writes through the existing `set_review` path and returns the authoritative state.

No second review database or plugin-owned canonical state exists.

## FDI provenance convention

The prototype locates a product surface through existing asset metadata. Tag captures with normal provenance fields plus `extra` keys:

```bash
asset-viewer metadata fdi-captures quote-mobile.png \
  --set source_project=FDI \
  --set git_commit=<commit-sha> \
  --set run_id=<capture-run> \
  --extra-json '{"surface":"Quote Editor","viewport":"412x915","device":"mobile"}'
```

Use the same `surface` and `viewport` on the accepted reference and its candidate variants.

## Local/private test setup

Install MCP support and run the existing web viewer plus streamable HTTP MCP adapter:

```bash
pip install -e '.[mcp]'
export ASSET_VIEWER_PUBLIC_BASE_URL='https://<trusted-viewer-origin>'
asset-viewer serve
asset-viewer mcp --transport streamable-http --host 127.0.0.1 --port 8161
```

The MCP listener intentionally remains loopback-only. Use the project's existing trusted/private bridge or reverse-proxy boundary rather than weakening that guard for the prototype.

Connect the reachable MCP endpoint in ChatGPT Developer Mode, call `get_visual_context`, then pass the returned object unchanged to `render_visual_decision_panel`.

## Performance contract

The panel renders at most two primary images: candidate and accepted reference. Both use Asset Viewer's bounded review preview endpoint. It does not enumerate a project gallery, preload originals, or store business state in browser storage.

## Prototype gate

Do not promote this to a hosted product until real FDI dogfood demonstrates all of the following:

- a fresh agent can recover prior human visual decisions without conversational reconstruction;
- exact asset/provenance grounding improves a subsequent implementation turn;
- reviewing in-chat reduces meaningful context switching versus opening the full viewer;
- client resource use stays bounded as collection size grows;
- the workflow is materially different from ordinary visual-regression reporting.

If the final point fails, integrate an established visual-testing provider instead of expanding this prototype.
