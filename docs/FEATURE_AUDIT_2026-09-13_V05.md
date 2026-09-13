# Feature and benefit audit — v0.5 — 2026-09-13

## Executive summary

Asset Viewer should continue to avoid competing as a general DAM or cloud proofing suite. Its strongest product position is becoming clearer:

> **Asset Viewer is a filesystem-native visual decision protocol: tools and agents produce files where they already belong, humans review them precisely, and automation receives durable machine-readable judgment.**

v0.5 closes several gaps that separated Asset Viewer from a serious review surface: precise point/region annotations, linked zoom/pan comparison, overlay/difference modes, production serving, isolated preview generation, bounded cache management, and content-bound feedback integrity.

The next differentiator is not more generic collaboration. It is **version/variant structure for generated work**: grouping successive files into one concept while preserving project-owned storage and the review/event protocol.

## Current market baseline

### Frame.io

Frame.io V4 documents anchored comments, annotations, metadata, search, shares, version comparison and version stacking. Its current commenting model lets reviewers anchor feedback to an exact visual location.

Sources:
- https://help.frame.io/en/articles/9084073-frame-io-v4-legacy-feature-comparison
- https://help.frame.io/en/articles/9105251-commenting-on-your-media

**Implication:** precise spatial feedback and version-aware comparison are baseline capabilities for professional review. Asset Viewer should match the useful static-image primitives while remaining filesystem-owned and automation-first.

### Ziflow

Ziflow's current compare workflow supports side-by-side and overlay comparison, synchronized zoom/pan/navigation, and automatic change highlighting.

Source:
- https://www.ziflow.com/blog/how-to-compare-proofs

**Implication:** linked navigation is materially useful, not polish. v0.5 implements linked/independent zoom-pan across comparisons; automatic visual-diff highlighting can remain future work beyond the current difference blend.

### Filestage

Filestage supports side-by-side/overlay comparison, synchronized review, version history, review decisions, and exportable audit reports.

Sources:
- https://help.filestage.io/en/articles/5560093-compare-versions-of-a-file-directly-in-the-viewer
- https://help.filestage.io/en/articles/7872784-chapter-3-managing-versions

**Implication:** version family semantics and a human-readable review report are the most relevant remaining creative-review gaps—not chat, project management, or cloud storage.

### Air

Air supports point, rectangle, and freeform visual annotations tied to comments.

Sources:
- https://help.air.inc/en/articles/5666241-explore-annotations
- https://help.air.inc/en/articles/9006480-leaving-an-annotated-comment

**Implication:** v0.5's point/region model captures the highest-value precision feedback with a small durable data model. Freeform drawing should only be added if real use shows points/regions are insufficient.

### Immich

Immich external libraries track filesystem-owned assets and provide folder-oriented access, but its current external-library documentation notes that moving an asset can cause application-side metadata to be lost because the moved file is treated as a new asset.

Source:
- https://docs.immich.app/features/libraries/

**Implication:** filesystem viewing alone is not differentiation. Asset Viewer's stable identity and rename-preserved review/annotation state are strategically important.

### Photofield

Photofield emphasizes non-destructive local files, progressive multi-resolution viewing, fast indexing, and lightweight tags stored outside originals.

Sources:
- https://photofield.dev/
- https://photofield.dev/features/tags

**Implication:** fast, non-destructive local viewing is table stakes. Asset Viewer's value must remain the semantics around decision, completion, feedback integrity, and agent consumption.

## v0.5 capability audit

| Capability | v0.5 status | Benefit |
|---|---|---|
| Register folders in place | Strong | Zero import/duplication; project remains source of truth |
| Durable SQLite catalog | Strong | Fast cached reads and stable review identity |
| Stable UUID asset identity | Strong | Review/annotations survive unambiguous same-filesystem renames |
| SHA-256 review binding | Strong | Changed bytes cannot inherit stale approval |
| Tombstones | Strong | Deletion is explicit machine state rather than silent omission |
| Bounded review previews | Strong | Large originals do not dominate routine review bandwidth/memory |
| Production runtime | **Added v0.5** | Waitress replaces the development server as default |
| Isolated image decoding | **Added v0.5** | Decoder failures/timeouts are contained in disposable workers |
| Cache budgets/pruning | **Added v0.5** | Long-running installations do not grow preview cache without bound |
| Approve / Maybe / Reject | Strong | Minimal useful decision vocabulary |
| Notes/comments | Strong | Actionable textual instruction |
| Point/region annotations | **Added v0.5** | Human can say *where*, not only *what* |
| Content-bound annotation staleness | **Added v0.5** | Visual feedback cannot silently refer to replaced pixels |
| Annotation resolve/reopen | **Added v0.5** | Feedback becomes an actionable task list without adding project management |
| Batch review | Strong | Efficient triage of generated batches |
| Search/sort | Good | Useful at hundreds/thousands of assets |
| Side-by-side compare | Strong | 2–4 variant inspection |
| Overlay/difference compare | Strong | Better inspection of subtle visual changes |
| Linked/independent zoom-pan | **Added v0.5** | Detailed A/B inspection stays aligned |
| Stable collection/asset links | Strong | Agents can hand a human the exact review target |
| Explicit completion | Strong | Human controls when automation may continue |
| Review history/undo | Strong | Decisions are recoverable/auditable |
| Ordered event feed | Strong | Incremental automation without UI scraping |
| `wait-for-review` | Strong | Simple human-in-the-loop orchestration primitive |
| Version/variant families | **Primary remaining product gap** | Generated iterations need concept-level structure |
| Filesystem watcher | Gap | New work still appears on refresh/TTL reconciliation rather than immediately |
| Generation metadata | Gap | Prompt/model/seed/provenance could improve agent iteration context |
| Human-readable review report/contact sheet | Gap | Useful for handoff/archive without becoming source storage |
| Multi-user identity/permissions | Deliberately later | Not necessary for the core solo/agent workflow yet |

## Benefit analysis

### Human reviewer: less coordination, more precision

A human no longer needs to locate server paths, open an IDE, download a batch, or explain "the thing near the left edge" in prose. The collection/deep-link contract gets them to the work; linked comparison and annotations capture judgment where it matters.

### Agent: judgment becomes an API, not an inference problem

The agent can discover capabilities, wait for explicit completion, consume ordered events, inspect comments and normalized annotations, and key state to stable asset IDs. It can tell the difference between "approved," "approved but later replaced," "deleted," "renamed," "commented," and "review still pending."

### Project integrity: storage ownership stays where it belongs

Asset Viewer never needs to become the canonical asset store. The project owns bytes; Asset Viewer owns reversible review/catalog metadata. That keeps the system compatible with local folders, Git workspaces, NAS, object-store mounts, render outputs, and future storage systems.

### Operator: long-running review is now practical

Waitress, process-isolated decoding, cache budgets, SQLite transactions, bounded scans, and `doctor` move Asset Viewer from a convenient prototype toward dependable private infrastructure.

### Open-source adopter: small mental model

The system has one core workflow and a small protocol. It can be adopted by any generator/tool capable of writing files and invoking a CLI without requiring a particular AI vendor, DAM, cloud account, or orchestration framework.

## Product priorities after v0.5

### 1. Variant/version families

Add a lightweight grouping layer that can express "these six files are iterations of the same concept" without moving or renaming source files. Support manual grouping first, then optional filename heuristics. A family should expose latest/preferred member, review history across variants, and direct compare.

This is the highest-value next feature because generative workflows produce *sets of related attempts*, not merely unrelated files.

### 2. Filesystem watcher with reconciliation fallback

Use a portable watcher to make additions/renames/removals visible quickly, while retaining periodic full reconciliation as the correctness mechanism. The watcher should be an optimization, never the only source of truth.

### 3. Generation/provenance metadata adapters

Allow sidecar JSON or pluggable extractors to display prompt/model/seed/job/revision metadata when projects already produce it. Do not write metadata into originals by default.

### 4. Review report/contact-sheet export

Produce a portable HTML/PDF/contact-sheet style summary of approved/rejected assets, comments, annotations, and timestamps for archival/handoff. Keep the JSON manifest as the authoritative machine format.

### 5. Push adapters after the protocol stabilizes

Webhook/MCP/plugin adapters can translate the existing event feed and completion semantics into push workflows. They should remain adapters over the core protocol rather than new sources of truth.

## Features to resist

Do not turn the core into:

- cloud storage/sync;
- a general DAM taxonomy system;
- Slack/chat;
- a project-management suite;
- an image generator/editor;
- a destructive file organizer;
- an enterprise identity platform before shared-review demand exists.

The product remains strongest when **files stay where the creating project put them and human judgment becomes durable machine state.**
