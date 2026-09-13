# Asset Viewer Security Audit — 2026-09-13

## Executive summary

Asset Viewer has a deliberately small attack surface and a good foundational security property: it binds to loopback by default and does not ingest or relocate source assets. The v0.1.0 implementation nevertheless contained one high-severity information-disclosure flaw and a meaningful localhost trust-boundary weakness. Both were reproduced during this audit and fixed for v0.2.0.

The current codebase is appropriate for local/private use after the v0.2.0 hardening release, but it should **not yet be described as an internet-facing production web application**. The built-in server uses Python's `http.server`, which Python explicitly does not recommend for production use. Remote deployments should remain behind a private/authenticated access layer until the server layer is replaced or separated from the application.

## Scope

Reviewed:

- Python HTTP server and request routing
- collection/path handling
- image discovery and thumbnail generation
- review-state persistence
- browser UI sinks and server-generated values
- package/dependency state
- GitHub Actions and repository security settings
- deployment documentation

Testing performed:

- manual source review
- traversal and arbitrary-file-read probes
- hostile `Host` header probe
- Bandit static scan
- `pip-audit`
- unit/regression tests
- package/wheel smoke tests
- GitHub repository security-setting review

## Findings

| ID | Severity | Finding | Status |
|---|---|---|---|
| AV-001 | High | Non-image files inside a registered directory could be fetched by guessed URL even though the UI only listed images. Reproduced against `.env`. | **Fixed in v0.2.0** by enforcing the image allowlist at the file-serving boundary and adding regression coverage. |
| AV-002 | High/Medium | v0.1.0 accepted arbitrary HTTP `Host` headers. For a localhost service, that enables DNS-rebinding-style access if a hostile site can rebind its origin to loopback. | **Fixed in v0.2.0** with explicit trusted-host validation. Non-loopback binds require configured trusted hosts. |
| AV-003 | Medium | The built-in web server is based on `http.server`, which Python documents as not recommended for production and as implementing only basic security checks. | **Open. P0 roadmap.** Keep listener on loopback/private access until replaced with a production-grade serving layer. |
| AV-004 | Medium | Thumbnail decoding is performed inside request threads. Large-but-legal or parser-complex images can consume substantial CPU/RAM; concurrent requests can amplify this. | **Partially mitigated in v0.2.0** with decompression-bomb handling plus configurable source-byte/pixel limits and inert fallback previews. Worker isolation/concurrency quotas remain P0. |
| AV-005 | Medium | Every gallery refresh recursively walks the collection and opens raster headers. Large trees can create O(N) latency and resource amplification. | **Open. P0 roadmap.** Replace repeated scans with an indexed catalog plus incremental watcher/rescan. |
| AV-006 | Medium | v0.1.0 review state used JSON files and could race across processes. | **Fixed in v0.2.0** by moving review/comment/seen state to transactional SQLite with WAL and automatic legacy migration. Collection registration remains a small atomic JSON file. |
| AV-007 | Medium | SVG is active web content when opened as a document. | **Fixed for the viewer surface in v0.2.0**: SVG gallery previews are inert generated placeholders and original SVG files are served as attachment downloads, not rendered inline. |
| AV-008 | Medium operational | Remote deployment needs authentication and request-forgery protection in addition to trusted Host validation. | **Materially mitigated in v0.2.0** with per-process CSRF tokens, Origin/Host validation, and optional built-in HTTP Basic authentication. Private network/authenticated reverse proxy remains the recommended outer boundary. |
| AV-009 | Low/Medium | The direct dependency requirement originally allowed `Pillow>=10.0`, while the audited environment uses current Pillow 12.3.0. Broad lower bounds can allow an already-installed older release to satisfy the requirement. | **Partially fixed in v0.2.0** by raising the supported floor to Pillow 12.1.1 and capping the next major. Reproducible release constraints/SBOM remain P1. |
| AV-010 | Low | CI originally referenced GitHub Actions by mutable major tags. | **Fixed** by pinning Actions to immutable commit SHAs. |
| AV-011 | Low | Dependabot alerts/security updates and CodeQL default setup were not enabled at launch. | **Fixed during audit.** Dependabot security updates, secret scanning/push protection, and CodeQL default setup are enabled. |
| AV-012 | Low | `main` had no branch protection/ruleset at audit start. | **Fixed during audit.** An active `Protect main` ruleset blocks deletion/force-push and requires the Python matrix plus security audit checks for ordinary PR merges, with repository-admin emergency bypass. |
| AV-013 | Informational | Client UI uses `innerHTML`, but values placed into markup are either server-constructed/allowlisted or HTML-escaped. No exploitable DOM XSS was identified in the reviewed paths. | Monitor with regression tests as UI grows. |
| AV-014 | Informational | Generated JPEG thumbnails do not intentionally copy EXIF/XMP metadata. `Open original` intentionally serves the original file and therefore exposes whatever metadata the source contains to authorized viewers. | Expected behavior; document for shared/remote deployments. |

## Verification snapshot

- `python -m unittest discover -v`: **26 tests passing**
- `bandit -r asset_viewer`: **0 findings**
- `pip-audit --skip-editable`: **0 known dependency vulnerabilities**

## Confirmed positive controls

- Loopback bind is the default.
- Registered absolute filesystem paths are not returned by the browser API.
- `Path.resolve()` plus parent containment blocks `../` traversal outside registered roots.
- v0.2.0 file serving enforces the same image extension allowlist used for discovery.
- POST review status is allowlisted to `approved`, `maybe`, `rejected`, or clear.
- State-changing browser requests require a same-host `Origin`, reducing CSRF exposure.
- Review requests are JSON and no permissive CORS policy is present.
- Response headers include CSP, `nosniff`, `frame-ancestors 'none'`, same-origin opener/resource policies, and a restrictive permissions policy.
- Full-size originals are streamed instead of loaded wholly into process memory.
- Local registry/review state is stored with private directory/file permissions where the OS supports POSIX modes.
- `pip-audit` reported no known vulnerabilities in the audited installed dependency set (Pillow 12.3.0).
- Bandit now reports no findings after the exception-handling path was tightened.
- GitHub secret scanning and push protection are enabled.

## Security priorities

### P0 — before calling remote deployment production-ready

1. Replace `http.server` with a production-grade serving layer or expose Asset Viewer as a WSGI/ASGI app intended to sit behind one.
2. Extend the new SQLite review store into a fully indexed asset catalog with stable asset identifiers and migrations.
3. Isolate image decoding from request handling with bounded workers, time/memory limits, and atomic thumbnail generation.
4. Replace the new bounded recursive scan with indexed/incremental collection scanning for large libraries.
5. Mature the new Basic-auth/CSRF remote mode with trusted-proxy identity or stronger session authentication where multi-user deployments require it.
6. Continue expanding end-to-end security regression tests beyond the now-covered raw-file access, Host/Origin/CSRF validation, SVG policy, traversal/symlink escape, auth, concurrent writes, and permissions into malformed-image fuzzing and request-budget tests.

### P1 — supply-chain and release hardening

- Raise and regularly test the minimum supported Pillow release.
- Produce a dependency lock/constraints file for release builds and an SBOM artifact.
- Keep branch rules and required security checks aligned with CI as workflows evolve.
- Add release provenance/signing where practical.
- Add structured security logs without leaking source paths by default.
- Fuzz URL/path parsing and image metadata boundaries.

## References

- Python `http.server` warning: https://docs.python.org/3/library/http.server.html
- Pillow decompression-bomb guidance: https://pillow.readthedocs.io/en/stable/reference/Image.html
- Pillow security guidance: https://pillow.readthedocs.io/en/stable/handbook/security.html
- GitHub Actions secure-use guidance: https://docs.github.com/en/actions/reference/security/secure-use
- GitHub repository security guidance: https://docs.github.com/en/code-security/getting-started/quickstart-for-securing-your-repository

## Audit conclusion

**v0.1.0 should be considered superseded for security reasons.** v0.2.0 closes the confirmed disclosure/rebinding issues and adds transactional review state, CSRF, optional authentication, SVG isolation, resource limits, security regression coverage, and supply-chain controls. Remaining P0 work is primarily production serving, indexed/stable asset identity, and process-isolated preview generation before internet-facing or larger multi-user deployment is recommended.
