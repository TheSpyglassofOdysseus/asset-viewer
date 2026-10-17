"""Optional, read-only character roster navigation for registered image collections.

Collection paths and review state remain owned by Asset Viewer. The roster is a
navigation index only: no migrations, renames, moves, or collection rewrites.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

LOGGER = logging.getLogger(__name__)
CHARACTER_ID = re.compile(r"^CHR-([0-9]{3})$")
COLLECTION_ID = re.compile(r"(?:^|[^a-z0-9])chr[-_ ]?([0-9]{3})(?:[^0-9]|$)", re.I)
ALNUM = re.compile(r"[^a-z0-9]+")


def _tokens(value: str) -> list[str]:
    return [part for part in ALNUM.split(value.lower()) if part]


def _belongs_to_character(row: dict, character: dict, distinct_tokens: dict[str, str]) -> bool:
    slug = str(row.get("slug") or "")
    label = str(row.get("label") or "")
    haystack = _tokens(slug + " " + label)
    id_match = COLLECTION_ID.search(slug) or COLLECTION_ID.search(label)
    if id_match:
        return character["id"] == f"CHR-{id_match.group(1)}"

    name_tokens = _tokens(character["name"])
    # Prefer an exact phrase; it avoids scattering similarly named characters.
    if name_tokens and " ".join(name_tokens) in " ".join(haystack):
        return True
    # Permit a unique, substantial family/name token for legacy pre-roster work.
    return any(
        len(token) >= 5 and distinct_tokens.get(token) == character["id"]
        for token in name_tokens if token in haystack
    )


def _assign_collections(characters: list[dict], rows: list[dict]) -> None:
    # Repeated/common words do not create accidental matches.
    owners: dict[str, set[str]] = {}
    for character in characters:
        for token in set(_tokens(character["name"])):
            if len(token) >= 5:
                owners.setdefault(token, set()).add(character["id"])
    distinct = {token: next(iter(ids)) for token, ids in owners.items() if len(ids) == 1}

    for row in rows:
        matches = [c for c in characters if _belongs_to_character(row, c, distinct)]
        # Leave ambiguous or unclassified collections visible in "Other".
        if len(matches) == 1:
            matches[0]["collections"].append(row["slug"])


def public_character_roster(rows: list[dict]) -> list[dict]:
    """Return public id/name/faction and matching collection slugs, if configured.

    Input is the optional ASSET_VIEWER_CHARACTER_ROSTER_PATH setting chosen
    by the operator; this never exposes local filesystem paths, briefs or
    private production metadata to the browser.
    """
    configured = os.environ.get("ASSET_VIEWER_CHARACTER_ROSTER_PATH", "")
    if not configured:
        return []
    try:
        path = Path(configured)
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("roster file missing or too large")
        document = json.loads(path.read_text(encoding="utf-8"))
        raw = document.get("characters", []) if isinstance(document, dict) else document
        if not isinstance(raw, list):
            raise ValueError("characters must be an array")

        characters: list[dict] = []
        used: set[str] = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            char_id = item.get("id")
            name = item.get("name")
            if not isinstance(char_id, str) or not CHARACTER_ID.fullmatch(char_id):
                continue
            if char_id in used or not isinstance(name, str) or not name.strip():
                continue
            used.add(char_id)
            characters.append({
                "id": char_id,
                "name": name.strip()[:120],
                "faction": str(item.get("faction") or "")[:100],
                "collections": [],
            })
            if len(characters) >= 1000:
                break

        _assign_collections(characters, rows)
        return characters
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        LOGGER.warning("optional character roster navigation disabled: %s", exc)
        return []
