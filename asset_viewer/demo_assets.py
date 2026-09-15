from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEMO_COLLECTION_LABEL = "Northline Coffee — Summer Launch"
DEMO_PROJECT = "northline-summer-launch"
DEMO_REVIEWS = {
    "01-hero-product-focus.png": (
        "approved",
        "Strong product focus and clean headline space. Use this as the primary launch direction.",
    ),
    "02-hero-lifestyle.png": (
        "maybe",
        "Great atmosphere. Compare against the product-first variant before finalizing the hero.",
    ),
    "03-social-tight-crop.png": (
        "rejected",
        "The crop is too tight and the product feels crowded. Show more environment.",
    ),
    "05-lifestyle-tote.png": (
        "maybe",
        "Good lifestyle direction. Try a larger mark so the tote reads better at mobile size.",
    ),
}
DEMO_FAMILY = (
    "Summer hero concepts",
    ("01-hero-product-focus.png", "02-hero-lifestyle.png"),
    "01-hero-product-focus.png",
)

DEMO_FILES = (
    "01-hero-product-focus.png",
    "02-hero-lifestyle.png",
    "03-social-tight-crop.png",
    "04-product-lineup.png",
    "05-lifestyle-tote.png",
    "06-homepage-banner.png",
)
LEGACY_DEMO_FILES = (
    "launch-poster.png",
    "product-card.png",
    "social-square.png",
    "banner-wide.png",
    "concept-a.png",
    "concept-b.png",
)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(round(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        draw.line((0, y, width, y), fill=color)
    return image


def _headline(draw: ImageDraw.ImageDraw, xy: tuple[int, int], lines: list[str], color=(22, 34, 48)) -> None:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, fill=color, font=_font(58))
        y += 62


def _brand(draw: ImageDraw.ImageDraw, xy: tuple[int, int], color=(22, 34, 48)) -> None:
    draw.text(xy, "N O R T H L I N E   C O F F E E", fill=color, font=_font(22))


def _can(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], body: tuple[int, int, int], accent: tuple[int, int, int], flavor: str) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=34, fill=body, outline=(225, 225, 225), width=3)
    draw.ellipse((x0 + 5, y0 - 9, x1 - 5, y0 + 20), fill=(190, 194, 197))
    draw.rectangle((x0, y1 - 115, x1, y1), fill=accent)
    cx = (x0 + x1) // 2
    draw.text((cx, y0 + 72), "NORTHLINE", anchor="mm", fill=(246, 244, 235), font=_font(25))
    draw.text((cx, y0 + 112), "COFFEE", anchor="mm", fill=(246, 244, 235), font=_font(21))
    draw.text((cx, (y0 + y1) // 2), flavor, anchor="mm", fill=(246, 244, 235), font=_font(30))
    draw.text((cx, y1 - 55), "COLD BREW", anchor="mm", fill=(246, 244, 235), font=_font(20))


def _glass(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=22, fill=(89, 48, 24), outline=(238, 225, 200), width=6)
    ice = ((22, 36, 38), (74, 82, 46), (132, 48, 34), (154, 136, 42),
           (40, 172, 50), (104, 214, 36), (158, 250, 44), (62, 292, 40))
    width = max(1, x1 - x0)
    height = max(1, y1 - y0)
    for dx, dy, size in ice:
        s = min(size, max(18, min(width, height) // 4))
        x = min(x0 + 18 + dx, x1 - s - 12)
        y = min(y0 + 22 + dy, y1 - s - 12)
        draw.rounded_rectangle((x, y, x + s, y + s), radius=9, fill=(205, 156, 94), outline=(239, 214, 169), width=2)
    draw.text(((x0 + x1) // 2, (y0 + y1) // 2 + 25), "NORTHLINE", anchor="mm", fill="white", font=_font(24))


def _coast(image: Image.Image, *, sunset: bool = False) -> ImageDraw.ImageDraw:
    draw = ImageDraw.Draw(image)
    width, height = image.size
    horizon = int(height * 0.56)
    ocean = (77, 153, 184) if not sunset else (78, 132, 159)
    draw.rectangle((0, horizon, width, height), fill=ocean)
    for y in range(horizon + 25, height, 44):
        draw.arc((-80, y, width + 120, y + 42), 190, 350, fill=(220, 242, 242), width=4)
    draw.polygon(((width * .72, horizon), (width, horizon - 105), (width, height)), fill=(73, 70, 64))
    return draw


def _hero_product(path: Path) -> None:
    image = _gradient((1200, 800), (173, 220, 240), (239, 226, 191))
    draw = _coast(image)
    for index in range(45):
        x = 520 + ((index * 83) % 620)
        y = 565 + ((index * 47) % 205)
        size = 18 + ((index * 19) % 38)
        draw.polygon(((x, y), (x + size, y - size // 2), (x + size * 2, y + 5), (x + size, y + size)), fill=(225, 247, 252), outline=(180, 218, 230))
    _brand(draw, (70, 75))
    _headline(draw, (70, 250), ["Good Coffee", "Brighter Days"])
    draw.text((73, 400), "SUMMER LAUNCH  /  PRODUCT-FOCUSED HERO", fill=(41, 64, 78), font=_font(21))
    _can(draw, (770, 145, 1010, 670), (22, 24, 26), (27, 28, 30), "BLACK")
    image.save(path)


def _hero_lifestyle(path: Path) -> None:
    image = _gradient((1200, 800), (250, 191, 134), (239, 227, 192))
    draw = _coast(image, sunset=True)
    _brand(draw, (75, 70))
    _headline(draw, (75, 225), ["A Brighter", "Kind of Energy"])
    draw.text((78, 365), "COLD BREW FOR WHAT'S NEXT", fill=(52, 57, 61), font=_font(24))
    draw.rounded_rectangle((78, 435, 345, 500), radius=7, fill=(25, 42, 55))
    draw.text((211, 467), "FIND YOUR FLOW  →", anchor="mm", fill="white", font=_font(21))
    _glass(draw, (825, 285, 1060, 690))
    image.save(path)


def _tight_crop(path: Path) -> None:
    image = _gradient((1000, 1000), (180, 122, 85), (43, 55, 60))
    draw = ImageDraw.Draw(image)
    draw.ellipse((-120, 100, 500, 780), fill=(197, 139, 103))
    _glass(draw, (570, 105, 1050, 930))
    draw.text((650, 510), "TOO TIGHT", fill=(255, 229, 198), font=_font(28))
    image.save(path)


def _lineup(path: Path) -> None:
    image = _gradient((1200, 800), (243, 238, 222), (217, 225, 213))
    draw = ImageDraw.Draw(image)
    _brand(draw, (70, 65))
    draw.text((70, 120), "Cold Brew Lineup", fill=(28, 38, 44), font=_font(55))
    cans = [
        ((170, 230, 390, 690), (236, 231, 213), (70, 141, 150), "VANILLA"),
        ((490, 210, 710, 690), (232, 223, 198), (46, 43, 37), "CLASSIC"),
        ((810, 230, 1030, 690), (220, 169, 93), (116, 72, 35), "SALTED CARAMEL"),
    ]
    for box, body, accent, flavor in cans:
        _can(draw, box, body, accent, flavor)
    image.save(path)


def _tote(path: Path) -> None:
    image = _gradient((1200, 800), (153, 207, 224), (239, 216, 172))
    draw = _coast(image)
    draw.polygon(((460, 180), (780, 180), (865, 690), (375, 690)), fill=(232, 221, 194), outline=(166, 150, 120))
    draw.arc((470, 55, 760, 310), 185, 355, fill=(153, 133, 100), width=18)
    draw.text((620, 360), "GOOD", anchor="mm", fill=(35, 43, 45), font=_font(44))
    draw.text((620, 418), "COFFEE", anchor="mm", fill=(35, 43, 45), font=_font(44))
    draw.text((620, 476), "BRIGHTER DAYS", anchor="mm", fill=(35, 43, 45), font=_font(31))
    draw.text((620, 560), "logo may need to be larger", anchor="mm", fill=(105, 93, 72), font=_font(20))
    image.save(path)


def _banner(path: Path) -> None:
    image = _gradient((1400, 600), (247, 186, 130), (113, 165, 187))
    draw = _coast(image, sunset=True)
    _brand(draw, (760, 80), color=(28, 45, 56))
    _headline(draw, (760, 160), ["Summer", "Tastes Better Here"], color=(28, 45, 56))
    draw.rounded_rectangle((765, 390, 1035, 452), radius=8, fill=(25, 42, 55))
    draw.text((900, 421), "FIND YOUR FLOW  →", anchor="mm", fill="white", font=_font(20))
    image.save(path)


def create_demo(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    # Demo generation is intentionally idempotent. Remove only Asset Viewer
    # demo filenames so rerunning this command never deletes unrelated images.
    for name in (*DEMO_FILES, *LEGACY_DEMO_FILES):
        target = directory / name
        if target.is_file():
            target.unlink()
    renderers = [
        ("01-hero-product-focus.png", _hero_product),
        ("02-hero-lifestyle.png", _hero_lifestyle),
        ("03-social-tight-crop.png", _tight_crop),
        ("04-product-lineup.png", _lineup),
        ("05-lifestyle-tote.png", _tote),
        ("06-homepage-banner.png", _banner),
    ]
    for name, render in renderers:
        render(directory / name)
