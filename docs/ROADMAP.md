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
- [~] Review/comment/seen state is now transactional SQLite with migration; stable asset IDs and indexed catalog records remain open.
- Build an indexed catalog so page loads do not recursively scan every source directory.
- [~] Image byte/pixel/scan limits are implemented; background worker isolation remains open.
- [x] SVG previews are inert JPEG placeholders and originals are forced downloads.
- [~] CSRF/origin protections, trusted hosts, and optional Basic auth are implemented; stronger proxy identity/session auth remains open.
- [~] Regression coverage now includes traversal, symlinks, Host/Origin, CSRF, SVG, non-image disclosure, concurrent writes, and permissions; fuzz/malformed-image/request-budget coverage remains open.
- [x] `asset-viewer doctor` reports bind, permissions, collection readability, and auth posture; richer decoder/staleness diagnostics can grow later.
- [~] Branch rules, pinned Actions, Dependabot, CodeQL, Bandit/pip-audit, and PR dependency review are in place; SBOM/provenance/signing remain open.

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
asset-viewer pending --json  # implemented; review sessions/events remain next
asset-viewer wait-for-review
asset-viewer export-manifest
```

Event concepts:

```text
asset.approved
asset.rejected
asset.commented
collection.review_complete
```

The intended loop is:

**Generate → register/publish folder → notify human → review → consume feedback → regenerate.**

## P3 — serious creative review

Target: support high-volume visual iteration without becoming an editor or DAM.

- Zoom/pan and fit modes.
- [~] Filename/path search is implemented; metadata search remains open.
- [~] Sort by time/name/status is implemented; dimensions/type/generation-metadata sorting remains open.
- Prompt/model/generation metadata display where available.
- Contact-sheet export.
- Compare/overlay/difference views.
- Version/variant families.
- Nested collection navigation.
- Review history and activity views.
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
