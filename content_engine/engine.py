from __future__ import annotations

import shutil
import json
from datetime import date
from pathlib import Path

from content_engine.archive.store import ContentArchive
from content_engine.config.brands import load_brands
from content_engine.platform.pipeline import create_queue, run_morning
from content_engine.signals.importer import collect_signals_from_sources, import_signals_from_inbox
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


def morning(today: date | None = None) -> Path:
    return run_morning(today=today)


def brand_lines() -> list[str]:
    return [
        f"{brand.slug}: {brand.name} ({', '.join(brand.social_platforms)})"
        for brand in load_brands()
    ]


def history_lines(limit: int = 20) -> list[str]:
    rows = ContentArchive().history(limit=limit)
    if not rows:
        return ["No archived posts yet."]
    return [
        f"{row['date']} | {row['brand']} | {row['platform']} | {row['content_type']} | {row['score']}/100"
        for row in rows
    ]


def latest_report_dir(base_dir: Path | str = "reports") -> Path | None:
    reports_base = Path(base_dir)
    if not reports_base.exists():
        return None
    dated_dirs = sorted([path for path in reports_base.iterdir() if path.is_dir()], reverse=True)
    return dated_dirs[0] if dated_dirs else None


def platform_report() -> Path:
    current = latest_report_dir()
    if current is None or not (current / "summary.md").exists():
        current = morning()
    return current / "summary.md"


def stats_text() -> str:
    current = latest_report_dir()
    statistics_path = current / "statistics.json" if current else None
    if statistics_path is None or not statistics_path.exists():
        current = morning()
        statistics_path = current / "statistics.json"
    return json.dumps(json.loads(statistics_path.read_text(encoding="utf-8")), indent=2)


def import_signal_lines() -> list[str]:
    return import_signals_from_inbox().lines()


def collect_signal_lines() -> list[str]:
    return collect_signals_from_sources().lines()


def signal_lines(
    brand_filter: str | None = None,
    today_only: bool = False,
    high_priority: bool = False,
    limit: int = 20,
) -> list[str]:
    signals = ContentArchive().recent_signals(
        limit=limit,
        brand_filter=brand_filter,
        today_only=today_only,
        high_priority=high_priority,
    )
    if not signals:
        return ["No signals imported yet."]
    return [
        f"{signal.id} | {signal.brand} | {signal.source_type} | priority {signal.priority} | confidence {round(signal.confidence * 100)}% | {signal.title}"
        for signal in signals
    ]


def queue_lines() -> list[str]:
    queue, skipped = create_queue()
    if not queue:
        return [f"No queued content. Skipped duplicates: {skipped}."]
    lines = [f"Queued items: {len(queue)}", f"Skipped duplicates: {skipped}"]
    lines.extend(
        f"{item.scheduled_time} | {item.platform} | {item.brand} | {item.rank_score}/100 | {item.signal.title} | {item.reason}"
        for item in queue
    )
    return lines


def preview_path() -> Path:
    current = latest_report_dir()
    if current is None or not (current / "preview.html").exists():
        current = morning()
    return current / "preview.html"
