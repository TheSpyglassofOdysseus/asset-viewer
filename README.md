# Asset Viewer

[![CI](https://github.com/TheSpyglassofOdysseus/asset-viewer/actions/workflows/ci.yml/badge.svg)](https://github.com/TheSpyglassofOdysseus/asset-viewer/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)

> A local-first visual review gallery for AI-generated images and project asset folders.

Asset Viewer gives humans a clean place to **see, compare, approve, defer, and reject image assets without moving the originals**.

It was built for a simple workflow problem: agents and creative tools are increasingly good at producing images, but the review step often degenerates into oversized chat attachments, IDE file trees, temporary uploads, or copies scattered across cloud drives. Asset Viewer keeps review separate from storage.

![Asset Viewer demo](docs/screenshot.png)

### Precision review

Open an exact asset, leave point/region feedback, compare variants with linked zoom/pan, and keep the full-resolution original out of the routine review path.

![Asset Viewer precision review](docs/precision-review.png)

## Why it exists

A good image pipeline should be boring:

1. A tool or agent writes images to the project folder that owns them.
2. That folder is registered with Asset Viewer once.
3. A human opens one stable gallery URL and reviews the work.
4. Approval state lives beside the workflow, not inside the original files.

No import job. No duplicate asset library. No requirement to upload the batch to a chat window just to inspect it.

## Features

- **Register existing folders in place** — originals never need to move.
- **Fast thumbnail grid** with lazy loading and disk-cached previews.
- **Full-screen carousel** using bounded review-size previews; full-resolution originals load only on explicit request.
- **Approve / Maybe / Reject** states stored separately from source files.
- **Review notes/comments plus pinned point/region annotations** attached to the exact asset without modifying it; spatial feedback is content-fingerprinted and becomes stale if the underlying pixels change.
- **New/unseen tracking** so recurring collections show what changed.
- **Variant/version families** that group related attempts without moving or renaming originals, with preferred/latest semantics and one-click family comparison.
- **Batch review plus side-by-side / overlay / difference comparison** with linked or independent zoom/pan for precise variant triage.
- **Stable collection and asset deep links** for direct handoff to a gallery or exact image.
- **Machine-readable manifests and ordered event feeds** through the CLI and read-only JSON API.
- **Explicit review completion** with automation-friendly pending state.
- **Review history and undo** for status/comment decisions.
- **Stable asset IDs, SHA-256 review fingerprints, and durable cataloging** so review state survives renames while replacements/deletions invalidate stale completion safely.
- **Metadata-aware search and sorting** across filenames, paths, notes, family names, and optional provenance fields such as project/model/prompt/run ID.
- **Human-readable Activity view** backed by the same durable event stream agents consume.
- **Approved-set handoff manifests** with exact stable IDs, hashes, decisions, annotations, family/preferred state, and provenance; optional copying is explicit and never mutates originals.
- **Grouped collection navigation** that organizes the viewer without moving project folders.
- **Context-aware selectors and menus** so capabilities grow without turning the toolbar into a button farm.
- **Keyboard review**: arrow keys to navigate; `A`, `M`, `R` to classify.
- **Multiple collections** behind one viewer URL.
- **Recursive discovery** of PNG, JPEG, WebP, GIF, AVIF, BMP, and SVG assets.
- **Local-first security posture** — localhost by default, Waitress production serving, CSRF/Host enforcement, safe SVG handling, process-isolated bounded decoding, and optional Basic auth.
- **Agent-friendly CLI** that is easy to call from scripts and repo instructions.
- **Minimal stack** — Python, Pillow, Waitress, SQLite from the standard library, and a small browser UI. No external database service required.

## Quick start

Asset Viewer requires Python 3.10+. The easiest install from GitHub is with `pipx`:

```bash
pipx install git+https://github.com/TheSpyglassofOdysseus/asset-viewer.git
asset-viewer demo
asset-viewer serve
```

Or install from a clone for development:

```bash
# From a clone
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Register a real image folder
asset-viewer add /absolute/path/to/project/images "Project Images"

# Start the viewer
asset-viewer serve
```

Open `http://127.0.0.1:8160`.

Want to try it without your own images?

```bash
asset-viewer demo
asset-viewer serve
```

The demo command creates a small set of synthetic sample assets and registers them as a collection.

### Live updates and reports

`asset-viewer serve` watches registered folders by default. Filesystem events trigger the normal bounded reconciliation path, while periodic full reconciliation remains the correctness fallback. Use `--no-watch` to disable it or `asset-viewer watch` to run watching separately.

The collection **Actions** menu opens a printable review summary for the active collection. The same report is available from the CLI:

```bash
asset-viewer report --collection project-images --output review.html
asset-viewer report --collection project-images --format markdown --output review.md
```

### Optional MCP adapter

Install the optional MCP dependency and run the adapter over stdio:

```bash
pipx inject local-asset-viewer 'mcp>=2,<3'
asset-viewer mcp
```

The MCP layer reuses the existing review protocol; it does not create a second database or review state. It exposes collection state, reviews, completion/pending state, ordered events, annotations, variant families, stable browser URLs, and explicit refresh tools.

## CLI

```text
asset-viewer add PATH [LABEL]      Register an image folder (`--group` optionally groups navigation)
asset-viewer remove SLUG|PATH      Remove a collection
asset-viewer list                  List registered folders
asset-viewer capabilities --json   Describe the stable agent/API contract
asset-viewer scan [--collection]   Discover/refresh asset metadata
asset-viewer reviews [--collection]  Read review state (add --json for agents)
asset-viewer export-manifest       Export review state as JSON
asset-viewer pending                Exit 2 while human review is still pending
asset-viewer events                 Read ordered review events for automation
asset-viewer wait-for-review        Wait on the explicit human-completion gate
asset-viewer complete SLUG          Mark a fully-reviewed collection complete
asset-viewer reopen SLUG            Reopen collection review
asset-viewer history SLUG REL       Show review history for one asset
asset-viewer undo SLUG REL          Undo the latest review/comment change
asset-viewer collection-url SLUG    Print the stable collection handoff URL
asset-viewer asset-url SLUG ASSET   Print a stable deep link to one asset
asset-viewer families SLUG           List variant/version families
asset-viewer family-create ...        Group related assets without moving them
asset-viewer family-add/remove ...    Maintain family membership
asset-viewer family-prefer ...        Set/clear the preferred family member
asset-viewer annotations SLUG ASSET List point/region feedback for one asset
asset-viewer annotate ...            Create precise point/region feedback
asset-viewer cache [status|prune]    Inspect/prune generated preview cache
asset-viewer report ...              Export a printable HTML/Markdown review report
asset-viewer metadata SLUG ASSET ... Read/update optional provenance metadata
asset-viewer activity ...            Read recent human-readable collection activity
asset-viewer handoff SLUG ...        Export the exact approved asset set
asset-viewer watch                   Watch registered folders and reconcile changes
asset-viewer mcp                     Run the optional MCP adapter for agents
asset-viewer annotation-update ...   Resolve/reopen/edit an annotation
asset-viewer annotation-delete ...   Delete an annotation
asset-viewer doctor                Check state and deployment prerequisites
asset-viewer serve                 Start the web viewer
asset-viewer demo                  Create/register synthetic demo assets
```

Common server usage:

```bash
asset-viewer add /srv/renders/acme "Acme Renders" --group "Client / Acme"
asset-viewer add /home/me/project/output "Project Output"
asset-viewer list
asset-viewer serve --host 127.0.0.1 --port 8160
```

## Designed for agents

Asset Viewer is intentionally easy to make part of an agent contract. Put something like this in `AGENTS.md`, `CLAUDE.md`, or your automation instructions:

```md
## Image review

When this repository creates images for human review:

1. Keep originals in the project-owned output folder.
2. Register that folder with:
   `asset-viewer add /absolute/path/to/images "Friendly Name"`
3. Tell the human the new assets are available in Asset Viewer.
4. Do not upload full-resolution batches to chat merely for review.
```

That turns the handoff into a predictable sentence: **“I added the new images to Asset Viewer.”**

Automation can now close the loop explicitly:

```bash
asset-viewer pending --collection project-images --json
# exit code 2 = human review still required
# exit code 0 = review explicitly completed

asset-viewer reviews --collection project-images --json
asset-viewer metadata project-images concept-17.png --set model=imagegen --set run_id=brand-007 --json
asset-viewer handoff project-images --output approved-handoff.json
asset-viewer events --collection project-images --after 0 --json
asset-viewer wait-for-review --collection project-images --timeout 900 --json
asset-viewer collection-url project-images --base-url https://viewer.example.com
asset-viewer asset-url project-images concept-17.png --base-url https://viewer.example.com
```

See [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) for a fuller pattern and [docs/API.md](docs/API.md) for the versioned machine-readable contract.

## Data model

Asset Viewer does not ingest or copy your originals.

By default it stores only:

```text
~/.local/share/asset-viewer/
├── collections.json    # registered source folders
└── asset-viewer.db     # transactional catalog, stable IDs, review/events state

~/.cache/asset-viewer/
└── *.jpg               # generated thumbnails
```

Override the data locations with `ASSET_VIEWER_HOME` and `ASSET_VIEWER_CACHE`.

Deleting Asset Viewer does not delete your project images.

## Remote access and security

Asset Viewer binds to localhost by default. For remote/private deployments it also supports optional HTTP Basic authentication with `ASSET_VIEWER_PASSWORD`, but an authenticated reverse proxy/private network remains the preferred outer boundary.

For remote use, keep the application on `127.0.0.1` and put it behind an authenticated/private reverse proxy such as Tailscale Serve, Caddy with authentication, nginx behind your VPN, or an equivalent trusted access layer. Reverse-proxy deployments must explicitly allow the browser-facing hostname, for example:

```bash
ASSET_VIEWER_PASSWORD='use-a-secret-manager' asset-viewer serve --host 127.0.0.1 --trusted-host gallery.example.com
```

`asset-viewer serve` now uses Waitress as its production serving layer. Direct non-loopback binds require both a trusted Host configuration and built-in authentication by default. `--allow-unauthenticated-remote` is an explicit escape hatch only for deployments where a trusted private/authenticated boundary already provides access control. Keep TLS and any broader identity/SSO policy at a trusted reverse proxy or private-network boundary.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), [SECURITY.md](SECURITY.md), the security-audit series, and the [final public-release sign-off](docs/PUBLIC_RELEASE_SIGNOFF_2026-09-13.md). The feature audits record the competitive/product analysis behind the roadmap.

## Project philosophy

Asset Viewer is deliberately not a DAM, cloud sync service, image editor, or source-of-truth database. Those products solve different problems.

The job here is narrower:

> **Make image review a first-class, stable interface while leaving storage ownership where it already belongs.**

That separation is especially useful for generative workflows, where image volume can be high and most variants are temporary.

## Development

```bash
git clone https://github.com/TheSpyglassofOdysseus/asset-viewer.git
cd asset-viewer
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover -v
```

Run a development instance with isolated state:

```bash
export ASSET_VIEWER_HOME="$PWD/.dev-data"
export ASSET_VIEWER_CACHE="$PWD/.dev-cache"
asset-viewer demo --path "$PWD/.demo-assets"
asset-viewer serve --port 8160
```

## Engineering documents

- [Agent/API contract](docs/API.md)
- [Feature and benefit analysis](docs/FEATURE_ANALYSIS.md)
- [v0.4 feature audit](docs/FEATURE_AUDIT_2026-09-13.md)
- [v0.5 feature and benefit audit](docs/FEATURE_AUDIT_2026-09-13_V05.md)
- [Initial security audit](docs/SECURITY_AUDIT_2026-09-13.md)
- [Round-two security audit](docs/SECURITY_AUDIT_2026-09-13_ROUND2.md)
- [Round-three production/precision-review security audit](docs/SECURITY_AUDIT_2026-09-13_ROUND3.md)
- [Final public-release sign-off](docs/PUBLIC_RELEASE_SIGNOFF_2026-09-13.md)
- [Round-two feature audit](docs/FEATURE_AUDIT_2026-09-13_ROUND2.md)
- [Deployment guide](docs/DEPLOYMENT.md)
- [Product roadmap](docs/ROADMAP.md)

## Roadmap

The roadmap is organized around a deliberate progression: **production hardening → human/agent feedback → agent-native automation → serious creative review → collaboration**.

The core human→agent loop now includes precise annotations, linked comparison, variant families, live watching, printable reports, optional provenance metadata, a human Activity view, exact approved-set handoff, grouped collection navigation, and an optional MCP adapter. The next product frontier is project-native registration/adapters, saved views/command palette, webhook integration, stronger identity for collaborative deployments, and signed release provenance while preserving the local-first review-plane boundary.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the phased feature/benefit analysis and roadmap.

Issues and focused pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Releases

Tagged releases publish a wheel, source archive, CycloneDX SBOM, and SHA-256 checksums. Release CI also runs the security and dependency checks described in the audit documentation.

## License

MIT. See [LICENSE](LICENSE).
