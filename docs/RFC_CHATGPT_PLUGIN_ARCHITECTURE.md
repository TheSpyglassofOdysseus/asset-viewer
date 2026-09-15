# RFC: Asset Viewer as a ChatGPT-native visual review memory

- **Status:** Proposed
- **Date:** 2026-09-14
- **Branch:** `design/chatgpt-plugin-architecture`
- **Scope:** Product/architecture design only
- **Implementation authority:** None. This RFC does not authorize production changes, public hosting, billing work, or a plugin submission.

## Summary

Asset Viewer already solves a useful local-first problem: projects own image files, agents and tools create them, humans review them in one stable surface, and structured review state flows back to automation.

This RFC explores a narrower extension: make that review memory available directly inside ChatGPT through an app/plugin experience, without turning Asset Viewer into another generic visual-regression SaaS or requiring every user to operate a web server.

The proposed product hypothesis is:

> **Asset Viewer is persistent human/AI visual decision memory: what we tried, what changed, what the human said, what was accepted, and what an agent should know before changing it again.**

The immediate recommendation is **not** to build a hosted SaaS. The next step, if this RFC is accepted, is a small dogfood prototype that reuses Asset Viewer's existing MCP contract and our existing hosted/private Asset Viewer deployment. That prototype should prove that a conversation-native visual-review workflow is materially better than opening the existing web UI or using established visual-testing products.

Only after that proof should we decide whether a general hosted service is justified.

---

## 1. Why this RFC exists

AI-assisted development makes it cheap to generate UI changes and expensive to remember why one visual direction was accepted over another.

During normal development, visual intent tends to leak into transient places:

- chat messages;
- screenshots pasted into conversations;
- pull-request comments;
- temporary browser tabs;
- local folders;
- design mockups;
- one-off before/after comparisons;
- a developer's memory.

That creates a failure mode that conventional code review does not solve: the code can remain technically correct while the interface gradually becomes visually inconsistent, fuzzy, cluttered, or simply different from what a human previously approved.

Asset Viewer already provides most of the durable substrate needed to address that problem: stable asset IDs, review state, annotations, families/variants, comparisons, provenance, events, approved handoff manifests, deep links, and an MCP adapter.

The open question is whether exposing that substrate *inside the development conversation* creates a distinct product rather than duplicating existing visual testing systems.

---

## 2. Current Asset Viewer contract

The current product deliberately defines itself as the **review plane, not the storage plane**.

Important existing properties to preserve:

1. Project folders remain the source of truth for originals.
2. Asset Viewer stores review/catalog metadata separately from source assets.
3. Cached thumbnails and bounded previews are disposable derivatives.
4. Review state is durable and machine-readable.
5. The browser does not need to decode every full-resolution image in a collection.
6. The same review protocol is already exposed through CLI, JSON API, ordered events, and MCP.
7. The product is local-first and can be deployed privately.

The current MCP adapter already exposes tools for:

- listing collections;
- reading reviews;
- reading pending/completion state;
- reading ordered events;
- reading variant families;
- reading annotations;
- resolving collection/asset URLs;
- reading activity;
- reading/writing provenance;
- exporting the approved handoff;
- refreshing collections.

This is a major architectural advantage. A ChatGPT app should initially be an **adapter over the existing contract**, not a second review system.

---

## 3. Competitive landscape

The market validates the underlying problem, but it also establishes a hard boundary for what Asset Viewer should not rebuild.

### 3.1 Vizzly

Vizzly is explicitly positioned as visual testing for coding agents. It keeps approved baselines, diffs, comments, and review decisions, then exposes compact review context back to agents.

Sources:

- https://vizzly.dev/
- https://vizzly.dev/agent-context/
- https://docs.vizzly.dev/

**What it proves:** agents benefit from prior human visual decisions and approved baselines.

**What we should not copy:** generic screenshot-test hosting, build-centric visual regression, baseline management tied primarily to CI runs.

### 3.2 Argos

Argos provides baseline/change review, overlays, synced zoom, pixel-pinned comments, approvals/rejections, GitHub checks, and agent-readable/agent-actionable review workflows through CLI/API/MCP-related tooling.

Sources:

- https://argos-ci.com/visual-testing
- https://argos-ci.com/review
- https://argos-ci.com/blog/playwright-mcp-visual-testing

**What it proves:** humans and agents can participate in the same visual review lifecycle.

**What we should not copy:** another PR-centric visual testing service whose primary unit is a test build.

### 3.3 Percy / BrowserStack

Percy's Visual Review Agent adds AI-assisted triage, noise reduction, bug classification, natural-language summaries, and change grouping on top of conventional visual testing.

Sources:

- https://www.browserstack.com/docs/percy/ai-agents/visual-review-agent/overview
- https://www.browserstack.com/docs/app-percy/review-agent/ai-visual-changes

**What it proves:** AI-assisted visual review is now a mainstream direction rather than a novelty.

**What we should not copy:** broad cross-browser regression infrastructure, hosted browser matrices, or enterprise testing breadth.

### 3.4 OpenAI Product Design plugin

The Product Design plugin can turn briefs, research, screenshots, and URLs into concepts, critiques, prototypes, and design handoff artifacts directly inside ChatGPT.

Sources:

- https://openai.com/business/plugins/product-design/
- https://chatgpt.com/plugins/product-design

**What it proves:** design work itself can be conversation-native.

**What appears different:** Product Design is oriented toward ideation, design QA, and prototype creation. Asset Viewer's opportunity is persistent project-specific visual review history and accepted decisions that survive across agent runs and development cycles.

### 3.5 OpenAI platform fit

OpenAI's Apps SDK is built on MCP and supports custom UI plus backend logic inside ChatGPT. Plugin listings can package apps and skills for discovery.

Sources:

- https://help.openai.com/en/articles/12515353-build-with-the-apps-sdk
- https://help.openai.com/en/articles/11487775
- https://help.openai.com/en/articles/20001256/

Asset Viewer therefore already has one important prerequisite: an MCP-shaped domain boundary.

---

## 4. Product wedge

The product should not be described as "visual regression testing in ChatGPT."

A sharper distinction is:

### Established visual-testing tools answer

> Did the UI change relative to an approved test baseline, and should that change pass CI?

### Asset Viewer should answer

> What visual directions have we tried, what did the human notice, what did we accept or reject, and what should the agent know before it changes this surface again?

That includes material that may never belong in a screenshot test suite:

- exploratory mockups;
- alternate layouts;
- generated concepts;
- responsive variants;
- annotated production captures;
- before/after polish passes;
- screenshots from FDI or another live product;
- intentionally rejected directions;
- accepted visual baselines;
- visual review notes tied to a specific commit/run.

The differentiator is therefore **decision memory**, not merely image diffing.

### Proposed one-line position

> **Visual QA memory for AI software development.**

Alternative, more precise internal language:

> **Persistent human/AI visual decision memory.**

The first phrase is easier to explain; the second is the stronger architecture/product boundary.

---

## 5. Non-goals

A v1 plugin/app effort must explicitly avoid the following:

- rebuilding Vizzly, Argos, Percy, Chromatic, or Applitools;
- becoming a general CI screenshot-testing platform;
- building a cloud browser farm;
- becoming a DAM or canonical asset store;
- replacing GitHub or pull-request review;
- billing/subscription infrastructure;
- enterprise SSO/RBAC before product fit;
- collaborative design editing;
- Figma replacement;
- image generation as a core capability;
- large-scale public multi-tenant hosting before a conversation-native workflow is proven;
- automatically approving visual changes without human authority.

If the product cannot create value without one of these, the wedge is probably not strong enough.

---

## 6. User experience hypothesis

The target interaction should feel like a normal development conversation rather than a separate visual-testing ceremony.

Example:

1. Agent changes FDI's quote editor.
2. Agent captures representative desktop and mobile renders using the project's normal tooling.
3. Captures become Asset Viewer assets with commit/run provenance.
4. ChatGPT asks Asset Viewer for the relevant accepted visual reference and recent review history.
5. ChatGPT presents the current vs accepted view in an inline review surface.
6. Human annotates or says what is wrong: e.g. "the right rail is too busy" or "text looks fuzzy at 100%."
7. Asset Viewer records the decision/annotation against the exact visual evidence.
8. Agent reads that evidence on the next implementation turn.
9. If accepted, the chosen visual becomes the new project reference/baseline according to explicit human action.

The important feature is not that ChatGPT can *see a screenshot*. It already can.

The important feature is that the screenshot is part of a durable project history that the next agent can retrieve without asking the human to reconstruct prior decisions.

---

## 7. Architecture options

There is a tension between two desirable properties:

- "no hosting required" for ordinary users;
- "Asset Viewer is not the storage plane."

That tension should be handled explicitly rather than hidden inside implementation.

### Option A — Local/private Asset Viewer + ChatGPT app

```text
Project assets
    ↓
Local/private Asset Viewer
    ↓ MCP/API
ChatGPT app/plugin
```

**Advantages**

- preserves current architecture;
- minimal new backend work;
- best privacy posture;
- easiest dogfood path;
- no new canonical storage system.

**Limitations**

- ChatGPT cannot assume it can reach every user's localhost/private network;
- setup can require a trusted bridge, remote MCP endpoint, or organization-specific network path;
- not a consumer-friendly installation story.

**Recommendation:** use this for the first prototype because we already control the environment. Do not confuse a prototype constraint with the final distribution model.

### Option B — Hosted review control plane + external asset sources

```text
Project-owned storage (GitHub / object store / Drive / app)
        ↓ authorized reads
Hosted Asset Viewer review plane
        ↓ MCP/App backend
ChatGPT app/plugin
```

The hosted service owns:

- project/review metadata;
- stable review identifiers;
- annotations;
- decisions;
- provenance;
- event history;
- bounded/generated derivatives needed for review.

The user's existing systems continue to own canonical originals.

**Advantages**

- no user-operated web server;
- preserves the source-of-truth boundary better than an upload-first SaaS;
- potentially works well with provider connectors.

**Limitations**

- substantially more auth/security work;
- every asset source has different access semantics;
- reliable preview generation may still require fetching/caching asset bytes;
- multi-tenant privacy requirements become real immediately.

**Recommendation:** plausible long-term architecture, not v1 implementation.

### Option C — Hosted upload workspace

```text
Agent/user uploads screenshots
        ↓
Hosted Asset Viewer stores them
        ↓
ChatGPT app/plugin
```

**Advantages**

- simplest onboarding;
- easiest mental model;
- no dependency on external asset providers.

**Limitations**

- turns Asset Viewer into a storage service;
- creates retention, cost, privacy, abuse, and deletion requirements;
- duplicates competitors' cloud screenshot storage model;
- conflicts with the current north-star contract.

**Recommendation:** reject as the default architecture.

A narrowly bounded **ephemeral review artifact** mode may be reconsidered later if artifacts have explicit TTLs and are never presented as canonical originals.

---

## 8. Recommended architecture

For product discovery, preserve the current core and add adapters around it:

```text
                 ChatGPT
                    │
        ┌───────────▼───────────┐
        │ Asset Viewer App UI   │
        │ focused current task  │
        └───────────┬───────────┘
                    │ Apps SDK / MCP
        ┌───────────▼───────────┐
        │ Asset Viewer contract │
        │ reviews / events /    │
        │ annotations / URLs /  │
        │ provenance / families │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │ Existing Asset Viewer │
        │ catalog + SQLite +    │
        │ bounded preview cache │
        └───────────┬───────────┘
                    │
        ┌───────────▼───────────┐
        │ Project-owned assets  │
        └───────────────────────┘
```

### Architectural rule

**The ChatGPT app must not create a second review state.**

Every decision visible in ChatGPT must resolve to the same durable Asset Viewer review model used by the web UI, CLI, API, and MCP adapter.

### Architectural rule

**The app should render only the evidence needed for the current decision.**

It should not attempt to reproduce the entire Asset Viewer dashboard inside a chat iframe/widget.

The full web UI remains the power-user workspace for browsing large collections and history.

---

## 9. MCP/app capability design

The existing MCP adapter is mostly read-oriented. A conversation-native review loop will eventually need a carefully scoped write surface.

### Existing capabilities to reuse

- `list_collections`
- `get_reviews`
- `get_pending`
- `get_events`
- `get_families`
- `get_annotations`
- `get_collection_url`
- `get_asset_url`
- `get_activity`
- `get_provenance`
- `set_provenance`
- `get_approved_handoff`
- `refresh_collections`

### Candidate future capabilities

Names are conceptual until the core API contract is reviewed.

- `set_review(asset, status, comment)`
- `create_annotation(asset, region_or_point, comment)`
- `resolve_annotation(annotation_id)`
- `create_family(name, assets)`
- `set_preferred_family_member(family, asset)`
- `mark_collection_complete(collection)`
- `reopen_collection(collection)`
- `compare_assets(asset_ids, mode)` or a resource that provides comparison descriptors
- `get_visual_context(collection, surface_or_provenance_filter)`

### Authority rule

Write tools that change approval/rejection/completion state should require explicit human intent or clear tool-action confirmation. The model may recommend; it should not silently promote a new baseline.

---

## 10. Inline UI scope

The first ChatGPT UI should be intentionally small.

### v0 component

A **Visual Decision Panel** showing:

- current candidate;
- accepted/reference asset if one exists;
- side-by-side or overlay toggle;
- concise provenance (project, commit/run, viewport/device when known);
- prior decision/comment summary;
- unresolved annotations;
- Approve / Maybe / Reject actions;
- "Open full Asset Viewer" deep link.

It should not initially include:

- collection administration;
- giant thumbnail grids;
- advanced filtering;
- account management;
- arbitrary file browsing;
- every existing Asset Viewer feature.

The app is a contextual decision surface; the website remains the comprehensive browser.

---

## 11. Performance and memory contract

Browser memory is a first-class product requirement.

### Requirement P1 — project-size independence

Client memory use must scale primarily with the **currently visible review evidence**, not total project size.

A collection with 10,000 assets must not cause 10,000 decoded images, image elements, or large metadata objects to enter the active client working set.

### Requirement P2 — derivative-first rendering

Use bounded review derivatives by default. Full-resolution originals load only by explicit action when precision inspection requires them.

### Requirement P3 — small active image set

For normal comparison, keep only the current candidate/reference/diff plus a very small prefetch window decoded.

### Requirement P4 — virtualization

Any list/grid exceeding a modest visible count must be virtualized or paginated. Off-screen images must be eligible for release.

### Requirement P5 — server-side heavy work

Where practical, thumbnail generation, expensive image decoding, and deterministic diff generation should occur outside the user's browser.

### Requirement P6 — measurable budgets

Before a public hosted mode, define automated acceptance budgets for:

- initial JS/UI payload;
- idle memory after opening the app;
- memory while comparing two 4K images through bounded derivatives;
- maximum concurrently decoded images;
- time-to-first-reviewable-content;
- cleanup after leaving a comparison.

The project already implements bounded previews and lazy loading. The plugin/app must preserve those properties rather than regress them.

---

## 12. Security and privacy constraints

A public plugin changes the threat model even if the core application remains local-first.

Before any multi-tenant hosted service, require a separate security design covering:

- authentication and account linking;
- project authorization boundaries;
- asset-source authorization;
- tenant isolation;
- signed/expiring asset access;
- preview cache retention;
- deletion semantics;
- audit events;
- CSRF/origin/session model for web surfaces;
- prompt/tool injection boundaries when asset metadata or comments are returned to models;
- secrets/tokens never entering review comments or provenance accidentally;
- private repository and screenshot handling;
- sensitive information visible inside screenshots;
- abuse/storage quotas if any artifact upload exists.

No public hosted prototype should be deployed merely because the local app is already hardened for trusted/private use.

---

## 13. Dogfood plan

FDI is the right first external dogfood project because it has active UI development, desktop/mobile concerns, and recurring visual-polish decisions.

### Phase 0 — RFC only

- Accept/reject this product boundary.
- Decide whether "visual decision memory" is the wedge.
- No code.

### Phase 1 — private conversation prototype

Goal: prove usefulness, not distribution.

- Reuse the existing Asset Viewer deployment.
- Reuse the current MCP domain model.
- Expose a small ChatGPT app UI against a deliberately tiny subset of capabilities.
- Use FDI captures with explicit provenance.
- Keep human approval authoritative.

Questions to answer:

1. Does reviewing inside ChatGPT save meaningful context-switching?
2. Does prior visual history materially improve the next coding turn?
3. Do annotations/accepted decisions get reused, or do they become stale clutter?
4. Is the inline panel better than simply opening Asset Viewer in another tab?
5. Which existing Asset Viewer features are actually needed in-chat?

### Phase 2 — deterministic visual context

If Phase 1 passes:

- define stable mapping from project/surface/viewport/commit to review evidence;
- add an explicit `get_visual_context` style API if the existing read tools are too low-level;
- add minimal write actions with explicit human authority;
- test agent cold-start behavior using only durable review history.

### Phase 3 — deployment decision

Only after dogfood:

Choose one:

- remain a local/self-hosted open-source tool with optional private ChatGPT app integration;
- provide a hosted review control plane that references external asset sources;
- integrate with an existing visual-testing provider instead of hosting competing infrastructure;
- stop the plugin effort if the web UI + MCP already provides most of the value.

### Phase 4 — public product work

Only if Phase 3 selects hosted/public distribution:

- multi-tenant auth/security design;
- provider/source adapters;
- retention/deletion policies;
- observability;
- quotas/cost controls;
- plugin directory submission requirements;
- privacy/terms documentation;
- public support model.

---

## 14. Success criteria

The prototype should not be judged by whether we successfully render an image in ChatGPT. That is too easy and proves almost nothing.

The prototype passes only if it demonstrates at least these outcomes:

1. **History reuse:** a fresh agent turn can retrieve a prior human visual decision without the human restating it.
2. **Decision grounding:** the model can associate feedback with exact assets/variants/provenance rather than vague conversational references.
3. **Lower context switching:** a common review can be completed inside the conversation without opening the full viewer.
4. **No duplicate state:** decisions made in-chat are visible through the existing Asset Viewer review model.
5. **Memory discipline:** client resource use remains bounded as project history grows.
6. **Human authority:** accepted/rejected visual state cannot silently change because an agent inferred intent.
7. **Distinct value:** the workflow is meaningfully different from installing a conventional visual-regression service and reading its PR report.

### Kill criterion

If the main value reduces to "show visual-regression diffs inside ChatGPT," stop and integrate an established visual-testing provider instead of building another one.

---

## 15. Open questions

These should be answered through prototype evidence, not speculation where possible.

1. What is the canonical mapping from a software "surface" (e.g. FDI Quote Editor) to one or more Asset Viewer assets/families?
2. Should accepted visual references be represented as ordinary approved assets, a preferred family member, or a separate baseline/reference concept?
3. How much write authority should MCP expose versus keeping review actions in the UI/API only?
4. Can the ChatGPT app efficiently render Asset Viewer-hosted bounded previews without broadening asset access?
5. For a future hosted mode, can canonical originals remain entirely outside Asset Viewer while still delivering a low-friction onboarding experience?
6. Which external asset providers are worth supporting first, if any?
7. Should deterministic screenshot capture remain outside Asset Viewer (Playwright/project tooling) with Asset Viewer receiving only resulting evidence?
8. Do we need a first-class "visual decision" entity that links multiple candidate assets, a decision, rationale, annotations, provenance, and supersession history?
9. How should stale visual decisions behave after the corresponding UI surface changes substantially?
10. What is the minimum inline UI that is materially better than a deep link to the existing viewer?

---

## 16. Proposed decision

Accept this RFC only as authorization for a **small private prototype**, not a hosted product build.

If accepted, the next implementation issue should be narrow:

> **Prototype one conversation-native Visual Decision Panel using the existing Asset Viewer MCP/review model and an FDI dogfood collection. Do not add multi-tenant hosting or new canonical asset storage.**

That issue should define concrete acceptance checks before any code is written.

---

## 17. Product principle

Asset Viewer should remain useful even if the plugin idea fails.

The plugin is an access surface over a durable review protocol, not the product's new source of truth.

The enduring contract remains:

> **Projects own the files. Agents create the files. Asset Viewer remembers the visual decisions. Humans retain authority over what becomes accepted.**
