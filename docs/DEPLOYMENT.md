# Deployment

## Local workstation

The safest default is also the simplest:

```bash
asset-viewer serve
```

This listens on `127.0.0.1:8160` using Waitress. Use `--development-server` only for debugging the legacy stdlib path.

## Private remote access

For a server, keep Asset Viewer bound to localhost and proxy it through your existing private access layer.

Example service command:

```bash
ASSET_VIEWER_PASSWORD="use-a-secret-manager" asset-viewer serve --host 127.0.0.1 --port 8160 --trusted-host gallery.example.com
```

A reverse proxy can then terminate TLS and provide authentication or VPN-only access. `--trusted-host` is required for the browser-facing hostname so the local listener can reject unexpected Host headers. Repeat the option if more than one hostname is legitimate.

## Direct non-loopback binding

A direct bind such as `--host 0.0.0.0` is intentionally harder to enable. It requires at least one `--trusted-host` **and** built-in Basic authentication through `ASSET_VIEWER_PASSWORD`. If another private/authenticated boundary already provides access control, `--allow-unauthenticated-remote` can explicitly acknowledge that design.

The normal server is Waitress. Prefer loopback + a TLS-terminating authenticated/private reverse proxy for remote access. The legacy Python stdlib server is development-only and requires `--development-server`. Built-in Basic auth is not encryption; do not send credentials over untrusted cleartext HTTP.

## Resource limits

Large or hostile images can consume CPU/RAM during metadata extraction and preview generation. Asset Viewer provides configurable bounds:

```text
ASSET_VIEWER_MAX_SCAN_FILES=50000
ASSET_VIEWER_MAX_SCAN_SECONDS=10
ASSET_VIEWER_MAX_THUMBNAIL_BYTES=262144000
ASSET_VIEWER_MAX_IMAGE_PIXELS=50000000
ASSET_VIEWER_THUMBNAIL_WORKERS=2
ASSET_VIEWER_SCAN_TTL_SECONDS=60
ASSET_VIEWER_PREVIEW_TIMEOUT_SECONDS=15
ASSET_VIEWER_PREVIEW_MEMORY_MB=768
ASSET_VIEWER_METADATA_BATCH_SIZE=512
ASSET_VIEWER_CACHE_MAX_MB=2048
ASSET_VIEWER_CACHE_MAX_AGE_DAYS=30
```

`asset-viewer doctor` reports the effective deployment posture, unavailable collection paths, catalog scan state, Waitress availability, preview-cache state, and resource-limit settings. `asset-viewer cache status` and `asset-viewer cache prune` provide explicit cache management.

If you deliberately embed the WSGI application in a multi-process server rather than using `asset-viewer serve`, set one shared `ASSET_VIEWER_CSRF_TOKEN` for all workers so browser sessions do not receive worker-specific mutation tokens.

## systemd example

```ini
[Unit]
Description=Asset Viewer
After=network.target

[Service]
Type=simple
User=assetviewer
ExecStart=/opt/asset-viewer/.venv/bin/asset-viewer serve --host 127.0.0.1 --port 8160 --trusted-host gallery.example.com
Restart=on-failure
Environment=ASSET_VIEWER_HOME=/var/lib/asset-viewer
Environment=ASSET_VIEWER_CACHE=/var/cache/asset-viewer
EnvironmentFile=/etc/asset-viewer.env

[Install]
WantedBy=multi-user.target
```

Give the service account read permission only to the image folders it needs to review. Asset Viewer itself never needs write permission to registered source directories.

## Backups

The source images belong to their projects. If review decisions matter, back up the Asset Viewer data directory containing `collections.json` and `asset-viewer.db`. Thumbnail cache files can always be regenerated.
