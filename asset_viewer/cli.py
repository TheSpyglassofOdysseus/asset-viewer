from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import __version__
from .app import LOOPBACK_HOSTS, scan_collection, serve
from .storage import add_collection, collections, data_dir, database_path, remove_collection, review_manifest


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
        images, meta = scan_collection(row["slug"])
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
        readable = os.access(path, os.R_OK | os.X_OK)
        findings.append(("PASS" if readable else "FAIL", f"{row['slug']}: {'readable' if readable else 'not readable'} — {path}"))
    normalized = {item.lower().rstrip('.') for item in trusted_hosts}
    if host not in LOOPBACK_HOSTS and not normalized:
        findings.append(("FAIL", "non-loopback bind has no --trusted-host"))
    elif host not in LOOPBACK_HOSTS:
        findings.append(("WARN", "non-loopback bind: keep Asset Viewer behind TLS and an authenticated/private access boundary"))
    else:
        findings.append(("PASS", "loopback bind is the safest default"))
    findings.append(("PASS" if os.environ.get("ASSET_VIEWER_PASSWORD") else "INFO", "built-in Basic auth " + ("enabled" if os.environ.get("ASSET_VIEWER_PASSWORD") else "disabled (acceptable for localhost/private proxy use)")))
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

    scan = sub.add_parser("scan", help="Discover assets and refresh review metadata")
    scan.add_argument("--collection")

    reviews = sub.add_parser("reviews", help="Read review state for agents or humans")
    reviews.add_argument("--collection")
    reviews.add_argument("--status", choices=["approved", "maybe", "rejected", "unreviewed", "new"])
    reviews.add_argument("--json", action="store_true")
    reviews.add_argument("--no-scan", action="store_true", help="Do not scan folders before reading the manifest")

    export = sub.add_parser("export-manifest", help="Export machine-readable review state")
    export.add_argument("--collection")
    export.add_argument("--status", choices=["approved", "maybe", "rejected", "unreviewed", "new"])
    export.add_argument("--output", default="-", help="Output file or - for stdout")
    export.add_argument("--no-scan", action="store_true")

    run = sub.add_parser("serve", help="Run the web viewer")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8160)
    run.add_argument("--trusted-host", action="append", default=[], help="Allowed Host header (repeatable). Required for non-loopback binds and reverse proxies.")
    run.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")

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
        elif args.command == "scan":
            for slug, count, truncated in scan_registered(args.collection):
                print(f"{slug}\t{count} images\t{'TRUNCATED' if truncated else 'complete'}")
        elif args.command == "reviews":
            if not args.no_scan:
                scan_registered(args.collection)
            print_manifest(review_manifest(args.collection, args.status), args.json)
        elif args.command == "export-manifest":
            if not args.no_scan:
                scan_registered(args.collection)
            payload = json.dumps(review_manifest(args.collection, args.status), indent=2, sort_keys=True) + "\n"
            if args.output == "-":
                sys.stdout.write(payload)
            else:
                Path(args.output).expanduser().write_text(payload)
                print(f"Wrote {args.output}")
        elif args.command == "serve":
            serve(args.host, args.port, args.trusted_host, log_level=args.log_level)
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
