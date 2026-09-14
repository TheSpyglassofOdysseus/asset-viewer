# Agent workflow

Asset Viewer was built around a simple boundary: **agents create files; humans review them; the viewer does not become the source of truth.**

## Recommended contract

When an agent produces images:

1. Write them to a stable project-owned output directory.
2. Register that directory once with Asset Viewer.
3. Leave the originals where they are.
4. Tell the human which Asset Viewer collection contains the new work.
5. Treat gallery review state as feedback metadata, not as a file-moving operation.

Example:

```bash
asset-viewer add "$REPO/artifacts/brand-concepts" "Brand Concepts" --group "Project / Brand"
```

Agent handoff:

> New brand concepts are in Asset Viewer under **Brand Concepts**. The originals remain in `artifacts/brand-concepts`.

## Why this matters

Without a review surface, image-producing agents often create accidental workflow debt:

- giant batches embedded into chat clients;
- temporary uploads that become de facto storage;
- cloud-drive copies that drift from the project originals;
- IDE-based review that is slow and visually poor;
- uncertainty about which variants have been approved.

The viewer removes that pressure by giving both the agent and the human one predictable interface.

## Suggested repository instruction

```md
## Image asset review

When this repo creates image assets for human review, keep originals in the project-owned output directory and register that directory with Asset Viewer using `asset-viewer add`. Tell the user the collection name when the work is ready. Do not use chat attachments or cloud-drive duplication as the default review workflow.
```

## Closing the loop

After a human reviews a collection, an agent can consume the decisions directly:

```bash
asset-viewer reviews --collection brand-concepts --json
```

Or export a stable manifest for another process:

```bash
asset-viewer export-manifest --collection brand-concepts --output review-manifest.json
```

The manifest includes status, comments, new/seen timestamps, update timestamps, and variant-family metadata when related attempts have been grouped. This is preferred over asking an agent to infer approval state from chat text.

## Variant families

Generative work often arrives as related attempts rather than unrelated files. Group those attempts in Asset Viewer without renaming or moving the originals:

```bash
asset-viewer family-create brand-concepts "Logo exploration" concept-v1.png concept-v2.png concept-v3.png --json
asset-viewer family-prefer brand-concepts <family-id> concept-v3.png --json
asset-viewer families brand-concepts --json
```

Family membership follows stable asset IDs across ordinary same-filesystem renames. Family create/add/remove/prefer/rename/delete actions also appear in the ordered event feed, so an agent can react to lineage and preference changes as structured feedback.

## Provenance and approved handoff

When generation context is available, attach it to the stable asset rather than encoding it into filenames or moving the original:

```bash
asset-viewer metadata brand-concepts concept-17.png --set source_project=Whetstone --set model=imagegen --set run_id=brand-007 --json
```

After review, consume the exact approved set with:

```bash
asset-viewer handoff brand-concepts --output approved-handoff.json
```

The handoff contains stable IDs, relative paths, review hashes, notes, annotations, family/preferred state, and provenance. It does not expose absolute server paths. `--copy-to` is available only when an explicit separate copy is wanted; originals remain untouched.

## Waiting for explicit human completion

A non-empty folder is not the same thing as a finished human review. Asset Viewer exposes explicit collection completion so orchestrators can distinguish those states:

```bash
asset-viewer pending --collection brand-concepts --json
```

Exit code `2` means human review is still pending. Exit code `0` means the collection was explicitly marked complete after every asset received a review status.

Once decisions are available:

```bash
asset-viewer reviews --collection brand-concepts --json
```

If a human changes their mind, Asset Viewer records review events and supports undo/history without touching the source image:

```bash
asset-viewer history brand-concepts concept-17.png --json
asset-viewer undo brand-concepts concept-17.png
```


## Event-driven consumption

Long-running agents do not need to repeatedly diff full manifests. Read ordered events using a cursor:

```bash
asset-viewer events --collection brand-concepts --after 42 --json
```

For orchestration that should stop until the reviewer explicitly finishes:

```bash
asset-viewer wait-for-review --collection brand-concepts --timeout 900 --json
```

A successful wait is stronger than "there are files in the folder": it requires a complete filesystem scan, present assets, classifications for every current asset, and explicit human completion. If source bytes change after approval or a file disappears, the collection becomes pending again.

## Stable identity and deep links

Each cataloged asset receives a stable UUID. An unambiguous same-filesystem rename keeps the same identity, review history, and decision. Replacing the file contents invalidates the old decision.

Use a stable asset link when handing one exact item to a human:

```bash
asset-viewer asset-url brand-concepts concept-17.png --base-url https://viewer.example.com
```

Manifests retain deleted assets as `present: false` tombstones by default so an agent can distinguish deletion from omission. Use `--present-only` when only the current filesystem set matters.


## MCP adapter

Asset Viewer v0.8 can expose the same durable review protocol through an optional MCP v2 adapter. Install the optional dependency and run `asset-viewer mcp` (stdio by default). The MCP layer is an adapter only: SQLite/catalog/review state remains canonical, and agents receive the same collections, manifests, pending/completion state, events, human Activity, provenance metadata, approved handoff, annotations, families, stable URLs, and refresh semantics already available through the CLI/API.
