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
asset-viewer add "$REPO/artifacts/brand-concepts" "Brand Concepts"
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

The manifest includes status, comments, new/seen timestamps, and update timestamps. This is preferred over asking an agent to infer approval state from chat text.
