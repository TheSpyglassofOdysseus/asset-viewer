# Changelog

All notable changes to Asset Viewer will be documented here.

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
