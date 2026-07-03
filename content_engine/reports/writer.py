from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from content_engine.models import RankedDeal


def ensure_daily_output_dir(base_dir: Path | str = "output", today: date | None = None) -> Path:
    current_date = today or date.today()
    output_dir = Path(base_dir) / current_date.isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_selected_deals(selected: list[RankedDeal], output_dir: Path) -> Path:
    path = output_dir / "selected_deals.json"
    path.write_text(json.dumps([item.to_dict() for item in selected], indent=2), encoding="utf-8")
    return path


def write_text_packages(instagram_caption: str, facebook_caption: str, hashtags: str, output_dir: Path) -> dict[str, Path]:
    paths = {
        "instagram_caption": output_dir / "instagram_caption.txt",
        "facebook_caption": output_dir / "facebook_caption.txt",
        "hashtags": output_dir / "hashtags.txt",
    }
    paths["instagram_caption"].write_text(instagram_caption + "\n", encoding="utf-8")
    paths["facebook_caption"].write_text(facebook_caption + "\n", encoding="utf-8")
    paths["hashtags"].write_text(hashtags + "\n", encoding="utf-8")
    return paths


def write_daily_report(
    selected: list[RankedDeal],
    report_date: date,
    instagram_caption: str,
    facebook_caption: str,
    hashtags: str,
    output_dir: Path,
) -> Path:
    path = output_dir / "daily_report.md"
    lines = [
        f"# Morning Content Report - {report_date.isoformat()}",
        "",
        "## Top 5 Deals",
        "",
    ]
    for index, ranked in enumerate(selected, start=1):
        deal = ranked.deal
        lines.extend(
            [
                f"### {index}. {deal.title}",
                "",
                f"- Site: {deal.site}",
                f"- Category: {deal.category}",
                f"- Price: ${deal.price:,.0f} (was ${deal.original_price:,.0f})",
                f"- Savings: ${deal.savings_amount:,.0f} / {deal.savings_percent}%",
                f"- Score: {ranked.score}/100",
                f"- Expiration: {deal.expiration}",
                f"- Suggested platform: {ranked.suggested_platform}",
                f"- Deal link: {deal.deal_url}",
                f"- Affiliate link: {deal.affiliate_url}",
                "",
                "Why selected:",
            ]
        )
        lines.extend([f"- {reason}" for reason in ranked.reasons])
        lines.extend(["", f"Notes: Use the placeholder image as a review draft. Verify live price and availability before posting.", ""])

    lines.extend(
        [
            "## Instagram Caption",
            "",
            instagram_caption,
            "",
            "## Facebook Caption",
            "",
            facebook_caption,
            "",
            "## Hashtags",
            "",
            hashtags,
            "",
            "## Manual Posting Notes",
            "",
            "- Review each affiliate link before publishing.",
            "- Confirm pricing and expiration dates on the live deal page.",
            "- Use `instagram_square.png` for Instagram feed review.",
            "- Use `facebook_post.png` for Facebook feed review.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

