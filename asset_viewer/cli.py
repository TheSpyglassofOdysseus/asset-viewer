from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import __version__
from .app import serve
from .storage import add_collection, collections, remove_collection


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
    for index, (name, title, background, foreground) in enumerate(specs, 1):
        size = (1200, 800) if "wide" not in name else (1400, 600)
        image = Image.new("RGB", size, background)
        draw = ImageDraw.Draw(image)
        margin = 70
        draw.rounded_rectangle((margin, margin, size[0] - margin, size[1] - margin), radius=28, outline=foreground, width=3)
        draw.text((margin + 45, margin + 40), "ASSET VIEWER / DEMO", fill=foreground)
        draw.text((margin + 45, size[1] // 2 - 18), title, fill=foreground, font=ImageFont.load_default(size=32) if hasattr(ImageFont.load_default(), "font_variant") else None)
        draw.text((margin + 45, size[1] - margin - 70), f"Synthetic review asset {index:02d}", fill=foreground)
        image.save(directory / name)


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

    run = sub.add_parser("serve", help="Run the web viewer")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8160)

    demo = sub.add_parser("demo", help="Create and register synthetic demo assets")
    demo.add_argument("--path", default="./asset-viewer-demo")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
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
    elif args.command == "serve":
        serve(args.host, args.port)
    elif args.command == "demo":
        path = Path(args.path).expanduser().resolve()
        create_demo(path)
        row = add_collection(str(path), "Asset Viewer Demo")
        print(f"Created and registered demo collection: {row['path']}")
        print("Run: asset-viewer serve")
    else:
        parser.print_help()
