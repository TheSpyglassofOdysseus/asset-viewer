# Deployment

## Local workstation

The safest default is also the simplest:

```bash
asset-viewer serve
```

This listens on `127.0.0.1:8160`.

## Private remote access

For a server, keep Asset Viewer bound to localhost and proxy it through your existing private access layer.

Example service command:

```bash
asset-viewer serve --host 127.0.0.1 --port 8160
```

A reverse proxy can then terminate TLS and provide authentication or VPN-only access.

## systemd example

```ini
[Unit]
Description=Asset Viewer
After=network.target

[Service]
Type=simple
User=assetviewer
ExecStart=/opt/asset-viewer/.venv/bin/asset-viewer serve --host 127.0.0.1 --port 8160
Restart=on-failure
Environment=ASSET_VIEWER_HOME=/var/lib/asset-viewer
Environment=ASSET_VIEWER_CACHE=/var/cache/asset-viewer

[Install]
WantedBy=multi-user.target
```

Give the service account read permission only to the image folders it needs to review. Asset Viewer itself never needs write permission to registered source directories.

## Backups

The source images belong to their projects. If review decisions matter, back up the Asset Viewer data directory containing `collections.json` and `reviews.json`. Thumbnail cache files can always be regenerated.
