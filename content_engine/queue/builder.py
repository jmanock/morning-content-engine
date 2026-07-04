from __future__ import annotations

from datetime import date, datetime

from content_engine.config.brands import load_brands
from content_engine.models import BrandProfile, QueuedContent, Signal


PLATFORM_ORDER = ["facebook", "instagram", "newsletter", "blog", "twitter", "linkedin"]
SCHEDULE_TIMES = ["8:00 AM", "8:15 AM", "9:00 AM", "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM", "12:00 PM"]
CONTENT_TYPE_BY_SOURCE = {
    "flight_deal": "deal_post",
    "hotel_deal": "deal_post",
    "cruise_deal": "deal_post",
    "local_event": "weekend_roundup",
    "credit_card_offer": "affiliate_highlight",
    "travel_points_offer": "affiliate_highlight",
    "business_opportunity": "trending",
    "traffic_spike": "did_you_know",
    "website_milestone": "newsletter_teaser",
    "affiliate_approval": "affiliate_highlight",
}


def build_daily_queue(
    signals: list[Signal],
    queue_date: date,
    duplicate_keys: set[str] | None = None,
    max_items: int = 8,
) -> tuple[list[QueuedContent], int]:
    duplicate_keys = duplicate_keys or set()
    brands = {brand.name: brand for brand in load_brands()}
    ranked = sorted(
        ((_rank_signal(signal, duplicate_keys, brands.get(signal.brand)), signal) for signal in signals),
        key=lambda item: item[0],
        reverse=True,
    )

    queue: list[QueuedContent] = []
    seen_titles: set[str] = set()
    skipped_duplicates = 0
    for rank_score, signal in ranked:
        normalized_title = signal.title.strip().lower()
        if signal.id in duplicate_keys or signal.url.strip().lower() in duplicate_keys or normalized_title in seen_titles:
            skipped_duplicates += 1
            continue
        if rank_score < 35:
            skipped_duplicates += 1
            continue
        platform = _platform_for(signal, brands.get(signal.brand), len(queue))
        brand = brands.get(signal.brand)
        queue.append(
            QueuedContent(
                date=queue_date.isoformat(),
                signal=signal,
                brand=signal.brand,
                platform=platform,
                content_type=CONTENT_TYPE_BY_SOURCE.get(signal.source_type, "deal_post"),
                rank_score=max(0, min(100, round(rank_score))),
                scheduled_time=SCHEDULE_TIMES[len(queue) % len(SCHEDULE_TIMES)],
                duplicate_risk=_duplicate_risk(signal, duplicate_keys),
                reason=_queue_reason(signal, rank_score, platform, brand, duplicate_keys),
            )
        )
        seen_titles.add(normalized_title)
        if len(queue) >= max_items:
            break
    return queue, skipped_duplicates


def _rank_signal(signal: Signal, duplicate_keys: set[str], brand: BrandProfile | None) -> float:
    score = signal.priority * 8 + signal.confidence * 30
    score += _expiration_score(signal)
    if brand is not None:
        score += 8
        if _brand_schedule_fit(signal, brand):
            score += 5
        if signal.category.lower() in " ".join(brand.hashtags).lower():
            score += 4
    if signal.id in duplicate_keys:
        score -= 80
    if signal.url.strip().lower() in duplicate_keys:
        score -= 50
    if signal.title.strip().lower() in duplicate_keys:
        score -= 40
    return score


def _expiration_score(signal: Signal) -> float:
    if not signal.expiration:
        return 5
    try:
        expiration = datetime.strptime(signal.expiration, "%Y-%m-%d").date()
    except ValueError:
        return 0
    days_left = (expiration - date.today()).days
    if days_left < 0:
        return -30
    if days_left <= 2:
        return 15
    if days_left <= 7:
        return 12
    if days_left <= 14:
        return 8
    return 4


def _platform_for(signal: Signal, brand: BrandProfile | None, index: int) -> str:
    if signal.category == "business":
        preferred = ["blog", "linkedin", "newsletter", "twitter"]
    elif signal.category == "finance":
        preferred = ["facebook", "linkedin", "newsletter", "twitter"]
    else:
        preferred = ["facebook", "instagram", "newsletter", "twitter"]

    allowed = set(brand.social_platforms if brand else PLATFORM_ORDER)
    allowed.add("blog")
    options = [platform for platform in preferred if platform in allowed] or list(allowed)
    return options[index % len(options)]


def _brand_schedule_fit(signal: Signal, brand: BrandProfile) -> bool:
    content_types = brand.posting_schedule.get("morning", {}).get("content_types", [])
    expected = CONTENT_TYPE_BY_SOURCE.get(signal.source_type, "deal_post")
    return not content_types or expected in content_types


def _duplicate_risk(signal: Signal, duplicate_keys: set[str]) -> str:
    if signal.id in duplicate_keys:
        return "high"
    if signal.url.strip().lower() in duplicate_keys:
        return "medium"
    if signal.title.strip().lower() in duplicate_keys:
        return "medium"
    return "low"


def _queue_reason(signal: Signal, rank_score: float, platform: str, brand: BrandProfile | None, duplicate_keys: set[str]) -> str:
    parts = [
        f"priority {signal.priority}/10",
        f"confidence {round(signal.confidence * 100)}%",
        f"rank {max(0, min(100, round(rank_score)))}/100",
    ]
    expiration = _expiration_score(signal)
    if expiration >= 12:
        parts.append("expires soon")
    if brand is not None:
        parts.append("brand match")
        if platform in set(brand.social_platforms) | {"blog"}:
            parts.append(f"{platform} fit")
        if _brand_schedule_fit(signal, brand):
            parts.append("schedule fit")
    if _duplicate_risk(signal, duplicate_keys) == "low":
        parts.append("unused recently")
    return "; ".join(parts)
