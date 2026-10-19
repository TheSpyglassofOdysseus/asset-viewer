# MDF Asset Viewer — Project-first front door

This is a **metadata and navigation layer** over the existing Asset Viewer 0.10 review engine. It changes no review decisions, databases, source assets, file paths, owner approvals or licensing gates.

## Design contract
- `/asset-viewer/` (bare root, no query) opens the new project dashboard via a **small patch to MDF's existing private JS override**.
- `/asset-viewer/c/<slug>`, `/asset-viewer/?collection=...`, `/asset-viewer/characters/`, `/asset-viewer/characters/CHR-###/`, and all direct demo routes remain functional and keep their existing data and review behavior.
- Original galleries' 110-item navigation becomes a **collapsed** All source collections section with a Project home link; mobile's existing collection selector remains.
- `projects.json` is an explicit *curated pointer list*. Its links are neither automatically newest by timestamp nor implicit release approval. Update it as part of a reviewed project handoff.
- `/api/pending` is read-only and supplies live unreviewed/new counts. `/api/gallery` supplies all original collection links.
- All files live within pre-existing Basic Auth-protected nginx static alias `/asset-viewer/characters/`; do not publish under `/3d/` or remove password protection.
- No filesystem archival or deletion in this initial navigation milestone.

## Implementation, validation, deployment
- Source: `deploy/mdf-project-home/{index.html,project-home.css,project-home.js,projects.json}`.
- Smoke fixture: `browser-smoke.cjs` uses the existing Oracle ARM local Flask/Gallery backend plus a loopback-only proxy that reproduces critical nginx URL rewriting. It does **not** bypass real nginx Basic Auth.
- Before deployment, run `node --check project-home.js`, `python3 -m json.tool projects.json`, generate `gallery-patched-preview.js` using `python3 patch_gallery.py --source /home/ubuntu/mdf-asset-viewer-private/asset-viewer-app.js --output gallery-patched-preview.js`, then `node browser-smoke.cjs`. After deployment the fixture falls back to the deployed JS when no preview copy is present.
- On the Oracle ARM, run `python3 deploy.py --apply` as ubuntu. It **refuses overwrites** and checks patch anchors before writing the private app override. The old JS is backed up under `services/asset-viewer-live/backups/project-home-<UTC timestamp>/asset-viewer-app.js`.
- Rollback: copy that backed-up JS over `/home/ubuntu/mdf-asset-viewer-private/asset-viewer-app.js` (preserve 0644) to restore the old root gallery behavior. The new static project directory can remain harmlessly; no existing path needs deletion.
- After deployment, verify original gallery direct links, project home, mobile layout, and unauthenticated HTTP 401s for new paths and old review engine. Do not claim authenticated browser QA without credentials.

## Follow-on work in #47
The larger audit still calls for server-side collection tagging and a durable `current_best` model with human review; this phase deliberately only pins six high-level destinations. Fix stale references inside older experiment pages, reconcile 90 roster IDs without mapped source collections against Drive/source, and separate archive status after approval.
