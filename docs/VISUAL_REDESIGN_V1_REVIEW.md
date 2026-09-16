# Visual Redesign v1 — Review and Counter-review

Baseline spec: `docs/VISUAL_REDESIGN_V1.md`

## Reviewer pass — product / UX

### R1 — Do not import mockup-only semantics

**Finding:** The concept images use Pending, Needs Review, user avatars, collection counts, folders, Trash, storage quota, and cloud-style Add Assets. Several are not Asset Viewer concepts today.

**Resolution:** Only current canonical states are rendered. `maybe` remains Maybe; empty status may be presented as Needs review in display copy but remains empty/unreviewed in state. No user/team/storage/trash/upload UI is added.

### R2 — Sidebar cannot become a second collection model

**Finding:** A new rail could diverge from the existing collection `<select>` and URL navigation.

**Resolution:** Rail and select are two renderings of `state.collections`; both call the same collection-loading path. Desktop rail is primary; the select remains available for narrow/mobile layouts.

### R3 — Approved cannot duplicate filter state

**Finding:** A new Approved view could create a second review query and disagree with `#filter=approved`.

**Resolution:** Approved tab is a UI shortcut over the existing status filter. It renders the same `state.images` and `applyFilter()` output.

### R4 — Bigger cards can damage high-volume review

**Finding:** Three-column concept density is attractive for six campaign assets but slower for 100-image audit collections.

**Resolution:** Use responsive `minmax()` sizing rather than a hard three-column grid. Target three columns at 1440 with the rail open, four on wider displays when space permits, and preserve keyboard review/bulk actions for high-volume work.
### R5 — Light shell must not reduce inspection quality

**Finding:** Some assets need neutral/dark framing, and transparent media can disappear on white.

**Resolution:** The application chrome becomes light; thumbnail wells and focused review/compare image surfaces remain neutral/dark enough for reliable inspection.

### R6 — Saved views and new workflow tabs can collide

**Finding:** Saved views currently live inside the View selector and may preserve arbitrary filters. A new Gallery/Activity/Approved tab row could silently overwrite them.

**Resolution:** Activating Activity or Approved clears the active saved-view marker. Applying a saved view returns to Gallery. Gallery tab resets only the explicit status shortcut, not search/sort.

### R7 — Accessibility must survive the visual polish

**Finding:** Concept mockups rely heavily on soft color, small chips, and low-contrast metadata.

**Resolution:** Status always includes text; focus-visible states remain; contrast is tested; checkboxes retain native semantics; keyboard review and command palette stay intact.

## Counter-review — adversarial engineering

### C1 — Reject a backend redesign disguised as visual work

The redesign should not require new persistence tables, new review states, migration work, or collection-count aggregation APIs. If implementation starts requiring those, split them into another release.

### C2 — Reject duplicated navigation state

There must be one source for active collection, one source for canonical asset/review data, and one filter pipeline. Sidebar, select, tabs, and saved views may only project that state.

### C3 — Reject screenshot-driven special cases

Northline is the visual test fixture, not a privileged runtime path. CSS and rendering must remain useful for mixed aspect ratios, 100+ assets, missing provenance, unavailable collections, long filenames, and no approved assets.

### C4 — Reject desktop-only beauty

At 390×844 the left rail must collapse, core filters must remain reachable, cards must remain tappable, and modals must not overflow horizontally.
### C5 — Reject hidden regression from moving controls

Collection actions, saved views, bulk actions, report/handoff, annotations, family actions, provenance, and compare modes must remain discoverable even if they move visually. Do not delete a control merely because it is absent from the concept art.

### C6 — Reject status vocabulary drift

Display copy may say “Needs review” for the empty/unreviewed state, but API values remain unchanged. `maybe` must never be relabeled Pending because Maybe is a deliberate human decision, not merely incomplete work.

### C7 — Reject visual success without machine proof

The redesign is not done because screenshots look good. Exact-head proof must include the built-wheel browser smoke plus rendered screenshots at desktop and mobile. A visual regression guard must assert no horizontal overflow and that core controls remain visible.

## Approved implementation boundary

Proceed with a frontend-only v1 unless an existing test exposes a genuine backend defect. The expected implementation surface is:

- `asset_viewer/static/index.html`
- `asset_viewer/static/app.css`
- `asset_viewer/static/app.js`
- browser/UI regression tests
- README screenshots/copy only after implementation proof

No schema, storage, watcher, webhook, MCP, handoff-integrity, or review-state semantics should change in this PR.

## Reviewer verdict

**Proceed**, provided the implementation stays inside the boundary above and treats the concept images as design references rather than a requirements waiver.
