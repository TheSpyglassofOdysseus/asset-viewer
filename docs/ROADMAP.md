# Asset Viewer roadmap

Asset Viewer is the **review plane**, not the storage plane. Projects and creative tools keep ownership of original files; Asset Viewer provides the stable human review surface and machine-readable feedback loop.

## Product benefits to preserve

| Capability | Human benefit | Agent/system benefit |
|---|---|---|
| Register folders in place | No import, upload, or duplicate library | Agents keep writing to normal project output paths |
| One review surface | No IDE/file-tree scavenger hunt | Deterministic handoff destination |
| Cached thumbnails | Fast review of large batches | Avoids pushing full-resolution assets through chat/context |
| Carousel + keyboard review | Rapid visual triage | Structured decisions instead of conversational ambiguity |
| Separate review state | Originals remain untouched | Viewer is disposable; project remains source of truth |
| Multiple collections | One interface across projects | Standard review protocol across repositories |
| CLI/API contract | Minimal administration | Agents can provision and query review work themselves |

## P0 — production hardening

Target: make private/server deployments robust enough to recommend confidently.

- Replace or wrap the development `http.server` listener with a production serving layer.
- [x] Review/comment/seen state and the asset catalog are transactional SQLite with migrations, stable UUID asset IDs, and SHA-256-bound non-empty review decisions.
- [~] Durable catalog + cached reads, tombstones, content-change invalidation, and rename reconciliation are implemented; a filesystem watcher remains open for immediate discovery without explicit/TTL rescans.
- [~] Image byte/pixel/scan limits and bounded concurrent decoding are implemented; process-isolated preview workers remain open.
- [x] SVG previews are inert JPEG placeholders and originals are forced downloads.
- [~] CSRF/origin protections and trusted hosts are implemented; direct non-loopback serving now requires Basic auth unless an operator explicitly acknowledges another trusted access boundary. Stronger proxy identity/session auth remains open.
- [~] Regression coverage now includes traversal, symlinks, Host/Origin, CSRF, SVG, non-image disclosure, concurrent writes, and permissions; fuzz/malformed-image/request-budget coverage remains open.
- [x] `asset-viewer doctor` reports bind/auth posture, unavailable collections, catalog scan state, permissions, and resource-limit configuration.
- [~] Branch rules, pinned Actions, Dependabot, CodeQL, Bandit/pip-audit, and PR dependency review are in place; CycloneDX SBOM generation is now in security CI; provenance/signing remain open.

## P1 — close the human/agent review loop

Target: make review decisions directly useful to the next agent turn.

- [x] Per-asset comments/notes.
- [x] JSON review manifest and `asset-viewer reviews --json`.
- [x] Stable collection URLs in the browser (`/c/<slug>`) plus `asset-viewer collection-url`.
- [x] Batch selection and bulk Approve / Maybe / Reject.
- [x] Side-by-side compare mode for 2–4 assets. Synchronized zoom/pan remains open.
- [x] New/unseen-since-discovery state.
- [x] Review history and undo for status/comment changes.
- [x] Exportable filtered manifests plus `asset-viewer pending --json` with explicit completion exit codes.

Example machine-readable feedback:

```json
{
  "collection": "brand-concepts",
  "asset": "concept-17.png",
  "status": "maybe",
  "comment": "Keep the composition; remove the subtitle."
}
```

## P2 — agent-native automation

Target: let automation wait for and react to human visual decisions without scraping the UI.

Planned CLI/API concepts:

```text
asset-viewer collection create
asset-viewer collection-url
asset-viewer reviews --json
asset-viewer pending --json       # implemented
asset-viewer events --after N     # implemented
asset-viewer wait-for-review      # implemented
asset-viewer export-manifest      # implemented
asset-viewer asset-url             # implemented
```

Ordered review events are implemented with stable asset IDs. Future webhook/MCP adapters can translate events such as review, comment, content-change, collection-complete, and collection-reopen into push-based integrations without changing the core database contract.

The intended loop is:

**Generate → register/publish folder → notify human → review → consume feedback → regenerate.**

## P3 — serious creative review

Target: support high-volume visual iteration without becoming an editor or DAM.

- Zoom/pan and fit modes; linked transforms across comparison panes remain open.
- [~] Filename/path search is implemented; metadata search remains open.
- [~] Sort by time/name/status/file-size/resolution is implemented; type/generation-metadata sorting remains open.
- Prompt/model/generation metadata display where available.
- Contact-sheet export.
- Pinned/anchored annotations with normalized image coordinates and agent-readable events. **Highest-value next human-feedback feature.**
- [x] Side-by-side, overlay, and difference comparison views; synchronized zoom/pan remains open.
- Version/variant families. **Highest-value structural creative feature after pinned annotations.**
- Nested collection navigation.
- [~] Per-asset review history and ordered machine event feed are implemented; human-facing collection activity view remains open.
- Export/copy approved sets without changing source-of-truth semantics.

Variant families are particularly important for generative workflows:

```text
Logo concept
├── v01
├── v02
├── v03
└── v04  ✓ approved
```

## P4 — collaboration, deliberately

Only after the local-first workflow is excellent:

- Named reviewers and reviewer identity.
- Per-user decisions and review assignments.
- Comments/replies.
- Collection permissions.
- Expiring/shareable review links.
- SSO or trusted reverse-proxy identity integration.

Asset Viewer should **not** become a cloud storage provider. Local disks, NAS, Git workspaces, object stores, Drive, and other systems should continue owning files. Asset Viewer owns the review experience and review metadata.

## North-star product contract

> Projects own the files. Agents create the files. Asset Viewer gives humans one stable place to review them — and gives agents a structured way to understand the decision.
