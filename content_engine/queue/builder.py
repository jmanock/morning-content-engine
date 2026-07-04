from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime

from content_engine.config.brands import load_brands
from content_engine.config.queue import QueueConfig, load_queue_config
from content_engine.models import BrandProfile, QueuedContent, Signal


PLATFORM_ORDER = ["facebook", "instagram", "newsletter", "blog", "twitter", "linkedin"]
SCHEDULE_TIMES = [
    "8:00 AM",
    "8:15 AM",
    "9:00 AM",
    "10:00 AM",
    "10:30 AM",
    "11:00 AM",
    "11:30 AM",
    "12:00 PM",
    "12:30 PM",
    "1:00 PM",
]
CONTENT_TYPE_BY_SOURCE = {
    "flight_deal": "deal_post",
    "hotel_deal": "deal_post",
    "cruise_deal": "deal_post",
    "local_event": "weekend_roundup",
    "credit_card_offer": "affiliate_highlight",
    "travel_points_offer": "affiliate_highlight",
    "business_opportunity": "business_opportunity",
    "traffic_spike": "market_signal",
    "website_milestone": "newsletter_teaser",
    "affiliate_approval": "affiliate_highlight",
    "opportunity": "business_opportunity",
    "github_no_homepage_opportunity": "github_opportunity",
    "github_stale_popular_repo": "github_opportunity",
    "github_fast_growth_candidate": "github_opportunity",
}


@dataclass(frozen=True)
class QueueBuildStats:
    total_signals_considered: int = 0
    total_queued: int = 0
    skipped_duplicates: int = 0
    skipped_low_confidence: int = 0
    skipped_low_priority: int = 0
    skipped_platform_limits: int = 0
    skipped_brand_limits: int = 0
    skipped_source_limits: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total_signals_considered": self.total_signals_considered,
            "total_queued": self.total_queued,
            "skipped_duplicates": self.skipped_duplicates,
            "skipped_low_confidence": self.skipped_low_confidence,
            "skipped_low_priority": self.skipped_low_priority,
            "skipped_platform_limits": self.skipped_platform_limits,
            "skipped_brand_limits": self.skipped_brand_limits,
            "skipped_source_limits": self.skipped_source_limits,
        }


def build_daily_queue(
    signals: list[Signal],
    queue_date: date,
    duplicate_keys: set[str] | None = None,
    max_items: int | None = None,
    brand_filter: str | None = None,
    source_filter: str | None = None,
    config: QueueConfig | None = None,
    return_stats: bool = False,
) -> tuple[list[QueuedContent], int] | tuple[list[QueuedContent], QueueBuildStats]:
    duplicate_keys = duplicate_keys or set()
    config = config or load_queue_config()
    max_posts = max_items or config.max_posts_per_day
    brands = {brand.name: brand for brand in load_brands()}
    filtered_signals = _filter_signals(signals, brand_filter, source_filter)
    ranked = sorted(
        ((_rank_signal(signal, duplicate_keys, brands.get(signal.brand)), signal) for signal in filtered_signals),
        key=lambda item: item[0],
        reverse=True,
    )

    queue: list[QueuedContent] = []
    seen_titles: set[str] = set()
    brand_counts: Counter[str] = Counter()
    platform_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    skipped_duplicates = 0
    skipped_low_confidence = 0
    skipped_low_priority = 0
    skipped_platform_limits = 0
    skipped_brand_limits = 0
    skipped_source_limits = 0

    for rank_score, signal in ranked:
        normalized_title = signal.title.strip().lower()
        confidence = round(signal.confidence * 100)
        if _is_duplicate(signal, normalized_title, duplicate_keys, seen_titles):
            skipped_duplicates += 1
            continue
        if confidence < config.min_confidence:
            skipped_low_confidence += 1
            continue
        if signal.priority < config.min_priority:
            skipped_low_priority += 1
            continue
        if not config.allow_multiple_same_brand and brand_counts[signal.brand] > 0:
            skipped_brand_limits += 1
            continue
        if brand_counts[signal.brand] >= config.max_posts_per_brand:
            skipped_brand_limits += 1
            continue
        if not config.allow_multiple_same_source_project and source_counts[signal.source_project] > 0:
            skipped_source_limits += 1
            continue

        brand = brands.get(signal.brand)
        platform = _platform_for(signal, brand, platform_counts, config)
        if platform is None:
            skipped_platform_limits += 1
            continue

        content_type = content_type_for(signal)
        queue.append(
            QueuedContent(
                date=queue_date.isoformat(),
                signal=signal,
                brand=signal.brand,
                platform=platform,
                content_type=content_type,
                rank_score=max(0, min(100, round(rank_score))),
                scheduled_time=SCHEDULE_TIMES[len(queue) % len(SCHEDULE_TIMES)],
                duplicate_risk=_duplicate_risk(signal, duplicate_keys),
                reason=_queue_reason(signal, rank_score, platform, brand, duplicate_keys, content_type),
            )
        )
        seen_titles.add(normalized_title)
        brand_counts[signal.brand] += 1
        platform_counts[platform] += 1
        source_counts[signal.source_project] += 1
        category_counts[signal.category] += 1
        if len(queue) >= max_posts:
            break

    stats = QueueBuildStats(
        total_signals_considered=len(filtered_signals),
        total_queued=len(queue),
        skipped_duplicates=skipped_duplicates,
        skipped_low_confidence=skipped_low_confidence,
        skipped_low_priority=skipped_low_priority,
        skipped_platform_limits=skipped_platform_limits,
        skipped_brand_limits=skipped_brand_limits,
        skipped_source_limits=skipped_source_limits,
    )
    return (queue, stats) if return_stats else (queue, skipped_duplicates)


def content_type_for(signal: Signal) -> str:
    source_type = signal.source_type.lower()
    category = signal.category.lower()
    title = signal.title.lower()
    if "github" in source_type or "github" in title:
        return "github_opportunity"
    if "saas" in category or "saas" in title:
        return "saas_opportunity"
    if "market" in category or "traffic" in source_type:
        return "market_signal"
    if source_type in CONTENT_TYPE_BY_SOURCE:
        return CONTENT_TYPE_BY_SOURCE[source_type]
    if "business" in category or "opportunity" in category:
        return "business_opportunity"
    if "finance" in category or "credit" in source_type:
        return "affiliate_highlight"
    return "deal_post"


def _filter_signals(signals: list[Signal], brand_filter: str | None, source_filter: str | None) -> list[Signal]:
    filtered = signals
    if brand_filter:
        target = _normalize_filter(brand_filter)
        filtered = [signal for signal in filtered if _normalize_filter(signal.brand) == target]
    if source_filter:
        target = _normalize_filter(source_filter)
        filtered = [signal for signal in filtered if _normalize_filter(signal.source_project) == target]
    return filtered


def _rank_signal(signal: Signal, duplicate_keys: set[str], brand: BrandProfile | None) -> float:
    score = signal.priority * 8 + signal.confidence * 30
    score += _expiration_score(signal)
    score += _category_diversity_bonus(signal)
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


def _platform_for(
    signal: Signal,
    brand: BrandProfile | None,
    platform_counts: Counter[str],
    config: QueueConfig,
) -> str | None:
    preferred = _preferred_platforms(signal)
    allowed = set(brand.social_platforms if brand else PLATFORM_ORDER)
    allowed.add("blog")
    options = [platform for platform in preferred if platform in allowed]
    options.extend(platform for platform in PLATFORM_ORDER if platform in allowed and platform not in options)
    for platform in sorted(options, key=lambda item: (platform_counts[item], options.index(item))):
        if platform_counts[platform] < config.max_posts_per_platform:
            return platform
    return None


def _preferred_platforms(signal: Signal) -> list[str]:
    source = _normalize_filter(signal.source_project)
    category = signal.category.lower()
    source_type = signal.source_type.lower()
    tags = " ".join(signal.tags).lower()
    if source == "bend-score" or "business" in category or "opportunity" in category:
        return ["linkedin", "twitter", "newsletter", "blog"]
    if source == "florida-deals" or "travel" in category or "deal" in source_type or "flight" in tags or "hotel" in tags:
        return ["facebook", "instagram", "newsletter", "twitter"]
    if source == "offer-radar" or "finance" in category or "credit" in source_type:
        return ["facebook", "newsletter", "twitter", "linkedin"]
    return ["facebook", "newsletter", "twitter", "linkedin", "instagram"]


def _brand_schedule_fit(signal: Signal, brand: BrandProfile) -> bool:
    content_types = brand.posting_schedule.get("morning", {}).get("content_types", [])
    expected = content_type_for(signal)
    return not content_types or expected in content_types


def _is_duplicate(signal: Signal, normalized_title: str, duplicate_keys: set[str], seen_titles: set[str]) -> bool:
    return (
        signal.id in duplicate_keys
        or signal.url.strip().lower() in duplicate_keys
        or normalized_title in duplicate_keys
        or normalized_title in seen_titles
    )


def _duplicate_risk(signal: Signal, duplicate_keys: set[str]) -> str:
    if signal.id in duplicate_keys:
        return "high"
    if signal.url.strip().lower() in duplicate_keys:
        return "medium"
    if signal.title.strip().lower() in duplicate_keys:
        return "medium"
    return "low"


def _queue_reason(
    signal: Signal,
    rank_score: float,
    platform: str,
    brand: BrandProfile | None,
    duplicate_keys: set[str],
    content_type: str,
) -> str:
    parts = [
        f"priority {signal.priority}/10",
        f"confidence {round(signal.confidence * 100)}%",
        f"rank {max(0, min(100, round(rank_score)))}/100",
        f"{content_type.replace('_', ' ')} template",
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


def _category_diversity_bonus(signal: Signal) -> int:
    category = signal.category.lower()
    if any(term in category for term in ["business", "finance", "travel", "hotel", "flight", "cruise"]):
        return 4
    return 0


def _normalize_filter(value: str) -> str:
    return value.lower().replace("_", "-").replace(" ", "-")
