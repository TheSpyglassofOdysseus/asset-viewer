# Asset Viewer Visual Redesign v1

Status: Draft for implementation and adversarial review
Baseline: `main` at `11d3fd7839dea62bbda39e63936b440a026f2f68` (v0.9.1)

## Problem

Asset Viewer has a strong review engine but the primary UI still presents like a dense internal utility. The public concept work established a clearer product language: image-first creative workspace, persistent project context, obvious workflow state, and first-class compare/handoff surfaces.

The redesign must converge the real app toward that product language without pretending unsupported capabilities exist.

## Product principle

**Make the real workflow look intentional, not make the product look bigger than it is.**

Every control shown must map to a working current capability. No fake Trash, storage quota, team presence, cloud upload, comments/reactions, billing, or hosted-DAM behavior will be added for visual similarity.

## Goals

1. Make a new user understand collection → review → compare → approve/handoff within seconds.
2. Put the assets, not controls, at the visual center of the application.
3. Preserve Asset Viewer's local-first, non-destructive, high-density character.
4. Make real screenshots strong enough to replace aspirational mockups on the public repo.
5. Keep keyboard review, saved views, command palette, provenance, annotations, Activity, families, and handoff behavior intact.
## Visual direction

The main workspace becomes a light, quiet studio shell inspired by the Northline concepts. Focused image inspection and pixel comparison may remain dark where contrast benefits the work.

### Workspace shell

- Persistent left rail on desktop with Asset Viewer identity and real registered collections.
- Grouped collections use existing collection `group` metadata; no invented folder taxonomy.
- Active collection receives a strong but restrained selected treatment.
- Mobile/tablet collapse the rail into the existing collection selector rather than forcing a permanent sidebar.

### Collection header

- Show the active collection label as the page title.
- Show concise review progress directly under/alongside the title.
- Expose three truthful workflow tabs: **Gallery**, **Activity**, **Approved**.
- Approved is a filtered gallery view, not a separate source of truth.
- Search, status filter, sort, saved views/actions remain available but visually secondary.

### Gallery cards

- Desktop target: three large columns at wide widths, two at medium widths, two/one on small screens.
- Use large edge-to-edge image previews with neutral image surfaces.
- Decision badges sit on the image and read Approved / Maybe / Rejected / Needs review.
- Selection becomes a small checkbox affordance, not a large overlay control.
- Filename is primary card text; redundant path is hidden when equal to the filename.
- Technical metadata uses quiet chips: type, resolution, size where available.
- Family, preferred, new, note, and annotation state remain visible but do not compete with the image.
### Compare

- Treat compare as a deliberate review workspace rather than a utility overlay.
- Preserve side-by-side, overlay, difference, linked zoom, pan, and reset behavior.
- Give each variant a clear identity block with decision state and review note.
- Preferred-family state must be visually obvious without inventing a new approval semantic.
- Keep full image area large; controls must not steal comparison space.

### Activity

- Replace the plain event ledger presentation with a readable timeline using the existing canonical event stream.
- Grouping by day/time is optional in v1; event type hierarchy is required.
- Do not invent actors when actor identity is absent. Machine/system events must remain visibly machine/system events.

### Approved / handoff

- Approved tab filters the canonical collection to approved assets.
- A collection-level approved summary may expose the existing handoff/report actions.
- Do not imply files were copied, exported, published, or delivered until the user explicitly runs the current handoff/copy workflow.

## Interaction contract

- Existing stable collection and asset URLs remain valid.
- `A/M/R` keyboard review shortcuts remain valid.
- Command palette remains available.
- Saved views remain functional and distinguishable from the Gallery/Activity/Approved tabs.
- Bulk selection and bulk decision semantics do not change.
- Review/autosave, annotations, variant families, provenance, Activity, reports, and handoff continue to use existing APIs and canonical state.
## Acceptance criteria

### Visual

1. At 1440 px, the Northline demo shows three large gallery cards across the primary content area; card imagery is materially larger than v0.9.1.
2. The active collection name and review progress are readable without parsing a compact toolbar.
3. Gallery / Activity / Approved are visible as first-class navigation states.
4. Approved, Maybe, Rejected, and unreviewed states are distinguishable by text, shape, and color; color is not the only signal.
5. The compare view gives at least 70% of its viewport height to image comparison on a 1440×1000 viewport.
6. The desktop shell has no horizontal overflow at 1280 and 1440 px.
7. Mobile at 390×844 remains usable with no permanent sidebar and no horizontal overflow.

### Behavioral

1. The existing browser smoke passes against a built wheel.
2. Unit suite, compileall, JS syntax, Bandit, dependency audit, and diff check pass.
3. Gallery filters and saved views still operate on canonical collection data.
4. Approved tab is implemented as canonical status filtering and never duplicates review state.
5. Switching collections updates title, progress, rail state, URL, cards, Activity, and Approved consistently.
6. Selection, compare, review mutation, comments/autosave, annotations, families, and handoff remain regression-covered.
7. No current API route is removed or semantically changed by the visual redesign.

## Explicit non-goals

- Hosted asset storage or upload management
- Trash/archive lifecycle
- User/team collaboration or presence
- Cloud quotas/storage meters
- New comment/reaction model
- Publishing to social/web channels
- New approval authority or automatic promotion
- Replacing the local-first collection model with a DAM hierarchy

## Delivery slices

1. Shell + collection rail + collection header/tabs.
2. Gallery card hierarchy + responsive density.
3. Approved filtered workspace + existing handoff/report affordance.
4. Compare visual refinement.
5. Activity visual refinement.
6. Real screenshots captured from the implemented app; README refreshed only after exact-head verification.