# Agent/API contract

Asset Viewer exposes a small local HTTP API and matching CLI surface. The goal is not to make the browser UI an API; the goal is to give agents and automation a stable contract for **discover → review → complete → consume feedback**.

## Protocol version

The current machine-readable contract is **version 1**. Manifests and event feeds include a top-level `version` field. Backward-compatible fields may be added within a protocol version; breaking changes require a new protocol version.

Use:

```bash
asset-viewer capabilities --json
```

or `GET /api/capabilities` to discover the running application/protocol version and supported features.

## Read APIs

All endpoints except `/api/health` require configured authentication when Basic auth is enabled.

### `GET /api/gallery?collection=<slug>&refresh=1`

Returns the browser-oriented current collection, present assets, scan state, and collection review state. `refresh=1` forces a filesystem reconciliation; otherwise a fresh catalog snapshot can be served without recursively walking the source directory.

Each asset has a stable `asset_id`. Use that identifier for durable integrations. Relative paths are human-readable locators and can change after a rename.

### `GET /api/reviews`

Query parameters:

- `collection=<slug>` — optional collection filter
- `status=approved|maybe|rejected|unreviewed|new` — optional decision filter
- `present=1` — omit tombstoned/missing assets

Response conforms to [`schemas/review-manifest.schema.json`](../schemas/review-manifest.schema.json).

Equivalent CLI:

```bash
asset-viewer reviews --collection brand-concepts --json
asset-viewer export-manifest --collection brand-concepts --output review.json
```

### `GET /api/events?collection=<slug>&after=<id>&limit=<n>`

Returns ordered review/system events after an event cursor. This is the preferred polling primitive for long-running agents because callers can persist `last_event_id` and request only later events. In addition to review/comment/completion activity, v0.4 emits filesystem lifecycle actions such as `asset_added`, `asset_renamed`, `content_changed`, `asset_missing`, and `asset_restored`; event `details` carries action-specific metadata such as old/new paths.

Response conforms to [`schemas/event-feed.schema.json`](../schemas/event-feed.schema.json).

Equivalent CLI:

```bash
asset-viewer events --collection brand-concepts --after 120 --json
```

### `GET /api/pending?collection=<slug>`

Returns explicit human-completion state. A collection is complete only when its latest complete scan is known, all present assets have decisions, and the human has explicitly marked the review complete. New, changed, or removed content makes a previously completed review stale/pending.

CLI automation can use exit codes:

```bash
asset-viewer pending --collection brand-concepts --json
# 0 = explicitly complete
# 2 = human review still required

asset-viewer wait-for-review --collection brand-concepts --timeout 900 --json
```

### `GET /api/review-history`

Accepts `collection` plus `asset_id` (preferred) or `rel`. Returns the asset's decision/comment history, including undone actions and system content-change events.

## Mutation APIs

Browser mutations use JSON POST requests and require the session CSRF token from `/api/session` in `X-Asset-Viewer-CSRF`. Origin/Host checks are also enforced.

- `POST /api/review` — set one status/comment or batch status
- `POST /api/comment` — set a note
- `POST /api/seen` — mark assets seen
- `POST /api/complete` — explicitly complete a fully reviewed collection
- `POST /api/reopen` — reopen a collection
- `POST /api/undo` — undo the most recent user review/comment change

Third-party automation should normally use the CLI for mutations unless it deliberately implements the browser security contract. Read APIs and CLI exports are designed as the stable integration surface first.

## Stable browser links

Collection:

```bash
asset-viewer collection-url brand-concepts --base-url https://viewer.example.com
```

Individual asset:

```bash
asset-viewer asset-url brand-concepts <asset-id-or-relative-path> --base-url https://viewer.example.com
```

The generated asset link uses the stable UUID, so ordinary same-filesystem renames do not invalidate the handoff.

## Storage semantics

- Source files remain authoritative and are never rewritten by Asset Viewer.
- Review state follows stable asset identity across detected same-filesystem renames.
- Non-empty review decisions are bound to a SHA-256 fingerprint (`review_sha256`) of the reviewed bytes. Replacing the bytes at an existing path invalidates the previous status/comment and makes the asset new again—even when size and nanosecond mtime are preserved and the replacement is detected by fingerprint reconciliation.
- Deleted assets are tombstoned rather than silently removed from manifests.
- Truncated/incomplete scans cannot declare missing files or produce a completed review state.
