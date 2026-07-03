from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from content_engine.ranking.scorer import rank_deals, select_top_deals
from content_engine.rendering.images import create_image_prompts, create_placeholder_images
from content_engine.reports.writer import (
    ensure_daily_output_dir,
    write_daily_report,
    write_selected_deals,
    write_text_packages,
)
from content_engine.social.captions import generate_facebook_caption, generate_instagram_caption
from content_engine.social.hashtags import format_hashtags, generate_hashtags
from content_engine.sources.sample_loader import load_sample_deals


def generate(today: date | None = None) -> Path:
    current_date = today or date.today()
    deals = load_sample_deals()
    selected = select_top_deals(deals, limit=5, today=current_date)
    output_dir = ensure_daily_output_dir(today=current_date)

    instagram_caption = generate_instagram_caption(selected)
    facebook_caption = generate_facebook_caption(selected)
    hashtags = format_hashtags(generate_hashtags(selected))

    write_selected_deals(selected, output_dir)
    write_text_packages(instagram_caption, facebook_caption, hashtags, output_dir)
    create_image_prompts(selected, output_dir)
    create_placeholder_images(selected, output_dir)
    write_daily_report(selected, current_date, instagram_caption, facebook_caption, hashtags, output_dir)
    return output_dir


def latest_output_dir(base_dir: Path | str = "output") -> Path | None:
    output_base = Path(base_dir)
    if not output_base.exists():
        return None
    dated_dirs = sorted([path for path in output_base.iterdir() if path.is_dir()], reverse=True)
    return dated_dirs[0] if dated_dirs else None


def report() -> Path:
    current = latest_output_dir()
    if current is None or not (current / "daily_report.md").exists():
        current = generate()
    return current / "daily_report.md"


def top(limit: int = 5) -> list[str]:
    deals = load_sample_deals()
    ranked = rank_deals(deals)
    return [
        f"{index}. {item.deal.short_title} - {item.score}/100 - {item.deal.site}"
        for index, item in enumerate(ranked[:limit], start=1)
    ]


def clean(base_dir: Path | str = "output") -> None:
    output_base = Path(base_dir)
    if output_base.exists():
        shutil.rmtree(output_base)
    output_base.mkdir(parents=True, exist_ok=True)
