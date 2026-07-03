from __future__ import annotations

import html
import json
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from content_engine.archive.store import ContentArchive
from content_engine.config.brands import load_brands
from content_engine.models import BrandProfile, GeneratedPost, RankedDeal
from content_engine.quality.scorer import score_content
from content_engine.ranking.scorer import rank_deals
from content_engine.sources.sample_loader import load_sample_deals
from content_engine.templates.renderer import TemplateCatalog, render_template


PLATFORMS = ["instagram", "facebook", "linkedin", "twitter", "newsletter"]
EMOJIS = {"none": "", "minimal": "*", "light": "*", "expressive": "*"}


def run_morning(today: date | None = None) -> Path:
    current_date = today or date.today()
    brands = load_brands()
    archive = ContentArchive()
    posts = generate_posts(brands, current_date, archive)
    archive.save_posts(posts)
    return save_reports(posts, current_date, archive)


def generate_posts(
    brands: list[BrandProfile],
    current_date: date,
    archive: ContentArchive | None = None,
) -> list[GeneratedPost]:
    archive = archive or ContentArchive()
    catalog = TemplateCatalog()
    existing = archive.existing_content_keys()
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


def save_reports(posts: list[GeneratedPost], current_date: date, archive: ContentArchive | None = None) -> Path:
    archive = archive or ContentArchive()
    report_dir = Path("reports") / current_date.isoformat()
    report_dir.mkdir(parents=True, exist_ok=True)

    for platform in PLATFORMS:
        _write_platform_report(
            report_dir / f"{platform}.md",
            platform,
            [post for post in posts if post.platform == platform],
        )

    stats = _statistics(posts, archive)
    (report_dir / "summary.md").write_text(_summary_markdown(posts, stats, current_date), encoding="utf-8")
    (report_dir / "preview.html").write_text(_preview_html(posts, stats, current_date), encoding="utf-8")
    (report_dir / "statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    (report_dir / "posts.json").write_text(json.dumps([post.to_dict() for post in posts], indent=2), encoding="utf-8")
    return report_dir


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


def _statistics(posts: list[GeneratedPost], archive: ContentArchive) -> dict[str, object]:
    by_platform = Counter(post.platform for post in posts)
    by_brand = Counter(post.brand for post in posts)
    scores = [post.score for post in posts]
    return {
        "generated_posts": len(posts),
        "average_score": round(sum(scores) / max(len(scores), 1), 2),
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "by_platform": dict(by_platform),
        "by_brand": dict(by_brand),
        "archive": archive.stats(),
    }


def _summary_markdown(posts: list[GeneratedPost], stats: dict[str, object], current_date: date) -> str:
    lines = [
        f"# Morning Content Summary - {current_date.isoformat()}",
        "",
        f"Generated posts: {stats['generated_posts']}",
        f"Average quality score: {stats['average_score']}",
        "",
        "## Posts",
        "",
    ]
    for post in posts:
        lines.append(f"- {post.brand} / {post.platform}: {post.content_type} ({post.score}/100)")
    return "\n".join(lines) + "\n"


def _preview_html(posts: list[GeneratedPost], stats: dict[str, object], current_date: date) -> str:
    grouped: dict[str, list[GeneratedPost]] = defaultdict(list)
    for post in posts:
        grouped[post.platform].append(post)

    sections = []
    for platform, platform_posts in grouped.items():
        cards = []
        for post in platform_posts:
            cards.append(
                f"""
                <article class="card">
                  <div class="meta">{html.escape(post.brand)} | {html.escape(post.content_type)} | {post.score}/100</div>
                  <pre>{html.escape(post.content)}</pre>
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
    pre {{ white-space: pre-wrap; font-family: inherit; line-height: 1.45; }}
    .template {{ color: #6e7781; font-size: 12px; margin-top: 12px; }}
  </style>
</head>
<body>
  <h1>Morning Content Preview</h1>
  <div class="stats">{current_date.isoformat()} | {stats["generated_posts"]} posts | average score {stats["average_score"]}</div>
  {''.join(sections)}
</body>
</html>
"""
