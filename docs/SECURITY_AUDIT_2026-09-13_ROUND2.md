# Security audit — round 2 — 2026-09-13

## Executive summary

This audit starts from the v0.3 security baseline and focuses on a less obvious class of failure: **review integrity**. For an agent-facing approval tool, it is not enough to prevent arbitrary file disclosure. The system must also prevent stale, incomplete, or misidentified review decisions from being treated as authoritative.

v0.4 materially strengthens that property. Asset Viewer now maintains stable asset identities in SQLite, tombstones removed files, invalidates approval when file content changes, preserves decisions across same-filesystem renames, refuses to complete a review after an incomplete scan, and exposes ordered review events for automation.

The application remains recommended for local/private deployments rather than raw public-Internet exposure. The largest remaining security engineering items are replacing the development-oriented `http.server` serving layer and moving image decoding into isolated worker processes with OS-level resource boundaries.

## Threat model

Protected assets include:

- registered source images and adjacent non-image files;
- review status, comments, history, and completion state;
- the semantic integrity of an approval decision ("approved" must still refer to the reviewed bytes);
- remote access credentials and CSRF state;
- host CPU/RAM when processing large or hostile images.

Relevant attackers/failure modes include malicious browser origins, hostile filenames and symlinks, crafted image files, accidental filesystem churn, mount disappearance, incomplete scans, stale automation state, and operators accidentally binding the raw service too broadly.

## Round-2 findings

| ID | Severity | Finding | v0.4 disposition |
|---|---|---|---|
| R2-001 | High integrity | Replacing the bytes of an already-approved file at the same path could retain the old approval. | **Fixed.** Catalog metadata changes invalidate status/comment, mark the asset new, record a `content_changed` event, and prevent undo from resurrecting pre-change approval. |
| R2-002 | High integrity | A truncated filesystem scan could leave automation with an incomplete view yet still permit review completion. | **Fixed.** Truncated/unavailable scans are explicit catalog state and `complete` is rejected until a complete scan succeeds. |
| R2-003 | Medium | Scanner discovery could encounter a symlinked image resolving outside the registered root. File-serving containment already blocked access, but metadata scanning should enforce the same boundary. | **Fixed.** Discovery uses non-following directory traversal, resolves each candidate strictly, enforces root containment, and decodes/stats only the resolved in-root file. |
| R2-004 | Medium integrity | Review identity followed collection + relative path; renames could orphan decisions/history. | **Fixed.** Stable UUID asset IDs plus same-filesystem device/inode reconciliation preserve state across unambiguous renames. |
| R2-005 | Medium integrity | Deleted files could disappear from machine-readable state, making it difficult for automation to distinguish deletion from an unreviewed omission. | **Fixed.** Complete scans tombstone missing assets; manifests retain them by default and `--present-only` provides a current-files view. |
| R2-006 | Medium confidentiality | Thumbnail responses were marked `public`, which is undesirable behind shared HTTP caches for authenticated/private collections. | **Fixed.** Generated previews now use private cache directives. |
| R2-007 | Medium availability | Image decoding could run concurrently in every request thread. Existing byte/pixel caps limited individual jobs but not aggregate decode concurrency. | **Partially fixed.** A bounded preview semaphore limits concurrent decodes. Separate worker processes with memory/CPU limits remain P0. |
| R2-008 | Medium operational | A direct non-loopback bind could be configured with trusted Host values but without authentication. Host validation is not authentication. | **Fixed by default.** Non-loopback serving requires built-in authentication unless an explicit `--allow-unauthenticated-remote` override is used behind another trusted boundary. |
| R2-009 | Medium operational | Temporarily missing registered folders were silently filtered out of configuration views, reducing diagnosability. | **Fixed.** Registered collections remain visible as unavailable; scans become incomplete instead of deleting catalog state, and `doctor` reports the failure. |
| R2-010 | Low/Medium | Large original images were used directly in full-screen review, increasing client/network cost. | **Fixed.** The review surface uses bounded generated previews while keeping "Open original" explicit. |
| R2-011 | Low/Medium | Event feeds could become unnecessarily large for long-running installations. | **Fixed.** Event page sizes are bounded (default 100, maximum 500). |
| R2-012 | Residual | Filesystem validation and later open/stat are separate operations; a privileged writer could theoretically race a path between checks. | **Open/P0.** Private/trusted source directories reduce practical exposure. A hardened file-opening layer (`openat`/no-follow semantics or worker sandbox) is preferred before hostile multi-tenant input is in scope. |
| R2-013 | Residual | Python's built-in `http.server` is not a production application server. | **Open/P0.** Continue binding to loopback behind a trusted reverse proxy/private access layer until replaced/wrapped. |

## Positive controls verified

- Source folders remain read-only from Asset Viewer's perspective.
- Non-image guessed URLs are rejected at the serving boundary.
- Traversal and symlink escape regression tests remain in place.
- Host validation, CSRF tokens, Origin checks, and optional Basic auth remain active.
- SVG is never rendered inline by the application; previews are inert raster placeholders and originals are attachments.
- Image source-byte and pixel limits are configurable.
- Preview concurrency is bounded.
- Review/catalog data is transactional SQLite with private filesystem permissions.
- Scan truncation and unavailable mounts are fail-closed for completion semantics.
- Approval is invalidated when cataloged content changes.
- Deleted assets remain visible to machine-readable manifests as tombstones.
- Review events have stable asset IDs and bounded pagination.

## Release verification requirements

Before merging/releasing v0.4:

```bash
python -m unittest discover -v
python -m compileall -q asset_viewer tests
node --check asset_viewer/static/app.js
bandit -r asset_viewer
pip-audit --skip-editable
python -m build
```

CI, CodeQL, dependency review, and the repository security workflow must also pass on the release pull request.

## Remaining P0 security engineering

1. Replace/wrap `http.server` with a production serving layer while preserving localhost-safe defaults.
2. Isolate image decoding in bounded worker processes with OS-level CPU/memory/time limits and atomic cache writes.
3. Harden the validated-file handoff against TOCTOU races for deployments where registered directories are not trusted.
4. Add malformed-image/fuzz regression cases and request-budget/load tests.
5. Add release SBOM/provenance/signing where practical.

## Recommendation

v0.4 is materially safer than v0.3 not only at the HTTP boundary but at the **decision boundary**. That is the right security model for this product: automation must never interpret stale approval, partial discovery, or a missing source directory as a completed human review.

## References

- Python `http.server` production warning: https://docs.python.org/3/library/http.server.html
- OWASP File Upload Cheat Sheet (allowlists, resource limits, image rewriting, least privilege, CSRF): https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- Pillow decompression-bomb guidance: https://pillow.readthedocs.io/en/stable/reference/Image.html
