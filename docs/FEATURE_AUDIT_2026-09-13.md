# Feature audit — 2026-09-13

## Executive summary

Asset Viewer should not compete as another photo library or DAM. Its strongest position is narrower and more useful:

> **Asset Viewer is the filesystem-native human review layer for work produced by agents and tools, with decisions that automation can safely consume.**

The current market validates the individual building blocks—favorites, proofing comments, annotations, version comparison, review completion, folder libraries—but generally packages them around uploaded/cloud-owned media or human collaboration. Asset Viewer can differentiate by preserving project-owned files and making the *review decision itself* a durable machine interface.

## Current competitive baseline

### Frame.io

Frame.io V4 provides a sophisticated creative review surface: image annotations, anchored comments, metadata, version stacking/comparison, linked zoom/pan, overlay, and pixel-difference comparison. This establishes the ceiling for serious visual comparison UX.

Sources:
- https://help.frame.io/en/articles/9952618-comparison-viewer
- https://help.frame.io/en/articles/9105322-image-viewer-in-frame-io
- https://help.frame.io/en/articles/9084073-frame-io-v4-legacy-feature-comparison

**Asset Viewer implication:** side-by-side alone is not enough long-term. Overlay/difference, linked zoom/pan, and precise annotations are high-value review primitives. We should implement the subset that serves static generated assets without inheriting a full media-production platform.

### Canto proofing

Canto's proofing interface combines review status, a comment panel, split/version views, zoom/navigation, and comment workflow states.

Source:
- https://support.canto.com/hc/en-us/articles/39166383251601-The-Proofing-Interface-an-overview

**Asset Viewer implication:** review notes should evolve toward anchored visual annotations and resolvable feedback, but only after the agent event/state contract remains stable.

### Pixieset

Pixieset's client proofing supports favorites, per-favorite notes, list sharing, and an explicit "finished selections" handoff.

Source:
- https://website-help.pixieset.com/en/articles/4064071-using-favorite-lists-for-client-proofing

**Asset Viewer implication:** explicit human completion is a real workflow primitive, not a cosmetic status. v0.3/v0.4's completion gate and `wait-for-review` are strategically important.

### Air

Air supports comments and annotations pinned to specific image regions for external reviewers.

Source:
- https://help.air.inc/en/articles/15461804-get-started-on-air-as-a-board-commenter

**Asset Viewer implication:** normalized-coordinate pinned annotations are the best next feedback feature after v0.4 rather than generic threaded chat.

### Immich

Immich can track externally stored filesystem assets, exposes folder view, and rescans external libraries for changes. Its current documentation notes that moving an external asset can lose Immich-side metadata because it may be treated as a new asset.

Sources:
- https://docs.immich.app/features/libraries/
- https://docs.immich.app/features/folder-view/

**Asset Viewer implication:** filesystem-native browsing is not unique by itself. Stable review identity across ordinary rename/move operations is therefore a meaningful differentiator; v0.4 intentionally preserves review state across unambiguous same-filesystem renames.

### FiftyOne

FiftyOne provides an in-app annotation surface for sample metadata and spatial label types, with schema-driven editing and session undo/redo.

Source:
- https://docs.voxel51.com/user_guide/annotation.html

**Asset Viewer implication:** rich ML labeling is a different category from lightweight creative review. Asset Viewer should adopt precise point/region feedback where it helps agents, but avoid turning the core into a dataset-labeling framework.

### Photofield

Photofield is fast and filesystem-oriented, with bulk selections and arbitrary tags/favorites; its tag metadata is currently documented as alpha and stored in its cache database rather than the photos.

Sources:
- https://photofield.dev/features/tags
- https://photofield.dev/configuration

**Asset Viewer implication:** fast folder-backed viewing is table stakes. The product value must live in review semantics, durable history, completion, and agent-readable state rather than gallery layout alone.

## v0.4 capability audit

| Capability | Status | Benefit |
|---|---|---|
| Folder registration without import | Strong | Project/source remains authoritative |
| Cached thumbnail gallery | Strong | Low-bandwidth high-volume browsing |
| Bounded full-screen previews | Strong in v0.4 | Large originals no longer burden routine review |
| Approve / Maybe / Reject | Strong | Minimal useful decision vocabulary |
| Notes/comments | Strong | Agent receives actionable text |
| New/unseen tracking | Strong | Returning reviewer sees new work immediately |
| Batch classification | Strong | Efficient variant triage |
| Search + sort | Good | Filename/path/comment search; time/name/status/size/resolution sorting |
| Side-by-side comparison | Good | 2–4-way visual selection |
| Overlay/difference comparison | Added in v0.4 | Better two-variant inspection |
| Stable collection URL | Strong | Predictable human handoff |
| Stable asset deep link | Added in v0.4 | A specific asset can be referenced without filename fragility |
| Stable asset identity | Added in v0.4 | Rename-safe decisions/history |
| Content-change invalidation + SHA-256 review fingerprint | Added in v0.4 | Old approval cannot silently bless replacement bytes, including same-size/same-timestamp replacements |
| Deleted-asset tombstones | Added in v0.4 | Automation can distinguish deletion from omission |
| Explicit review completion | Strong | Human controls the workflow gate |
| Ordered event feed | Added in v0.4 | Agents can incrementally consume decisions |
| `wait-for-review` | Added in v0.4 | Simple orchestration primitive |
| History + undo | Strong | Human decisions are recoverable/auditable |
| Local/private deployment | Strong | No mandatory SaaS upload |
| Production-grade serving | Gap | `http.server` remains local/private only |
| Process-isolated image decoding | Gap | Concurrency is bounded, but decoder isolation remains |
| Pinned visual annotations | Gap/high-value | Needed for precise creative feedback |
| Variant/version families | Gap/high-value | Generated iterations need grouping semantics |
| Linked zoom/pan | Gap | Important for detailed A/B inspection |
| Reviewer identity/multi-user permissions | Intentional later gap | Not needed for the core solo/agent workflow yet |

## Benefit analysis

### For human reviewers

The primary benefit is **less coordination tax**. A reviewer does not need to know where an agent ran, which IDE has the file tree, or which cloud folder received a duplicate. One stable review surface exposes new work, preserves decisions, and makes comparison fast.

### For agents

The primary benefit is **structured judgment instead of conversational inference**. An agent can wait for explicit completion, consume ordered events, read comments/statuses keyed by stable asset IDs, and confidently distinguish a reviewed file from a subsequently changed one.

### For project integrity

The project owns the bytes; Asset Viewer owns review metadata. v0.4 extends that separation with tombstones, stable identity, and SHA-256-bound decisions so review history remains useful even when the filesystem evolves and stale approval cannot silently follow replacement bytes.

### For self-hosted/server workflows

The viewer turns arbitrary output directories into a review surface without an ingest pipeline. Cached catalog reads reduce repeated filesystem traversal, while explicit refresh/TTL scans keep the model understandable.

## Product priorities after v0.4

### 1. Pinned annotations

Store normalized x/y coordinates, note text, creation/update timestamps, resolution context, and resolved/open state. Expose annotations in the same event/manifest model so an agent can receive instructions such as "remove this object" tied to a precise region.

### 2. Variant/version families

Allow files to be grouped into one concept/version stack without moving them. Keep grouping metadata separate from source files. This turns a flood of generated variants into reviewable concepts.

### 3. Linked zoom/pan comparison

For two same-dimension assets, synchronize viewport transforms across side-by-side, overlay, and difference views. This is the highest-value remaining comparison improvement.

### 4. Filesystem watcher

The catalog already removes recursive scan cost from normal reads. A portable watcher should make new work appear immediately while retaining periodic reconciliation as the correctness fallback.

### 5. Production server + decoder sandbox

These are the remaining blockers before recommending direct, long-running, internet-adjacent service use.

## Features to resist

Do not turn the core into cloud storage, a general DAM taxonomy product, an image editor/generator, chat, or an automatic file organizer. Those dilute the product's strongest contract:

> **Files stay where they belong. Human decisions become durable, reviewable machine state.**
