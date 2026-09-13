# Security policy

## Deployment model

Asset Viewer is designed to run on a trusted machine and bind to `127.0.0.1` by default. `asset-viewer serve` uses Waitress as the production runtime; the old stdlib server is available only with `--development-server`. Optional HTTP Basic authentication is available through `ASSET_VIEWER_PASSWORD`; a private network or TLS-terminating authenticated reverse proxy remains the recommended outer access boundary.

If you need remote access, prefer keeping Asset Viewer on loopback behind a trusted VPN/private network or authenticated reverse proxy. Configure each browser-facing hostname with `--trusted-host`; unexpected Host headers are rejected. A direct non-loopback bind now also requires built-in Basic authentication unless the operator explicitly passes `--allow-unauthenticated-remote`, which is intended only when another trusted boundary already provides access control. Basic authentication does not provide transport encryption: never send its credentials over an untrusted cleartext network. Do not expose the raw application listener directly to the public internet without TLS and a deliberate access-control boundary.

Asset Viewer treats SVG as active content: gallery previews use inert placeholders and opening an SVG original is forced to download as an attachment rather than rendered inline. Registered folders should still be treated as potentially hostile input and kept within the documented image/resource limits.

## Review integrity

Security includes the meaning of an approval, not only network access. The catalog invalidates review state when a known asset's file metadata indicates its contents changed, retains deleted assets as tombstones for auditability, and refuses to mark a collection complete after a truncated or unavailable scan. Stable IDs preserve decisions across unambiguous same-filesystem renames.

Filesystem validation still occurs separately from the final file open. Registered source directories should therefore remain writable only by trusted project processes/users. Image decoding is process-isolated in v0.5, but a stronger descriptor-relative/no-follow file-opening layer remains planned before hostile multi-tenant source folders are considered supported.

## Reporting a vulnerability

Please open a GitHub security advisory for the repository when possible. Avoid posting exploit details in a public issue before a fix can be prepared.

## Published audits

- [Initial public security audit](docs/SECURITY_AUDIT_2026-09-13.md)
- [Round-two security/review-integrity audit](docs/SECURITY_AUDIT_2026-09-13_ROUND2.md)
- [Round-three production/precision-review audit](docs/SECURITY_AUDIT_2026-09-13_ROUND3.md)
