from __future__ import annotations

import html
import json
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from content_engine.archive.store import ContentArchive
from content_engine.config.brands import load_brands
from content_engine.models import BrandProfile, GeneratedPost, QueuedContent, RankedDeal, Signal
from content_engine.quality.scorer import score_content
from content_engine.queue.builder import build_daily_queue
from content_engine.ranking.scorer import rank_deals
from content_engine.signals.importer import import_signals_from_inbox
from content_engine.sources.sample_loader import load_sample_deals
from content_engine.templates.renderer import TemplateCatalog, render_template


PLATFORMS = ["instagram", "facebook", "linkedin", "twitter", "newsletter", "blog"]
EMOJIS = {"none": "", "minimal": "*", "light": "*", "expressive": "*"}


def run_morning(today: date | None = None) -> Path:
    current_date = today or date.today()
    brands = load_brands()
    archive = ContentArchive()
    import_summary = import_signals_from_inbox(archive=archive)
    queue, skipped_duplicates = create_queue(current_date=current_date, archive=archive)
    posts = generate_posts(brands, current_date, archive, queue=queue)
    archive.save_posts(posts)
    return save_reports(posts, current_date, archive, queue=queue, import_summary=import_summary, skipped_duplicates=skipped_duplicates)


def create_queue(current_date: date | None = None, archive: ContentArchive | None = None) -> tuple[list[QueuedContent], int]:
    current_date = current_date or date.today()
    archive = archive or ContentArchive()
    existing_queue = archive.queue_for_date(current_date.isoformat())
    if existing_queue:
        return existing_queue, 0
    queue, skipped_duplicates = build_daily_queue(
        archive.recent_signals(limit=100),
        current_date,
        duplicate_keys=archive.signal_duplicate_keys(),
    )
    archive.save_queue(queue)
    return queue, skipped_duplicates


def generate_posts(
    brands: list[BrandProfile],
    current_date: date,
    archive: ContentArchive | None = None,
    queue: list[QueuedContent] | None = None,
) -> list[GeneratedPost]:
    archive = archive or ContentArchive()
    catalog = TemplateCatalog()
    existing = archive.existing_content_keys()
    if queue is not None and queue:
        return _generate_posts_from_queue(queue, brands, current_date, archive, catalog, existing)

    ranked_deals = rank_deals(load_sample_deals(), today=current_date)
    posts: list[GeneratedPost] = []

    for brand in brands:
        platforms = _schedule_list(brand, "platforms") or brand.social_platforms
        content_types = _schedule_list(brand, "content_types") or ["deal_post"]
        for platform in platforms:
            post = _generate_one_post(
                brand=brand,
                platform=platform,
                content_types=content_types,
                deals=ranked_deals,
                current_date=current_date,
                existing={*existing, *(item.archive_key() for item in posts)},
                catalog=catalog,
            )
            posts.append(post)
    return posts


def save_reports(
    posts: list[GeneratedPost],
    current_date: date,
    archive: ContentArchive | None = None,
    queue: list[QueuedContent] | None = None,
    import_summary: object | None = None,
    skipped_duplicates: int = 0,
) -> Path:
    archive = archive or ContentArchive()
    queue = queue or archive.queue_for_date(current_date.isoformat())
    report_dir = Path("reports") / current_date.isoformat()
    report_dir.mkdir(parents=True, exist_ok=True)

    for platform in PLATFORMS:
        _write_platform_report(
            report_dir / f"{platform}.md",
            platform,
            [post for post in posts if post.platform == platform],
        )

    stats = _statistics(posts, archive, queue, import_summary, skipped_duplicates)
    (report_dir / "summary.md").write_text(_summary_markdown(posts, stats, current_date, queue), encoding="utf-8")
    (report_dir / "preview.html").write_text(_preview_html(posts, stats, current_date, queue), encoding="utf-8")
    (report_dir / "publishing_schedule.md").write_text(_publishing_schedule(queue), encoding="utf-8")
    (report_dir / "statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (report_dir / "posts.json").write_text(json.dumps([post.to_dict() for post in posts], indent=2), encoding="utf-8")
    (report_dir / "queue.json").write_text(json.dumps([item.to_dict() for item in queue], indent=2), encoding="utf-8")
    return report_dir


def _generate_posts_from_queue(
    queue: list[QueuedContent],
    brands: list[BrandProfile],
    current_date: date,
    archive: ContentArchive,
    catalog: TemplateCatalog,
    existing: set[str],
) -> list[GeneratedPost]:
    brand_map = {brand.name: brand for brand in brands}
    posts: list[GeneratedPost] = []
    for item in queue:
        brand = brand_map.get(item.brand) or _brand_from_signal(item.signal)
        hashtags = _hashtags_for_platform(brand.hashtags, item.platform)
        variables = _signal_variables_for(brand, item.signal, item.platform, hashtags)
        template_path = catalog.choose(item.content_type, f"{item.date}:{item.signal.id}:{item.platform}")
        content = render_template(template_path, variables)
        all_existing = {*existing, *(post.archive_key() for post in posts)}
        if content.strip().lower() in all_existing:
            content = _make_unique_content(content, current_date, all_existing)
        score, reasons = score_content(content, item.platform, hashtags, all_existing)
        posts.append(
            GeneratedPost(
                date=current_date.isoformat(),
                brand=brand.name,
                brand_slug=brand.slug,
                platform=item.platform,
                content_type=item.content_type,
                content=content,
                hashtags=hashtags,
                score=score,
                score_reasons=reasons,
                template_used=str(template_path),
                variables=variables,
            )
        )
    return posts


def _generate_one_post(
    brand: BrandProfile,
    platform: str,
    content_types: list[str],
    deals: list[RankedDeal],
    current_date: date,
    existing: set[str],
    catalog: TemplateCatalog,
) -> GeneratedPost:
    rng = random.Random(f"{current_date.isoformat()}:{brand.slug}:{platform}")
    content_type_order = content_types[:]
    rng.shuffle(content_type_order)
    ranked_deal = _deal_for_brand(brand, deals)
    hashtags = _hashtags_for_platform(brand.hashtags, platform)
    variables = _variables_for(brand, ranked_deal, platform, hashtags)

    best_candidate: GeneratedPost | None = None
    for content_type in content_type_order:
        variations = catalog.variations_for(content_type)
        for template_path in variations:
            content = render_template(template_path, variables)
            score, reasons = score_content(content, platform, hashtags, existing)
            candidate = GeneratedPost(
                date=current_date.isoformat(),
                brand=brand.name,
                brand_slug=brand.slug,
                platform=platform,
                content_type=content_type,
                content=content,
                hashtags=hashtags,
                score=score,
                score_reasons=reasons,
                template_used=str(template_path),
                variables=variables,
            )
            if candidate.archive_key() not in existing:
                return candidate
            if best_candidate is None or candidate.score > best_candidate.score:
                best_candidate = candidate

    if best_candidate is None:
        raise ValueError(f"No templates found for brand {brand.slug}")

    content = _make_unique_content(best_candidate.content, current_date, existing)
    score, reasons = score_content(content, platform, hashtags, existing)
    return GeneratedPost(
        date=best_candidate.date,
        brand=best_candidate.brand,
        brand_slug=best_candidate.brand_slug,
        platform=best_candidate.platform,
        content_type=best_candidate.content_type,
        content=content,
        hashtags=best_candidate.hashtags,
        score=score,
        score_reasons=reasons,
        template_used=best_candidate.template_used,
        variables=best_candidate.variables,
    )


def _make_unique_content(content: str, current_date: date, existing: set[str]) -> str:
    for number in range(1, 100):
        suffix = f"\n\nUpdate for {current_date.isoformat()} #{number}."
        candidate = content + suffix
        if candidate.strip().lower() not in existing:
            return candidate
    raise ValueError("Could not create unique content after 99 attempts.")


def _schedule_list(brand: BrandProfile, key: str) -> list[str]:
    morning = brand.posting_schedule.get("morning", {})
    return list(morning.get(key, []))


def _deal_for_brand(brand: BrandProfile, deals: list[RankedDeal]) -> RankedDeal:
    if "offer" in brand.slug or "radar" in brand.slug:
        finance = [deal for deal in deals if deal.deal.category == "finance"]
        if finance:
            return finance[0]
    non_finance = [deal for deal in deals if deal.deal.category != "finance"]
    return non_finance[0] if non_finance else deals[0]


def _variables_for(brand: BrandProfile, ranked_deal: RankedDeal, platform: str, hashtags: list[str]) -> dict[str, str]:
    deal = ranked_deal.deal
    cta = "See the full list on the site" if platform in {"facebook", "linkedin", "newsletter"} else "Check today's Florida deals"
    return {
        "brand": brand.name,
        "title": deal.short_title,
        "city": deal.destination_or_brand,
        "price": f"${deal.price:,.0f}",
        "discount": f"{deal.savings_percent}% off",
        "emoji": EMOJIS.get(brand.emoji_style, ""),
        "cta": f"{cta}: {brand.website}",
        "hashtags": " ".join(hashtags),
        "affiliate_disclosure": brand.affiliate_disclosure,
    }


def _signal_variables_for(brand: BrandProfile, signal: Signal, platform: str, hashtags: list[str]) -> dict[str, str]:
    cta = "See the full list on the site" if platform in {"facebook", "linkedin", "newsletter", "blog"} else "Check today's update"
    link = signal.affiliate_url or signal.url or brand.website
    price = signal.metadata.get("price") or signal.metadata.get("bonus_value") or signal.metadata.get("value") or ""
    discount = signal.metadata.get("savings_percent") or signal.metadata.get("bonus_percent") or ""
    return {
        "brand": brand.name,
        "signal_id": signal.id,
        "title": signal.title,
        "summary": signal.summary,
        "description": signal.description,
        "category": signal.category,
        "city": str(signal.metadata.get("market", "")),
        "price": f"${price:,.0f}" if isinstance(price, int | float) else str(price),
        "discount": f"{discount}% potential value" if isinstance(discount, int | float) else str(discount),
        "url": signal.url,
        "affiliate_url": signal.affiliate_url,
        "confidence": f"{round(signal.confidence * 100)}%",
        "priority": str(signal.priority),
        "emoji": EMOJIS.get(brand.emoji_style, ""),
        "cta": f"{cta}: {link}",
        "hashtags": " ".join(hashtags),
        "affiliate_disclosure": brand.affiliate_disclosure,
    }


def _brand_from_signal(signal: Signal) -> BrandProfile:
    return BrandProfile(
        slug=signal.brand.lower().replace(" ", "_").replace("/", "_"),
        name=signal.brand,
        description=f"Auto-created profile for {signal.brand}",
        tone="Clear and helpful.",
        emoji_style="minimal",
        hashtags=[f"#{signal.brand.replace(' ', '')}", f"#{signal.category.title().replace(' ', '')}"],
        social_platforms=["facebook", "newsletter", "blog", "twitter", "linkedin"],
        website=signal.url,
        logo_path="",
        affiliate_disclosure="Review links and terms before publishing.",
        posting_schedule={},
    )


def _hashtags_for_platform(tags: list[str], platform: str) -> list[str]:
    if platform == "newsletter":
        return tags[:3]
    if platform == "linkedin":
        return tags[:5]
    if platform == "twitter":
        return tags[:3]
    return tags[:22]


def _write_platform_report(path: Path, platform: str, posts: list[GeneratedPost]) -> None:
    lines = [f"# {platform.title()} Posts", ""]
    if not posts:
        lines.append("No posts generated for this platform.")
    for post in posts:
        lines.extend(
            [
                f"## {post.brand} - {post.content_type}",
                "",
                f"Score: {post.score}/100",
                f"Template: `{post.template_used}`",
                "",
                post.content,
                "",
                "Quality notes:",
            ]
        )
        lines.extend([f"- {reason}" for reason in post.score_reasons])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _statistics(
    posts: list[GeneratedPost],
    archive: ContentArchive,
    queue: list[QueuedContent],
    import_summary: object | None,
    skipped_duplicates: int,
) -> dict[str, object]:
    by_platform = Counter(post.platform for post in posts)
    by_brand = Counter(post.brand for post in posts)
    scores = [post.score for post in posts]
    confidences = [item.signal.confidence for item in queue]
    signal_stats = archive.signal_stats()
    imported = getattr(import_summary, "signals_saved", 0) if import_summary is not None else 0
    import_processed = getattr(import_summary, "files_processed", 0) if import_summary is not None else 0
    import_errors = getattr(import_summary, "files_failed", 0) if import_summary is not None else 0
    import_duplicates = getattr(import_summary, "duplicates", 0) if import_summary is not None else 0
    import_sources = getattr(import_summary, "sources_used", []) if import_summary is not None else []
    return {
        "signals_imported": imported,
        "signals_import_processed_files": import_processed,
        "signal_import_errors": import_errors,
        "signal_import_duplicates": import_duplicates,
        "signal_sources_used": import_sources,
        "signals_queued": len(queue),
        "generated_posts": len(posts),
        "posts_generated": len(posts),
        "brands_represented": len(by_brand),
        "platforms_used": len(by_platform),
        "average_confidence": round(sum(confidences) / max(len(confidences), 1), 3),
        "average_score": round(sum(scores) / max(len(scores), 1), 2),
        "average_content_score": round(sum(scores) / max(len(scores), 1), 2),
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "skipped_duplicates": skipped_duplicates,
        "by_platform": dict(by_platform),
        "by_brand": dict(by_brand),
        "archive": archive.stats(),
        "signals": signal_stats,
    }


def _summary_markdown(posts: list[GeneratedPost], stats: dict[str, object], current_date: date, queue: list[QueuedContent]) -> str:
    lines = [
        f"# Morning Content Summary - {current_date.isoformat()}",
        "",
        "## Signal Intake Summary",
        "",
        f"- Imported: {stats['signals_imported']}",
        f"- Duplicates: {stats['signal_import_duplicates']}",
        f"- Errors: {stats['signal_import_errors']}",
        f"- Processed files: {stats['signals_import_processed_files']}",
        f"- Sources used: {', '.join(stats['signal_sources_used']) if stats['signal_sources_used'] else 'none'}",
        "",
        "## Queued Content Summary",
        "",
    ]
    if not queue:
        lines.append("- No queued signals.")
    for item in queue:
        lines.append(
            f"- {item.scheduled_time} / {item.platform.title()} / {item.brand}: {item.signal.title} "
            f"({item.signal.source_project}, {item.signal.source_type}, confidence {round(item.signal.confidence * 100)}%, "
            f"priority {item.signal.priority}) - {item.reason}"
        )
    lines.extend(
        [
            "",
            "## Post Summary",
            "",
        ]
    )
    lines.extend(
        [
        f"Generated posts: {stats['generated_posts']}",
        f"Average quality score: {stats['average_score']}",
        "",
        "## Posts",
        "",
        ]
    )
    for post in posts:
        lines.append(f"- {post.brand} / {post.platform}: {post.content_type} ({post.score}/100)")
    return "\n".join(lines) + "\n"


def _preview_html(posts: list[GeneratedPost], stats: dict[str, object], current_date: date, queue: list[QueuedContent]) -> str:
    grouped: dict[str, list[GeneratedPost]] = defaultdict(list)
    for post in posts:
        grouped[post.platform].append(post)

    queue_by_signal = {item.signal.id: item for item in queue}
    signal_rows = []
    for item in queue:
        signal_rows.append(
            f"""
            <tr>
              <td>{html.escape(item.scheduled_time)}</td>
              <td>{html.escape(item.platform.title())}</td>
              <td>{html.escape(item.brand)}</td>
              <td>{html.escape(item.signal.source_project)}</td>
              <td>{html.escape(item.signal.title)}</td>
              <td>{round(item.signal.confidence * 100)}%</td>
              <td>{item.rank_score}/100</td>
              <td>{html.escape(item.reason)}</td>
              <td><a href="{html.escape(item.signal.url)}">link</a></td>
            </tr>
            """
        )

    sections = []
    for platform, platform_posts in grouped.items():
        cards = []
        for post in platform_posts:
            queue_item = queue_by_signal.get(post.variables.get("signal_id", ""))
            signal_meta = ""
            if queue_item is not None:
                signal_meta = (
                    f"<div class=\"detail\">Source: {html.escape(queue_item.signal.source_project)} | "
                    f"Confidence: {round(queue_item.signal.confidence * 100)}% | "
                    f"Reason: {html.escape(queue_item.reason)} | "
                    f"CTA: {html.escape(post.variables.get('cta', ''))}</div>"
                )
            cards.append(
                f"""
                <article class="card">
                  <div class="meta">{html.escape(post.brand)} | {html.escape(post.content_type)} | {post.score}/100</div>
                  {signal_meta}
                  <pre>{html.escape(post.content)}</pre>
                  <div class="detail">Hashtags: {html.escape(' '.join(post.hashtags))}</div>
                  <div class="template">{html.escape(post.template_used)}</div>
                </article>
                """
            )
        sections.append(f"<section><h2>{html.escape(platform.title())}</h2>{''.join(cards)}</section>")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Morning Content Preview {current_date.isoformat()}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; background: #f6f8fa; color: #172026; }}
    h1, h2 {{ margin-bottom: 8px; }}
    .stats {{ margin: 16px 0 28px; color: #495057; }}
    .card {{ background: white; border: 1px solid #d8dee4; border-radius: 8px; padding: 18px; margin: 14px 0; }}
    .meta {{ font-weight: 700; color: #0969da; margin-bottom: 12px; }}
    .detail {{ color: #495057; font-size: 13px; margin: 6px 0 12px; }}
    pre {{ white-space: pre-wrap; font-family: inherit; line-height: 1.45; }}
    .template {{ color: #6e7781; font-size: 12px; margin-top: 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; margin: 16px 0 28px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f6; }}
  </style>
</head>
<body>
  <h1>Morning Content Preview</h1>
  <div class="stats">{current_date.isoformat()} | {stats["generated_posts"]} posts | average score {stats["average_score"]}</div>
  <h2>Top Signals And Queue</h2>
  <table>
    <thead><tr><th>Time</th><th>Platform</th><th>Brand</th><th>Source</th><th>Signal</th><th>Confidence</th><th>Rank</th><th>Reason</th><th>Link</th></tr></thead>
    <tbody>{''.join(signal_rows)}</tbody>
  </table>
  {''.join(sections)}
</body>
</html>
"""


def _publishing_schedule(queue: list[QueuedContent]) -> str:
    lines = ["# Publishing Schedule", ""]
    if not queue:
        lines.append("No queued content for today.")
    for item in queue:
        lines.append(f"{item.scheduled_time} - {item.platform.title()} - {item.brand} - {item.signal.title} ({item.reason})")
    return "\n".join(lines) + "\n"
