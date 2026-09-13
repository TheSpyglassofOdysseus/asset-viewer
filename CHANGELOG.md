# Changelog

All notable changes to Asset Viewer will be documented here.

## 0.4.0 — 2026-09-13

Durable catalog and agent-event release.

- Add stable UUID asset identities that survive same-filesystem renames.
- Add a durable SQLite asset catalog with scan generations, present/missing tombstones, dimensions, file identity, and change metadata.
- Preserve review status, comments, and history across renames; invalidate stale approvals when file content changes.
- Bind non-empty review decisions to a streaming SHA-256 fingerprint of the reviewed bytes; forced reconciliation detects same-size/same-timestamp replacements and completion re-verifies fingerprints.
- Keep deleted assets in manifests as missing/tombstoned records so automation can account for reviewed work that disappeared.
- Add cached gallery reads with bounded explicit rescans instead of recursive filesystem discovery on every page refresh.
- Prevent truncated scans from incorrectly tombstoning unvisited files or allowing a collection to be marked review-complete.
- Add ordered review/system event feeds through `/api/events` and `asset-viewer events`, including asset add/rename/change/missing/restore lifecycle events.
- Add `asset-viewer wait-for-review` for automation that needs an explicit human-completion gate.
- Allow review/history requests to target stable `asset_id` values.
- Bound concurrent thumbnail/review-preview decoding and mark generated preview responses private-cache only.
- Use bounded 2048px review previews in the carousel instead of loading full-resolution originals by default.
- Add stable per-asset deep links and `asset-viewer asset-url`.
- Add side-by-side, opacity-overlay, and difference comparison modes; sort by file size/resolution and search review comments.
- Keep configured collections visible when their source path is temporarily unavailable; fail review completion closed and report the condition in `doctor`.
- Harden direct non-loopback serving so authentication is required unless an operator explicitly acknowledges an external access-control boundary.
- Expand migration, catalog-integrity, rename, deletion, replacement, symlink, event, preview, and automation regression coverage.
- Add a tag-driven release workflow that publishes wheel/sdist artifacts, a CycloneDX SBOM, and SHA-256 checksums.

## 0.3.0 — 2026-09-13

Agent-review workflow release.

- Add explicit collection review completion/reopen state.
- Add `asset-viewer pending` with automation-friendly exit codes (`2` pending, `0` complete).
- Add review event history and one-step undo for status/comment changes.
- Add `history`, `undo`, and `collection-url` CLI commands.
- Add read-only pending/history APIs plus CSRF-protected complete/reopen/undo endpoints.
- Add filename/path search and client-side sort controls.
- Surface review progress/completion directly in the gallery.
- Fix duplicate `New` filter and duplicate review-note DOM IDs from the v0.2 UI.
- Increase review timestamps to microsecond precision so new work reliably invalidates older completion state.

## 0.2.0 — 2026-09-13

Security hardening and closed-loop review foundation.

- Prevent non-image files inside registered folders from being served by guessed URLs.
- Validate HTTP `Host` headers to reduce localhost DNS-rebinding exposure.
- Reject cross-origin review mutations with strict `Origin`/`Host` validation.
- Require explicit trusted hosts for non-loopback/reverse-proxy deployments.
- Treat Pillow decompression-bomb warnings as preview failures.
- Store registry/review data with private filesystem permissions where supported.
- Add regression tests for traversal, non-image disclosure, and Host validation.
- Move review metadata to SQLite with automatic migration from legacy `reviews.json`.
- Add review notes, new/seen state, batch-review backend support, and machine-readable review manifests.
- Add CSRF tokens and optional HTTP Basic authentication for remote/private deployments.
- Serve SVG originals as downloads and use inert preview placeholders instead of rendering active SVG content.
- Add bounded collection scans, image size/pixel limits, structured logging, and `asset-viewer doctor`.
- Add stable collection URLs (`/c/<slug>`) and a `New` review filter.
- Pin GitHub Actions to immutable commit SHAs and add Dependabot configuration.

## 0.1.0 — 2026-09-13

Initial public release.

- Register existing image directories without importing or moving originals.
- Browse multiple collections from a thumbnail gallery.
- Full-screen carousel navigation.
- Approve / Maybe / Reject review state.
- Keyboard review shortcuts.
- Cached raster thumbnails and direct SVG previews.
- Localhost-by-default HTTP server.
- Agent-oriented CLI and workflow documentation.
- Synthetic demo collection and screenshot.
