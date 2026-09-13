# Asset Viewer — Feature and Benefit Analysis

## Product thesis

Asset Viewer is not another place to store images. It is the **human review surface for images that already belong somewhere else**.

That distinction is the product.

Agents, renderers, design tools, test systems, and repositories already know where to write files. The missing layer is a fast, stable, low-friction way for a human to inspect those files and send decisions back without forcing the assets through chat, an IDE, or a second storage system.

## Primary users

### 1. AI-assisted builders and operators

They generate many visual variants from agents and need one predictable handoff: "the images are in Asset Viewer."

**Benefit:** removes file-transfer choreography from agent workflows and keeps chats lightweight.

### 2. Developers producing screenshots, renders, reports, and visual test artifacts

They already have artifacts in project folders but lack a pleasant visual review interface.

**Benefit:** turns arbitrary build/output directories into reviewable collections without modifying build pipelines.

### 3. Designers and solo creative teams

They iterate locally or on a server and need fast approve/maybe/reject review without introducing a full DAM.

**Benefit:** adds decision state without moving or renaming source assets.

### 4. Privacy-sensitive/self-hosted users

They want remote visual review without uploading source assets to a SaaS vendor.

**Benefit:** the source filesystem remains authoritative and deployment can remain private.

## Existing feature value

| Capability | User benefit | Strategic value |
|---|---|---|
| Register folders in place | No import or duplicate copy step | Preserves source-of-truth ownership |
| One stable gallery URL | Humans know where to go every time | Makes agent handoffs predictable |
| Cached thumbnails | Fast browsing without loading originals | Keeps review cheap on client and network |
| Full-screen carousel | Rapid visual inspection | Better than IDE/file-tree review |
| Approve / Maybe / Reject | Captures the simplest useful decision | Establishes human-in-the-loop state |
| Multiple collections | One viewer can cover many projects | Avoids one-off gallery deployments |
| Keyboard controls | Faster review of large batches | Supports high-throughput workflows |
| Read-only relationship to originals | Review cannot accidentally mutate source files | Strong trust and safety property |
| Local-first deployment | No mandatory third-party upload | Privacy and low operational dependency |
| Agent-friendly CLI | Automation can register outputs directly | Core differentiation from generic photo galleries |

## The closed-loop opportunity

Today Asset Viewer solves **agent → human** handoff well enough: an agent creates files, registers a folder, and tells the human where to look.

The larger opportunity is **agent → human → agent**:

1. Agent creates variants.
2. Human reviews in Asset Viewer.
3. Human records decisions/comments.
4. Agent queries those decisions in a stable machine-readable way.
5. Agent continues only from approved or requested changes.

That loop is more important than adding decorative gallery features. It makes Asset Viewer an interface between human judgment and automated production.

## Necessary features

### Machine-readable review API and CLI

Implemented substantially: `reviews`, `pending`, `events`, `wait-for-review`, manifest export, and documented HTTP state/event endpoints form the agent-facing review contract.

**Why necessary:** without this, agents can create review work but cannot reliably consume the resulting decisions.

### Stable asset identity

Implemented in v0.4: each cataloged asset has a stable UUID. Same-filesystem renames preserve review state/history; content replacement invalidates stale approval and re-enters review.

**Why necessary:** review decisions must survive ordinary workflow changes.

### Indexed catalog and filesystem watcher

The durable SQLite catalog and cached gallery reads are implemented in v0.4, including additions, replacements, deletions/tombstones, and unambiguous same-filesystem renames. A filesystem watcher remains future work; explicit/TTL reconciliation is the correctness fallback.

**Why necessary:** scale and responsiveness. A filesystem viewer should remain fast as collections grow without making filesystem events the sole source of truth.

### SQLite review/catalog state

Implemented: transactional SQLite now stores review state, history, completion state, stable IDs, and catalog metadata.

**Why necessary:** transactional writes, concurrency safety, indexing, future comments/audit history, and simpler backups.

### Compare mode

Implemented substantially: 2–4 assets can be reviewed side-by-side, and two assets can use overlay or difference modes. Linked zoom/pan remains the important next comparison primitive.

**Why necessary:** many generated-image decisions are relative ("A versus B"), not isolated yes/no decisions.

### Batch review

Implemented: multi-select plus bulk approve/reject/maybe/clear.

**Why necessary:** large AI-generated batches make one-at-a-time classification unnecessarily expensive.

### Search, sort, and folder-aware navigation

Implemented substantially: filename/path/comment search plus status filtering and time/name/status/size/resolution sorting. Richer folder navigation remains open.

**Why necessary:** collections become unusable once they exceed a few hundred assets.

### Notes/comments

Implemented: a review note is stored with the stable asset record and exposed to agents. Precise pinned annotations remain future work.

**Why necessary:** `maybe` and `reject` often need a reason that an agent can act on.

### Review sessions / manifests

Create a named review session or export a manifest of assets and decisions.

**Why necessary:** makes a review reproducible and gives agents/build pipelines a precise completion artifact.

### Bounded background thumbnail workers

Move image decoding out of HTTP request threads and cap concurrency/resource use.

**Why necessary:** reliability and security on large/untrusted batches.

### Production-grade serving and optional authentication

Provide a hardened server mode and a simple authenticated/private deployment story.

**Why necessary:** the product is naturally useful on remote build servers; relying only on localhost limits adoption.

## High-value but not immediately necessary

| Feature | Benefit | Why later |
|---|---|---|
| Webhooks on review changes | Lets agents/pipelines react immediately | Polling/API is sufficient first |
| Multi-user identity | Shows who approved what | Only needed once collaboration expands |
| Review audit log | Compliance/accountability | Build after stable identity/state model |
| Shareable review links | External client review | Requires deliberate auth/permission model |
| Annotation/drawing tools | Precise visual feedback | Useful but materially increases UI complexity |
| Duplicate/content similarity detection | Helps prune variant floods | Nice optimization after core review loop |
| Optional AI semantic search | Natural-language asset discovery | Risks distracting from the core local-review product |
| Format plugins (RAW/PSD/PDF/video) | Broadens creative use cases | Add through plugins rather than bloating the core |
| MCP/agent connector | Deep agent-native integration | Valuable once the HTTP/CLI review contract stabilizes |

## Features to deliberately avoid in the core

Asset Viewer should resist becoming:

- a primary asset store;
- a cloud sync engine;
- an image-generation product;
- a Photoshop replacement;
- a full enterprise DAM taxonomy system;
- an automatic file mover that silently changes project state.

Those features weaken the strongest architectural advantage: **the filesystem/project remains authoritative, while Asset Viewer is a reversible review layer.**

## Product benefits by category

### Workflow efficiency

- One stable review location instead of ad hoc transfer steps.
- Lower chat/browser memory pressure because batches are represented by thumbnails.
- Faster iteration through keyboard, batch, and compare workflows.

### Data integrity

- Originals stay in the owning project.
- Review metadata is separate from asset bytes.
- No accidental divergence caused by review-only copies.

### Agent interoperability

- Any agent capable of writing files and running a CLI can use the viewer.
- No dependency on a specific model vendor or image generator.
- The manifest, pending-state, event, and completion APIs close the human-feedback loop in a model-neutral way.

### Privacy and control

- No mandatory cloud upload.
- Can remain on private infrastructure.
- Users choose the remote-access boundary.

### Operational simplicity

- Small dependency footprint.
- SQLite is embedded and zero-admin; no external database service is required.
- One viewer can span many project outputs.

## Competitive audit

The current product was compared against Frame.io, Canto, Pixieset, Air, Immich, and Photofield. The result reinforces the product direction: gallery/favorite features are commodity; the differentiator is durable filesystem-native review state that automation can consume. See [FEATURE_AUDIT_2026-09-13.md](FEATURE_AUDIT_2026-09-13.md).

## Strategic positioning

The most useful one-line positioning is:

> **Asset Viewer is the review layer between tools that create image files and humans who decide what happens next.**

That makes it complementary to agents, render farms, build systems, repositories, cloud drives, and DAMs rather than a replacement for all of them.
