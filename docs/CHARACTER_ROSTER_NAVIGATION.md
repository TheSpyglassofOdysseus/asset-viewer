# Character roster navigation (optional)

The character roster view groups existing Asset Viewer collections under canonical
character identities. It is **presentation-only**. It does not copy, move,
delete, rename, rescan, or change review status for any image or collection.

## Enable the roster hierarchy

Point the Asset Viewer service at a roster JSON file:

```sh
export ASSET_VIEWER_CHARACTER_ROSTER_PATH=/absolute/path/to/roster.json
asset-viewer serve
```

Alternatively, without changing a systemd unit, place a **symlink** named
`character-roster.json` in the instance's existing `ASSET_VIEWER_HOME`
directory, pointing to the canonical project roster. If the explicit environment
variable is set, it takes precedence. A missing symlink and missing environment
variable leave the original flat navigation enabled.

The JSON may be a list of records or an object with a `characters` array.
Each record should have an immutable ID (for example `CHR-003`), a display
`name`, and optionally `faction`.

For the AI-Native 3D Studio, configure this environment variable to point at
the **canonical production roster**, not a copy maintained within Asset Viewer.
Do not commit any host-specific private file paths to this repository.

With a valid roster, the desktop navigation shows **one collapsible row per
character** (including those with no images), an optional search box, and nested
revisions ordered newest-first. It automatically expands the current character.
Unmatched collections remain in the collapsed **Other collections** section.
Mobile uses the existing native collection selector with character optgroups.

Registered collections are matched first by canonical `CHR-###` identifiers
in their slugs/labels, then by unique name identifiers for legacy collections.
Ambiguous/unmatched collections stay in **Other collections** rather than
silently being assigned to the wrong person.

When the variable is unset or the roster file cannot be read, the existing
flat/grouped Asset Viewer navigation is used without any new behavior.

## Technical contract

- Source of truth: external roster JSON for names; Asset Viewer collection
  registry for existing collection IDs and review state.
- API: `GET /api/gallery` optionally includes `roster` with
  `{id, name, faction, collections: [slug]}` records. It exposes no filesystem
  paths or private character descriptions.
- Each revision button uses the existing collection-slug navigation. Existing
  `/c/<slug>` links, gallery routes, review history and approvals still work.
- A roster row with no published images says `No artwork registered yet`,
  never `approved`.
- No model-output inference or automatic owner approval is part of navigation.
- Grouping in Asset Viewer is not itself a completed production-package check.

## Tests and deployment

```sh
node --check asset_viewer/static/app.js
python -m unittest tests.test_character_roster tests.test_http
python -m unittest discover
python -m compileall -q asset_viewer tests
```

Deploy through the existing operator review process after staging validation.
Do **not** restart the live service, rewrite production collections, or set up
unapproved public sharing as part of a navigation-only change.
