# Public Release Sign-off — 2026-09-13

This audit is the final public-release review for the Asset Viewer v0.6 line. It covers the source tree, distributable artifacts, machine protocol, browser runtime, and intended deployment boundary.

## Decision

**Approved for public release and long-running local/private-server use.** Asset Viewer is suitable for installation from its published wheel or source archive when deployed on loopback, a private network such as Tailscale, or behind a TLS-terminating authenticated reverse proxy.

It is **not** positioned as an anonymous Internet-facing multi-tenant service. Registered source trees remain a trusted-project boundary.

## Release gates

- Full automated test suite passes on supported Python versions through GitHub CI.
- Python source compiles and browser JavaScript passes syntax validation.
- Bandit reports no findings in the application package.
- `pip-audit` reports no known vulnerabilities in pinned release dependencies.
- GitHub dependency review and CodeQL gates pass with no open code-scanning alerts at sign-off.
- Wheel and source distributions build successfully and install into a clean virtual environment.
- Setuptools package-data intent is explicit; the v0.6.1 build is warning-free and still contains the static UI assets.
- Published release artifacts include SHA-256 checksums and a CycloneDX SBOM.
- Current source and release archive scans contain no private server addresses, private project paths, credentials, or private deployment identifiers.

## Security controls rechecked

- Loopback is the default listener.
- Non-loopback serving requires authentication or an explicit acknowledgement of an external trusted boundary.
- Host validation rejects untrusted Host headers and mitigates DNS-rebinding attacks.
- State-changing browser requests require CSRF protection and same-origin validation.
- Request bodies are bounded and mutation endpoints require JSON.
- Asset paths reject traversal, dot paths, unsupported source extensions, and symlink escapes.
- Raster decoding and metadata inspection run in disposable bounded worker processes.
- SVG previews are inert raster placeholders; original SVG files are served as attachments rather than executable inline content.
- Security headers include CSP, nosniff, frame protection, same-origin policies, and restrictive permissions policy.
- Full originals are streamed rather than loaded wholesale into the application process.
- Review decisions and spatial annotations are bound to content hashes so changed bytes cannot silently inherit stale judgment.

## Protocol and data integrity rechecked

- Stable asset UUIDs preserve review and family lineage across ordinary same-filesystem renames.
- Deleted assets remain tombstoned in machine-readable state instead of disappearing silently.
- Truncated scans cannot tombstone unvisited assets or be marked review-complete.
- Variant/version families are metadata only and never move, rename, copy, rewrite, or delete source files.
- Review manifests expose decisions, comments, annotations, content integrity, family lineage, and completion state.
- Ordered events expose human decisions and family changes to automation without requiring chat scraping.
- JSON schemas remain versioned and machine-readable.

## Residual risk accepted for this release

The remaining security frontier is deliberate and documented rather than hidden:

1. Registered project directories are trusted. A hostile process racing filesystem entries can still exploit ordinary path-validation/open TOCTOU windows; descriptor-relative no-follow opening remains future hardening work.
2. Basic authentication provides access control but not transport encryption. Remote deployments must use a private transport or TLS proxy.
3. The application does not yet provide a per-client application-level rate limiter; deployment is expected to remain private/authenticated and resource bounds exist at the server/worker layers.
4. Multi-user identity, per-user permissions, expiring public shares, and SSO are outside the supported core model today.
5. Release artifacts provide checksums and an SBOM; stronger cryptographic provenance/signing remains future supply-chain work.

## Product boundary

Asset Viewer is a filesystem-native visual decision protocol and review plane. It should continue to own review metadata and human/agent feedback while leaving source-file ownership with the project, repository, NAS, object store, or other existing storage system. It should not become a cloud-storage product or destructive file organizer.
