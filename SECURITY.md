# Security policy

## Deployment model

Asset Viewer is designed to run on a trusted machine and bind to `127.0.0.1` by default. It does **not** currently implement user authentication or authorization.

If you need remote access, place Asset Viewer behind a trusted access boundary such as a VPN/private network or an authenticated reverse proxy. Do not expose the raw application listener directly to the public internet.

Registered folders should contain content you trust. In particular, SVG is a web-capable format and should be treated as active/untrusted content when sourced from unknown parties.

## Reporting a vulnerability

Please open a GitHub security advisory for the repository when possible. Avoid posting exploit details in a public issue before a fix can be prepared.
