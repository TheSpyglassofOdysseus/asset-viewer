# AGENTS.md

## Project intent

Asset Viewer is a small, local-first visual review surface for existing image folders. Keep it storage-agnostic and avoid turning it into a second source-of-truth DAM.

## Development checks

Before committing backend or CLI changes:

```bash
python -m unittest discover -v
python -m compileall -q asset_viewer tests
bandit -r asset_viewer
pip-audit --skip-editable
```

For UI changes, use synthetic demo assets rather than private project imagery:

```bash
export ASSET_VIEWER_HOME="$PWD/.dev-data"
export ASSET_VIEWER_CACHE="$PWD/.dev-cache"
asset-viewer demo --path "$PWD/.demo-assets"
asset-viewer serve
```

Do not commit machine-specific absolute paths, tokens, private review state, or user image collections.
