# Security policy

## Deployment model

Asset Viewer is designed to run on a trusted machine and bind to `127.0.0.1` by default. Optional HTTP Basic authentication is available through `ASSET_VIEWER_PASSWORD`; a private network or authenticated reverse proxy remains the recommended outer access boundary.

If you need remote access, place Asset Viewer behind a trusted access boundary such as a VPN/private network or an authenticated reverse proxy. Configure each browser-facing hostname with `--trusted-host`; unexpected Host headers are rejected. Do not expose the raw application listener directly to the public internet.

Asset Viewer treats SVG as active content: gallery previews use inert placeholders and opening an SVG original is forced to download as an attachment rather than rendered inline. Registered folders should still be treated as potentially hostile input and kept within the documented image/resource limits.

## Reporting a vulnerability

Please open a GitHub security advisory for the repository when possible. Avoid posting exploit details in a public issue before a fix can be prepared.
