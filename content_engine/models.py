from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class Deal:
    id: str
    site: str
    category: str
    title: str
    short_title: str
    description: str
    price: float
    original_price: float
    savings_percent: int
    destination_or_brand: str
    deal_url: str
    affiliate_url: str
    image_prompt: str
    expiration: str
    priority: int
    source: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Deal":
        return cls(
            id=str(data["id"]),
            site=str(data["site"]),
            category=str(data["category"]),
            title=str(data["title"]),
            short_title=str(data["short_title"]),
            description=str(data["description"]),
            price=float(data["price"]),
            original_price=float(data["original_price"]),
            savings_percent=int(data["savings_percent"]),
            destination_or_brand=str(data["destination_or_brand"]),
            deal_url=str(data["deal_url"]),
            affiliate_url=str(data["affiliate_url"]),
            image_prompt=str(data["image_prompt"]),
            expiration=str(data["expiration"]),
            priority=int(data["priority"]),
            source=str(data["source"]),
        )

    @property
    def savings_amount(self) -> float:
        return max(0.0, self.original_price - self.price)

    @property
    def expiration_date(self) -> date | None:
        try:
            return datetime.strptime(self.expiration, "%Y-%m-%d").date()
        except ValueError:
            return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "site": self.site,
            "category": self.category,
            "title": self.title,
            "short_title": self.short_title,
            "description": self.description,
            "price": self.price,
            "original_price": self.original_price,
            "savings_percent": self.savings_percent,
            "destination_or_brand": self.destination_or_brand,
            "deal_url": self.deal_url,
            "affiliate_url": self.affiliate_url,
            "image_prompt": self.image_prompt,
            "expiration": self.expiration,
            "priority": self.priority,
            "source": self.source,
        }


@dataclass(frozen=True)
class RankedDeal:
    deal: Deal
    score: int
    reasons: list[str]
    suggested_platform: str

    def to_dict(self) -> dict[str, Any]:
        payload = self.deal.to_dict()
        payload["score"] = self.score
        payload["reasons"] = self.reasons
        payload["suggested_platform"] = self.suggested_platform
        return payload


@dataclass(frozen=True)
class BrandProfile:
    slug: str
    name: str
    description: str
    tone: str
    emoji_style: str
    hashtags: list[str]
    social_platforms: list[str]
    website: str
    logo_path: str
    affiliate_disclosure: str
    posting_schedule: dict[str, Any]

    @classmethod
    def from_dict(cls, slug: str, data: dict[str, Any]) -> "BrandProfile":
        return cls(
            slug=slug,
            name=str(data["name"]),
            description=str(data.get("description", "")),
            tone=str(data.get("tone", "Friendly and useful.")),
            emoji_style=str(data.get("emoji_style", "light")),
            hashtags=list(data.get("hashtags", [])),
            social_platforms=list(data.get("social_platforms", [])),
            website=str(data.get("website", "")),
            logo_path=str(data.get("logo_path", "")),
            affiliate_disclosure=str(data.get("affiliate_disclosure", "")),
            posting_schedule=dict(data.get("posting_schedule", {})),
        )


@dataclass(frozen=True)
class GeneratedPost:
    date: str
    brand: str
    brand_slug: str
    platform: str
    content_type: str
    content: str
    hashtags: list[str]
    score: int
    score_reasons: list[str]
    template_used: str
    variables: dict[str, str]

    def archive_key(self) -> str:
        return self.content.strip().lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "brand": self.brand,
            "brand_slug": self.brand_slug,
            "platform": self.platform,
            "content_type": self.content_type,
            "content": self.content,
            "hashtags": self.hashtags,
            "score": self.score,
            "score_reasons": self.score_reasons,
            "template_used": self.template_used,
            "variables": self.variables,
        }
