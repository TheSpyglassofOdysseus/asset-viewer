from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import __version__
from .app import LOOPBACK_HOSTS, capability_document, scan_collection, serve
from .storage import (
    add_collection,
    catalog_records,
    catalog_state,
    collections,
    complete_collection_review,
    data_dir,
    database_path,
    pending_summary,
    remove_collection,
    reopen_collection_review,
    review_events_since,
    review_history,
    review_manifest,
    root_for,
    undo_last_review,
)


def create_demo(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    specs = [
        ("launch-poster.png", "Launch Poster", (34, 50, 75), (235, 244, 255)),
        ("product-card.png", "Product Card", (45, 79, 61), (235, 255, 241)),
        ("social-square.png", "Social Square", (76, 44, 84), (252, 239, 255)),
        ("banner-wide.png", "Banner Wide", (89, 61, 34), (255, 247, 229)),
        ("concept-a.png", "Concept A", (42, 42, 42), (247, 247, 247)),
        ("concept-b.png", "Concept B", (28, 63, 82), (235, 249, 255)),
    ]
    default_font = ImageFont.load_default()
    for index, (name, title, background, foreground) in enumerate(specs, 1):
        size = (1200, 800) if "wide" not in name else (1400, 600)
        image = Image.new("RGB", size, background)
        draw = ImageDraw.Draw(image)
        margin = 70
        draw.rounded_rectangle((margin, margin, size[0] - margin, size[1] - margin), radius=28, outline=foreground, width=3)
        draw.text((margin + 45, margin + 40), "ASSET VIEWER / DEMO", fill=foreground, font=default_font)
        draw.text((margin + 45, size[1] // 2 - 18), title, fill=foreground, font=default_font)
        draw.text((margin + 45, size[1] - margin - 70), f"Synthetic review asset {index:02d}", fill=foreground, font=default_font)
        image.save(directory / name)


def scan_registered(collection: str | None = None) -> list[tuple[str, int, bool]]:
    rows = collections()
    if collection:
        rows = [row for row in rows if row["slug"] == collection]
        if not rows:
            raise ValueError(f"collection not found: {collection}")
    result = []
    for row in rows:
        images, meta = scan_collection(row["slug"], force=True)
        result.append((row["slug"], len(images), bool(meta["truncated"])))
    return result


def print_manifest(manifest: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return
    counts = manifest["counts"]
    print(
        f"total={counts['total']} approved={counts['approved']} maybe={counts['maybe']} "
        f"rejected={counts['rejected']} unreviewed={counts['unreviewed']} new={counts['new']}"
    )
    for item in manifest["items"]:
        status = item["status"] or "unreviewed"
        comment = item["comment"].replace("\t", " ").replace("\n", " ")
        print(f"{item['collection']}\t{status}\t{item['rel']}\t{comment}")


def doctor(host: str, trusted_hosts: list[str]) -> int:
    findings: list[tuple[str, str]] = []
    root = data_dir()
    mode = stat.S_IMODE(root.stat().st_mode)
    findings.append(("PASS" if mode & 0o077 == 0 else "WARN", f"data directory permissions {oct(mode)}: {root}"))
    db = database_path()
    if db.exists():
        db_mode = stat.S_IMODE(db.stat().st_mode)
        findings.append(("PASS" if db_mode & 0o077 == 0 else "WARN", f"SQLite permissions {oct(db_mode)}: {db}"))
    rows = collections()
    findings.append(("PASS" if rows else "INFO", f"registered collections: {len(rows)}"))
    for row in rows:
        path = Path(row["path"])
        available = bool(row.get("available"))
        readable = available and os.access(path, os.R_OK | os.X_OK)
        findings.append(("PASS" if readable else "FAIL", f"{row['slug']}: {'readable' if readable else 'unavailable/not readable'} — {path}"))
        state = catalog_state(row["slug"])
        if state["generation"]:
            if state["truncated"]:
                findings.append(("WARN", f"{row['slug']}: latest catalog scan incomplete ({state['reason'] or 'unknown'})"))
            else:
                findings.append(("PASS", f"{row['slug']}: catalog generation {state['generation']} last scanned {state['last_scan_at']}"))
    normalized = {item.lower().rstrip('.') for item in trusted_hosts}
    if host not in LOOPBACK_HOSTS and not normalized:
        findings.append(("FAIL", "non-loopback bind has no --trusted-host"))
    elif host not in LOOPBACK_HOSTS:
        findings.append(("WARN", "non-loopback bind: keep Asset Viewer behind TLS and an authenticated/private access boundary"))
    else:
        findings.append(("PASS", "loopback bind is the safest default"))
    findings.append(("PASS" if os.environ.get("ASSET_VIEWER_PASSWORD") else "INFO", "built-in Basic auth " + ("enabled" if os.environ.get("ASSET_VIEWER_PASSWORD") else "disabled (acceptable for localhost/private proxy use)")))
    findings.append(("WARN", "built-in http.server is intended for local/private use; use a production reverse proxy/access boundary for remote service"))
    findings.append(("INFO", f"scan limits: files={os.environ.get('ASSET_VIEWER_MAX_SCAN_FILES', '50000')} seconds={os.environ.get('ASSET_VIEWER_MAX_SCAN_SECONDS', '10')}"))
    findings.append(("INFO", f"preview limits: bytes={os.environ.get('ASSET_VIEWER_MAX_THUMBNAIL_BYTES', str(250 * 1024 * 1024))} pixels={os.environ.get('ASSET_VIEWER_MAX_IMAGE_PIXELS', '50000000')} workers={os.environ.get('ASSET_VIEWER_THUMBNAIL_WORKERS', '2')}"))
    failures = 0
    for level, text in findings:
        print(f"[{level}] {text}")
        failures += level == "FAIL"
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asset-viewer", description="Local-first visual review gallery for image folders.")
    parser.add_argument("--version", action="version", version=f"asset-viewer {__version__}")
    sub = parser.add_subparsers(dest="command")

    add = sub.add_parser("add", help="Register an image folder")
    add.add_argument("path")
    add.add_argument("label", nargs="?")

    remove = sub.add_parser("remove", help="Remove a registered folder")
    remove.add_argument("key", help="Collection slug or absolute path")

    sub.add_parser("list", help="List registered folders")

    capabilities = sub.add_parser("capabilities", help="Describe the agent/API protocol and enabled capabilities")
    capabilities.add_argument("--json", action="store_true")

    scan = sub.add_parser("scan", help="Discover assets and refresh review metadata")
    scan.add_argument("--collection")

    reviews = sub.add_parser("reviews", help="Read review state for agents or humans")
    reviews.add_argument("--collection")
    reviews.add_argument("--status", choices=["approved", "maybe", "rejected", "unreviewed", "new"])
    reviews.add_argument("--json", action="store_true")
    reviews.add_argument("--no-scan", action="store_true", help="Do not scan folders before reading the manifest")
    reviews.add_argument("--present-only", action="store_true", help="Exclude tombstoned/missing assets")

    export = sub.add_parser("export-manifest", help="Export machine-readable review state")
    export.add_argument("--collection")
    export.add_argument("--status", choices=["approved", "maybe", "rejected", "unreviewed", "new"])
    export.add_argument("--output", default="-", help="Output file or - for stdout")
    export.add_argument("--no-scan", action="store_true")
    export.add_argument("--present-only", action="store_true", help="Exclude tombstoned/missing assets")

    pending = sub.add_parser("pending", help="Report collections still waiting for human review")
    pending.add_argument("--collection")
    pending.add_argument("--json", action="store_true")
    pending.add_argument("--no-scan", action="store_true")

    events = sub.add_parser("events", help="Read ordered review events for agents/automation")
    events.add_argument("--collection")
    events.add_argument("--after", type=int, default=0, dest="after_id")
    events.add_argument("--limit", type=int, default=100)
    events.add_argument("--json", action="store_true")

    wait = sub.add_parser("wait-for-review", help="Wait until review is explicitly complete")
    wait.add_argument("--collection")
    wait.add_argument("--timeout", type=float, default=300.0, help="Maximum seconds to wait")
    wait.add_argument("--interval", type=float, default=2.0, help="Seconds between review-state checks")
    wait.add_argument("--scan-interval", type=float, default=30.0, help="Seconds between filesystem rescans")
    wait.add_argument("--json", action="store_true")
    wait.add_argument("--no-scan", action="store_true")

    complete = sub.add_parser("complete", help="Mark a collection review complete")
    complete.add_argument("collection")

    reopen = sub.add_parser("reopen", help="Reopen a completed collection review")
    reopen.add_argument("collection")

    history = sub.add_parser("history", help="Show review history for one asset")
    history.add_argument("collection")
    history.add_argument("rel")
    history.add_argument("--json", action="store_true")
    history.add_argument("--limit", type=int, default=50)

    undo = sub.add_parser("undo", help="Undo the most recent review/comment change for one asset")
    undo.add_argument("collection")
    undo.add_argument("rel")

    url = sub.add_parser("collection-url", help="Print a stable browser URL for a collection")
    url.add_argument("collection")
    url.add_argument("--base-url", default="http://127.0.0.1:8160")

    asset_url = sub.add_parser("asset-url", help="Print a stable browser deep link for one asset")
    asset_url.add_argument("collection")
    asset_url.add_argument("asset", help="Stable asset ID or relative path")
    asset_url.add_argument("--base-url", default="http://127.0.0.1:8160")

    run = sub.add_parser("serve", help="Run the web viewer")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8160)
    run.add_argument("--trusted-host", action="append", default=[], help="Allowed Host header (repeatable). Required for non-loopback binds and reverse proxies.")
    run.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")
    run.add_argument(
        "--allow-unauthenticated-remote", action="store_true",
        help="Allow a non-loopback listener without built-in Basic auth. Use only behind a trusted authenticated/private boundary.",
    )

    check = sub.add_parser("doctor", help="Check deployment safety and local state")
    check.add_argument("--host", default="127.0.0.1")
    check.add_argument("--trusted-host", action="append", default=[])

    demo = sub.add_parser("demo", help="Create and register synthetic demo assets")
    demo.add_argument("--path", default="./asset-viewer-demo")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "add":
            row = add_collection(args.path, args.label)
            print(f"Added {row['label']} ({row['slug']}): {row['path']}")
        elif args.command == "remove":
            row = remove_collection(args.key)
            print(f"Removed {row['label']} ({row['slug']})")
        elif args.command == "list":
            rows = collections()
            if not rows:
                print("No folders registered.")
            for row in rows:
                print(f"{row['slug']}\t{row['label']}\t{row['path']}")
        elif args.command == "capabilities":
            payload = capability_document()
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                enabled = [name for name, value in payload["features"].items() if value]
                print(f"Asset Viewer {payload['app_version']} protocol v{payload['protocol_version']}")
                print("Features: " + ", ".join(enabled))
        elif args.command == "scan":
            for slug, count, truncated in scan_registered(args.collection):
                print(f"{slug}\t{count} images\t{'TRUNCATED' if truncated else 'complete'}")
        elif args.command == "reviews":
            if not args.no_scan:
                scan_registered(args.collection)
            print_manifest(review_manifest(args.collection, args.status, include_missing=not args.present_only), args.json)
        elif args.command == "export-manifest":
            if not args.no_scan:
                scan_registered(args.collection)
            payload = json.dumps(
                review_manifest(args.collection, args.status, include_missing=not args.present_only),
                indent=2, sort_keys=True
            ) + "\n"
            if args.output == "-":
                sys.stdout.write(payload)
            else:
                Path(args.output).expanduser().write_text(payload)
                print(f"Wrote {args.output}")
        elif args.command == "pending":
            if not args.no_scan:
                scan_registered(args.collection)
            payload = pending_summary(args.collection)
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                for state in payload["collections"]:
                    marker = "PENDING" if state["pending"] else "COMPLETE"
                    print(f"{marker}\t{state['collection']}\tunreviewed={state['unreviewed']} new={state['new']} completed_at={state['completed_at'] or '-'}")
            raise SystemExit(2 if payload["pending"] else 0)
        elif args.command == "events":
            payload = review_events_since(args.collection, args.after_id, args.limit)
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                for event in payload["events"]:
                    target = event["rel"] or "(collection)"
                    print(f"{event['id']}\t{event['created_at']}\t{event['collection']}\t{target}\t{event['action']}")
        elif args.command == "wait-for-review":
            timeout = max(0.0, args.timeout)
            interval = max(0.1, args.interval)
            scan_interval = max(interval, args.scan_interval)
            started = time.monotonic()
            last_scan = -scan_interval
            while True:
                elapsed = time.monotonic() - started
                if not args.no_scan and elapsed - last_scan >= scan_interval:
                    scan_registered(args.collection)
                    last_scan = elapsed
                payload = pending_summary(args.collection)
                if not payload["pending"]:
                    if args.json:
                        print(json.dumps(payload, indent=2, sort_keys=True))
                    else:
                        print("Review complete")
                    raise SystemExit(0)
                if elapsed >= timeout:
                    if args.json:
                        print(json.dumps(payload, indent=2, sort_keys=True))
                    else:
                        print("Review still pending")
                    raise SystemExit(2)
                time.sleep(min(interval, max(0.0, timeout - elapsed)))
        elif args.command == "complete":
            if not root_for(args.collection):
                raise ValueError(f"collection not found: {args.collection}")
            scan_registered(args.collection)
            state = complete_collection_review(args.collection)
            print(f"Completed {args.collection} at {state['completed_at']}")
        elif args.command == "reopen":
            if not root_for(args.collection):
                raise ValueError(f"collection not found: {args.collection}")
            state = reopen_collection_review(args.collection)
            print(f"Reopened {args.collection}")
        elif args.command == "history":
            if not root_for(args.collection):
                raise ValueError(f"collection not found: {args.collection}")
            events = review_history(args.collection, args.rel, args.limit)
            if args.json:
                print(json.dumps({"collection": args.collection, "rel": args.rel, "events": events}, indent=2, sort_keys=True))
            else:
                for event in events:
                    undone = " UNDONE" if event["undone_at"] else ""
                    print(f"{event['id']}\t{event['created_at']}\t{event['action']}\t{event['old_status'] or 'unreviewed'} -> {event['new_status'] or 'unreviewed'}{undone}")
        elif args.command == "undo":
            if not root_for(args.collection):
                raise ValueError(f"collection not found: {args.collection}")
            result = undo_last_review(args.collection, args.rel)
            if not result:
                raise ValueError("no review change to undo")
            print(f"Restored {args.rel} to {result['status'] or 'unreviewed'}")
        elif args.command == "collection-url":
            if not root_for(args.collection):
                raise ValueError(f"collection not found: {args.collection}")
            print(args.base_url.rstrip('/') + "/c/" + args.collection)
        elif args.command == "asset-url":
            if not root_for(args.collection):
                raise ValueError(f"collection not found: {args.collection}")
            records = catalog_records(args.collection, present_only=False)
            asset = next((row for row in records if row["asset_id"] == args.asset or row["rel"] == args.asset), None)
            if not asset:
                raise ValueError(f"asset not found: {args.asset}")
            base = args.base_url.rstrip('/')
            print(base + "/c/" + args.collection + "?asset=" + asset["asset_id"])
        elif args.command == "serve":
            serve(
                args.host, args.port, args.trusted_host, log_level=args.log_level,
                allow_unauthenticated_remote=args.allow_unauthenticated_remote,
            )
        elif args.command == "doctor":
            raise SystemExit(doctor(args.host, args.trusted_host))
        elif args.command == "demo":
            path = Path(args.path).expanduser().resolve()
            create_demo(path)
            row = add_collection(str(path), "Asset Viewer Demo")
            print(f"Created and registered demo collection: {row['path']}")
            print("Run: asset-viewer serve")
        else:
            parser.print_help()
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
