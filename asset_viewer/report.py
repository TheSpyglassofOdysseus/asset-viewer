from __future__ import annotations

import base64
import html
from collections import defaultdict
from typing import Any

from .storage import safe_file


STATUS_LABELS = {
    "approved": "Approved",
    "maybe": "Maybe",
    "rejected": "Rejected",
    "": "Unreviewed",
}


def _thumbnail_data_uri(item: dict[str, Any]) -> str | None:
    if not item.get("present"):
        return None
    source = safe_file(str(item["collection"]), str(item["rel"]))
    if source is None:
        return None
    try:
        from .app import make_thumbnail

        payload = make_thumbnail(source)
    except Exception:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(payload).decode("ascii")


def _annotation_text(annotation: dict[str, Any]) -> str:
    state = "stale" if annotation.get("stale") else ("resolved" if annotation.get("resolved") else "open")
    kind = annotation.get("kind") or "annotation"
    text = str(annotation.get("text") or "").strip()
    return f"{kind} · {state}" + (f" — {text}" if text else "")


def render_markdown_report(manifest: dict[str, Any], *, title: str = "Asset Viewer Review Report") -> str:
    counts = manifest["counts"]
    lines = [
        f"# {title}",
        "",
        f"Generated: {manifest.get('generated_at', '-')}",
        "",
        "## Summary",
        "",
        f"- Total: {counts['total']}",
        f"- Approved: {counts['approved']}",
        f"- Maybe: {counts['maybe']}",
        f"- Rejected: {counts['rejected']}",
        f"- Unreviewed: {counts['unreviewed']}",
        f"- New/unseen: {counts['new']}",
        "",
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in manifest["items"]:
        grouped[str(item["collection_label"])].append(item)

    for label, items in grouped.items():
        lines.extend([f"## {label}", ""])
        for item in items:
            status = STATUS_LABELS.get(str(item.get("status") or ""), str(item.get("status") or "Unreviewed"))
            presence = "" if item.get("present") else " · Missing"
            lines.append(f"### {item['rel']} — {status}{presence}")
            family = item.get("family")
            if family:
                preferred = " · preferred" if family.get("preferred") else ""
                lines.append(f"Family: {family.get('name', family.get('family_id'))}{preferred}")
            comment = str(item.get("comment") or "").strip()
            if comment:
                lines.extend(["", f"> {comment}"])
            annotations = item.get("annotations") or []
            if annotations:
                lines.extend(["", "Annotations:"])
                lines.extend(f"- {_annotation_text(annotation)}" for annotation in annotations)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_html_report(
    manifest: dict[str, Any],
    *,
    title: str = "Asset Viewer Review Report",
    embed_images: bool = True,
) -> str:
    counts = manifest["counts"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in manifest["items"]:
        grouped[str(item["collection_label"])].append(item)

    sections: list[str] = []
    for label, items in grouped.items():
        rows: list[str] = []
        for item in items:
            status_key = str(item.get("status") or "")
            status = STATUS_LABELS.get(status_key, status_key or "Unreviewed")
            image = _thumbnail_data_uri(item) if embed_images else None
            image_html = (
                f'<img src="{image}" alt="Preview of {html.escape(str(item["rel"]))}">' if image
                else '<div class="no-preview">No preview</div>'
            )
            comment = str(item.get("comment") or "").strip()
            comment_html = f'<p class="comment">{html.escape(comment)}</p>' if comment else ""
            family = item.get("family")
            family_html = ""
            if family:
                preferred = " · preferred" if family.get("preferred") else ""
                family_html = f'<div class="meta">Family: {html.escape(str(family.get("name") or family.get("family_id")))}{preferred}</div>'
            annotation_html = ""
            annotations = item.get("annotations") or []
            if annotations:
                annotation_html = "<ul>" + "".join(
                    f"<li>{html.escape(_annotation_text(annotation))}</li>" for annotation in annotations
                ) + "</ul>"
            missing = '<span class="missing">Missing</span>' if not item.get("present") else ""
            rows.append(
                '<article class="asset">'
                f'<div class="preview">{image_html}</div>'
                '<div class="asset-body">'
                f'<div class="asset-head"><strong>{html.escape(str(item["rel"]))}</strong>'
                f'<span class="status status-{html.escape(status_key or "unreviewed")}">{html.escape(status)}</span>{missing}</div>'
                f'{family_html}{comment_html}{annotation_html}'
                '</div></article>'
            )
        sections.append(f'<section><h2>{html.escape(label)}</h2><div class="assets">{"".join(rows)}</div></section>')

    summary = "".join(
        f'<div><strong>{value}</strong><span>{label}</span></div>'
        for label, value in [
            ("Total", counts["total"]),
            ("Approved", counts["approved"]),
            ("Maybe", counts["maybe"]),
            ("Rejected", counts["rejected"]),
            ("Unreviewed", counts["unreviewed"]),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#18202a;background:#f5f6f8}}
*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1180px;margin:0 auto;padding:36px 24px 64px}}
header{{border-bottom:1px solid #cfd5dd;padding-bottom:22px;margin-bottom:28px}}h1{{margin:0 0 8px;font-size:30px}}h2{{font-size:20px;margin:32px 0 12px}}
.generated{{color:#65707e;font-size:13px}}.summary{{display:flex;flex-wrap:wrap;gap:20px;margin-top:20px}}.summary div{{min-width:110px}}
.summary strong{{display:block;font-size:24px}}.summary span{{color:#65707e;font-size:12px;text-transform:uppercase;letter-spacing:.06em}}
.assets{{border-top:1px solid #d9dee5}}.asset{{display:grid;grid-template-columns:180px 1fr;gap:18px;padding:18px 0;border-bottom:1px solid #d9dee5}}
.preview{{width:180px;height:130px;background:#e8ebef;display:flex;align-items:center;justify-content:center;overflow:hidden;border-radius:8px}}
.preview img{{width:100%;height:100%;object-fit:contain;background:#fff}}.no-preview{{color:#7b8490;font-size:12px}}.asset-body{{min-width:0}}
.asset-head{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}.asset-head strong{{overflow-wrap:anywhere}}.status,.missing{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;padding:4px 7px;border-radius:999px}}
.status-approved{{background:#dff4e6;color:#205e35}}.status-maybe{{background:#fff1c9;color:#75520a}}.status-rejected{{background:#f9dddd;color:#7c2525}}.status-unreviewed{{background:#e6e9ed;color:#515b67}}.missing{{background:#ede4f8;color:#634183}}
.meta{{color:#65707e;font-size:13px;margin-top:7px}}.comment{{margin:10px 0 0;white-space:pre-wrap}}ul{{margin:10px 0 0;padding-left:20px;color:#495463}}
@media(max-width:650px){{main{{padding:24px 16px}}.asset{{grid-template-columns:1fr}}.preview{{width:100%;height:220px}}}}
@media print{{body{{background:#fff}}main{{max-width:none;padding:0}}.asset{{break-inside:avoid}}}}
</style>
</head>
<body><main>
<header><h1>{html.escape(title)}</h1><div class="generated">Generated {html.escape(str(manifest.get('generated_at', '-')))}</div><div class="summary">{summary}</div></header>
{''.join(sections)}
</main></body></html>
"""


def render_review_report(
    manifest: dict[str, Any],
    *,
    format: str = "html",
    title: str = "Asset Viewer Review Report",
    embed_images: bool = True,
) -> str:
    if format == "html":
        return render_html_report(manifest, title=title, embed_images=embed_images)
    if format in {"markdown", "md"}:
        return render_markdown_report(manifest, title=title)
    raise ValueError(f"unsupported report format: {format}")
