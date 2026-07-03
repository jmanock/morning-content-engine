from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

from content_engine.models import RankedDeal


def create_image_prompts(selected: list[RankedDeal], output_dir: Path) -> Path:
    path = output_dir / "image_prompts.txt"
    lines = []
    for index, ranked in enumerate(selected, start=1):
        deal = ranked.deal
        lines.extend(
            [
                f"{index}. {deal.short_title}",
                f"Category: {deal.category}",
                f"Prompt: {deal.image_prompt}",
                "",
            ]
        )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def create_placeholder_images(selected: list[RankedDeal], output_dir: Path) -> dict[str, Path]:
    top = selected[0].deal if selected else None
    square = output_dir / "instagram_square.png"
    facebook = output_dir / "facebook_post.png"
    _draw_deal_image(square, (1080, 1080), top, "Instagram")
    _draw_deal_image(facebook, (1200, 630), top, "Facebook")
    return {"instagram_square": square, "facebook_post": facebook}


def _draw_deal_image(path: Path, size: tuple[int, int], deal, platform: str) -> None:
    width, height = size
    background = "#f7fbff"
    accent = "#0077b6"
    dark = "#172026"
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)

    font_large = _font(72 if width >= 1000 else 52, bold=True)
    font_medium = _font(44 if width >= 1000 else 34, bold=True)
    font_small = _font(30 if width >= 1000 else 24)
    font_tiny = _font(24 if width >= 1000 else 20)

    draw.rectangle([(0, 0), (width, 120)], fill=accent)
    draw.text((60, 36), "Today's Deal", font=font_medium, fill="white")
    draw.text((width - 220, 44), platform, font=font_tiny, fill="white")

    if deal is None:
        draw.text((60, 190), "No deals selected", font=font_large, fill=dark)
    else:
        y = 190
        for line in wrap(deal.short_title, width=24 if width == height else 34)[:3]:
            draw.text((60, y), line, font=font_large, fill=dark)
            y += 82

        draw.text((60, y + 25), f"${deal.price:,.0f}", font=font_large, fill=accent)
        draw.text((60, y + 115), f"Usually ${deal.original_price:,.0f} | {deal.savings_percent}% off", font=font_small, fill=dark)
        draw.text((60, y + 170), deal.category.upper(), font=font_small, fill="#495057")

        footer_y = height - 110
        draw.rectangle([(0, footer_y), (width, height)], fill="#e9f5fb")
        draw.text((60, footer_y + 34), deal.site, font=font_small, fill=dark)
        draw.text((width - 360, footer_y + 38), deal.destination_or_brand, font=font_tiny, fill="#495057")

    image.save(path)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()

