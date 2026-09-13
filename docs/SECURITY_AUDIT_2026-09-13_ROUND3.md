# Asset Viewer Security Audit — Round 3 — 2026-09-13

## Executive summary

Round 3 reviewed the v0.5 production-runtime and precision-review work after the v0.4 durable-catalog release. The two largest remaining P0 concerns from the previous audit were the stdlib HTTP serving boundary and in-request image decoding. v0.5 materially closes both: `asset-viewer serve` now runs the application through Waitress by default, and raster metadata/preview decoding is performed in disposable child processes with explicit time, memory, pixel, byte, concurrency, and output-file limits.

The new spatial-annotation feature was also treated as security-sensitive review state rather than decorative UI. An annotation is attached to a stable asset UUID and stores a SHA-256 fingerprint of the bytes it described. A replacement that preserves file size and nanosecond mtime is therefore still detected during reconciliation, and old spatial feedback becomes stale rather than silently applying to different pixels.

Asset Viewer remains a local/private-first application. Waitress makes the direct serving path production-grade as an application server, but Internet exposure should still sit behind TLS and, for broader deployments, a deliberate identity/reverse-proxy boundary.

## Scope

Reviewed in this round:

- Waitress/WSGI serving boundary and parity with the legacy development handler
- authentication, Host, Origin, CSRF, request-size, and method controls
- child-process image metadata/preview decoding
- decoder timeout, memory, pixel, input-byte, output-file, and concurrency limits
- atomic preview-cache publication and cache eviction behavior
- stable asset identity and review/annotation fingerprint integrity
- point/region annotation geometry, lifecycle, API, event, CLI, and manifest surfaces
- SQLite migrations and concurrent state semantics
- source-path containment/symlink protections
- browser comparison/annotation code paths
- dependency/release security and public-source privacy

## Findings

| ID | Severity | Finding | Status |
|---|---|---|---|
| AV3-001 | High | Prior releases decoded source images in HTTP request threads/process space. A parser bug or pathological image could affect the serving process despite pixel/byte checks. | **Fixed in v0.5.0.** Source-image metadata and raster preview decoding run in disposable child processes with timeout and best-effort POSIX address-space/file-size limits. |
| AV3-002 | Medium | The stdlib `http.server` listener remained the default serving path even though Python documents it as a basic development server. | **Fixed in v0.5.0.** Waitress is now the default server. The legacy listener is available only with `--development-server`. |
| AV3-003 | Medium | Location-based feedback can become semantically wrong if source bytes change without ordinary metadata changing. | **Fixed in v0.5.0.** Spatial annotations carry content fingerprints. Reconciliation detects annotation fingerprint mismatches and marks existing annotations stale. |
| AV3-004 | Medium | An unbounded generated-preview cache can become an availability/storage problem on long-running render servers. | **Fixed in v0.5.0.** Configurable size/age budgets, deterministic eviction, automatic periodic pruning, CLI controls, and `doctor` visibility were added. |
| AV3-005 | Medium operational | HTTP Basic authentication does not itself provide transport encryption and is not a multi-user identity system. | **By design/documented.** Localhost is default. Remote deployments should use TLS/private networking or an authenticated reverse proxy; stronger identity/SSO remains collaboration-roadmap work. |
| AV3-006 | Medium residual | Source-path validation and the eventual child-process open are separate operations, so a malicious actor with concurrent write/rename access to registered source directories can still create TOCTOU races. | **Open boundary.** Registered roots remain trusted project output directories, not hostile multi-tenant upload directories. A future descriptor-based broker/sandbox can further tighten this. |
| AV3-007 | Low/Medium | Child-process memory limits are best-effort and POSIX-specific. Platforms without `resource` do not receive RLIMIT enforcement. | **Documented residual risk.** Timeout, byte/pixel limits and process isolation still apply; platform-specific stronger sandboxing remains possible. |
| AV3-008 | Low | Annotation volume is authorized-user-controlled and can grow SQLite/event state. | **Accepted for current local/private model.** Request-size limits and 4,000-character annotation text cap bound individual mutations; collection quotas can be added if multi-user deployments need them. |
| AV3-009 | Informational | Linked comparison zoom/pan and annotations use browser transforms/normalized coordinates; they never rewrite source bytes. | **Positive control.** Review UI remains non-destructive. |

## Positive controls verified

- Waitress is the default `serve` path; development server use is explicit.
- Host allowlisting and fail-closed non-loopback configuration remain enforced.
- Non-loopback direct serving requires authentication unless the operator explicitly acknowledges an external trusted boundary.
- CSRF token plus Origin/Host matching protects browser mutations.
- No permissive CORS policy is present.
- Registered-source access remains extension-allowlisted, traversal checked, symlink-escape checked, resolved-root contained, and `is_file()` checked.
- SVG preview remains inert and SVG originals are attachment downloads.
- Raster decode runs outside the serving process; timeout failures return inert placeholders.
- Preview cache writes are atomic in child workers.
- Review decisions and spatial annotations can be bound to SHA-256 content fingerprints.
- Truncated or unavailable scans cannot produce a newly completed review.
- Missing assets remain tombstones rather than disappearing from machine-readable history.
- State lives in private SQLite/data paths; source assets are not rewritten.
- GitHub branch rules, pinned Actions, CodeQL, Bandit, pip-audit, Dependabot, dependency review, secret scanning/push protection, SBOM, and release checksums remain in place.

## Remaining security priorities

### Near term

1. Add fuzz/property tests around URL decoding, annotation geometry, event cursors, and manifest schemas.
2. Add platform-specific decoder sandbox documentation/tests for Windows/macOS where POSIX rlimits do not apply.
3. Consider descriptor-based source opening if Asset Viewer ever targets hostile multi-tenant source directories.
4. Add authenticated reviewer identity before treating built-in auth as collaborative authorization.
5. Add rate limiting only if the deployment model expands beyond trusted/private operators; avoid unnecessary complexity for localhost use.

### Release/supply chain

- Continue pinning GitHub Actions by immutable SHA.
- Keep the release dependency set audited and synchronized with `pyproject.toml`.
- Publish SBOM and SHA-256 checksums for tagged releases.
- Add cryptographic artifact provenance/signing when the release channel justifies the operational overhead.

## Verification commands

```bash
python -m unittest discover -v
python -m compileall -q asset_viewer tests
node --check asset_viewer/static/app.js
bandit -r asset_viewer
pip-audit --skip-editable
pip-audit -r requirements-release.txt
```

The release process additionally builds and installs the wheel into a clean virtual environment and smoke-tests the installed CLI/API contract.

## References

- Python `http.server` warning: https://docs.python.org/3/library/http.server.html
- Waitress documentation: https://docs.pylonsproject.org/projects/waitress/
- Pillow decompression-bomb guidance: https://pillow.readthedocs.io/en/stable/reference/Image.html
- OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- GitHub Actions secure-use guidance: https://docs.github.com/en/actions/reference/security/secure-use

## Conclusion

v0.5 moves Asset Viewer out of the "hardened prototype served by development infrastructure" category. For its intended local/private/reverse-proxied deployment model, the highest-risk serving and image-decoder concerns are now materially reduced. The remaining security work is mostly about stronger isolation and identity for deployment models Asset Viewer does not yet claim to support, rather than a known blocker in its current single-owner/private-server model.
