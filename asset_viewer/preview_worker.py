from __future__ import annotations

import os
import warnings
from contextlib import suppress
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


def _apply_resource_limits(memory_bytes: int) -> None:
    """Apply best-effort child-process limits where the platform supports them."""
    if memory_bytes <= 0:
        return
    try:
        import resource

        # Address-space limit contains decoder explosions. The hard limit is kept
        # identical so a child cannot raise its own budget.
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        # Generated previews should never need large output files.
        resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    except (ImportError, OSError, ValueError):
        # Windows and some constrained platforms do not expose POSIX rlimits.
        pass


def _safe_preview_image(source: Path, max_pixels: int) -> tuple[Image.Image, tuple[int, int]]:
    Image.MAX_IMAGE_PIXELS = max_pixels
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(source) as opened:
            original_size = opened.size
            if opened.width * opened.height > max_pixels:
                raise ValueError("image exceeds configured pixel limit")
            image = ImageOps.exif_transpose(opened)
            image.load()
    return image, original_size


def render_preview_worker(
    source_text: str,
    destination_text: str,
    max_size: tuple[int, int],
    max_source_bytes: int,
    max_pixels: int,
    memory_bytes: int,
    sender: Any,
) -> None:
    """Decode/render one image in an isolated process and atomically publish it."""
    try:
        _apply_resource_limits(memory_bytes)
        source = Path(source_text)
        destination = Path(destination_text)
        stat = source.stat()
        if stat.st_size > max_source_bytes:
            raise ValueError("file exceeds configured preview byte limit")
        image, original_size = _safe_preview_image(source, max_pixels)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        if image.mode not in ("RGB", "L"):
            background = Image.new("RGB", image.size, (17, 17, 17))
            if "A" in image.getbands():
                background.paste(image, mask=image.getchannel("A"))
            else:
                background.paste(image.convert("RGB"))
            image = background
        elif image.mode == "L":
            image = image.convert("RGB")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        try:
            image.save(temporary, "JPEG", quality=84, optimize=True)
            os.replace(temporary, destination)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        sender.send({"ok": True, "width": original_size[0], "height": original_size[1]})
    except BaseException as exc:  # Child boundary: serialize failure, never leak it across the process boundary.
        with suppress(Exception):
            sender.send({"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500]})
    finally:
        with suppress(Exception):
            sender.close()


def inspect_images_worker(
    source_texts: list[str],
    max_source_bytes: int,
    max_pixels: int,
    memory_bytes: int,
    sender: Any,
) -> None:
    """Inspect changed image headers in one disposable bounded worker process."""
    results: dict[str, dict[str, Any]] = {}
    try:
        _apply_resource_limits(memory_bytes)
        Image.MAX_IMAGE_PIXELS = max_pixels
        for source_text in source_texts:
            source = Path(source_text)
            try:
                if source.stat().st_size > max_source_bytes:
                    results[source_text] = {"width": 0, "height": 0, "error": "preview source exceeds configured size limit"}
                    continue
                if source.suffix.lower() == ".svg":
                    results[source_text] = {"width": 0, "height": 0, "error": None}
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(source) as image:
                        if image.width * image.height > max_pixels:
                            raise ValueError("image exceeds configured pixel limit")
                        results[source_text] = {"width": int(image.width), "height": int(image.height), "error": None}
            except (OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
                results[source_text] = {"width": 0, "height": 0, "error": f"{type(exc).__name__}: {exc}"[:500]}
        sender.send({"ok": True, "results": results})
    except BaseException as exc:
        with suppress(Exception):
            sender.send({"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500], "results": results})
    finally:
        with suppress(Exception):
            sender.close()
