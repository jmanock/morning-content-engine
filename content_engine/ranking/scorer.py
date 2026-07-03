from __future__ import annotations

from datetime import date

from content_engine.models import Deal, RankedDeal


CATEGORY_AFFILIATE_POTENTIAL = {
    "cruise": 10,
    "hotel": 9,
    "finance": 9,
    "flight": 8,
    "local": 6,
}

CATEGORY_BROAD_APPEAL = {
    "flight": 10,
    "hotel": 9,
    "cruise": 8,
    "local": 7,
    "finance": 8,
}

CATEGORY_SEASONAL_RELEVANCE = {
    "cruise": 9,
    "hotel": 9,
    "flight": 8,
    "local": 8,
    "finance": 6,
}


def rank_deals(deals: list[Deal], today: date | None = None) -> list[RankedDeal]:
    current_date = today or date.today()
    ranked = [score_deal(deal, current_date) for deal in deals]
    return sorted(ranked, key=lambda item: item.score, reverse=True)


def score_deal(deal: Deal, today: date) -> RankedDeal:
    category = deal.category.lower()
    urgency = _urgency_score(deal, today)
    savings_amount_score = min(deal.savings_amount / 600 * 100, 100)
    savings_percent_score = min(deal.savings_percent, 80) / 80 * 100
    affiliate_score = CATEGORY_AFFILIATE_POTENTIAL.get(category, 6) * 10
    broad_appeal_score = CATEGORY_BROAD_APPEAL.get(category, 6) * 10
    seasonal_score = CATEGORY_SEASONAL_RELEVANCE.get(category, 6) * 10
    site_priority_score = min(max(deal.priority, 1), 10) * 10
    content_quality_score = _content_quality_score(deal)

    weighted = (
        savings_amount_score * 0.18
        + savings_percent_score * 0.18
        + urgency * 0.13
        + affiliate_score * 0.13
        + broad_appeal_score * 0.12
        + seasonal_score * 0.10
        + site_priority_score * 0.10
        + content_quality_score * 0.06
    )

    score = max(0, min(100, round(weighted)))
    return RankedDeal(
        deal=deal,
        score=score,
        reasons=_selection_reasons(
            deal,
            score,
            urgency,
            savings_amount_score,
            savings_percent_score,
            affiliate_score,
            broad_appeal_score,
            seasonal_score,
        ),
        suggested_platform=_suggest_platform(category),
    )


def select_top_deals(deals: list[Deal], limit: int = 5, today: date | None = None) -> list[RankedDeal]:
    return rank_deals(deals, today=today)[:limit]


def _urgency_score(deal: Deal, today: date) -> float:
    expiration = deal.expiration_date
    if expiration is None:
        return 50
    days_left = (expiration - today).days
    if days_left < 0:
        return 0
    if days_left <= 1:
        return 100
    if days_left <= 3:
        return 85
    if days_left <= 7:
        return 70
    if days_left <= 14:
        return 50
    return 30


def _content_quality_score(deal: Deal) -> float:
    score = 50
    if len(deal.short_title) <= 45:
        score += 15
    if 60 <= len(deal.description) <= 220:
        score += 15
    if deal.image_prompt:
        score += 10
    if deal.price < deal.original_price and deal.savings_percent > 0:
        score += 10
    return min(score, 100)


def _selection_reasons(
    deal: Deal,
    score: int,
    urgency: float,
    savings_amount_score: float,
    savings_percent_score: float,
    affiliate_score: float,
    broad_appeal_score: float,
    seasonal_score: float,
) -> list[str]:
    reasons = [f"Overall score: {score}/100."]
    if savings_amount_score >= 60:
        reasons.append(f"Strong dollar savings of ${deal.savings_amount:,.0f}.")
    if savings_percent_score >= 50:
        reasons.append(f"Clear value story at {deal.savings_percent}% off.")
    if urgency >= 70:
        reasons.append(f"Timely offer expiring on {deal.expiration}.")
    if affiliate_score >= 80:
        reasons.append("High affiliate potential for this category.")
    if broad_appeal_score >= 80:
        reasons.append("Broad audience appeal for Florida deal followers.")
    if seasonal_score >= 80:
        reasons.append("Good seasonal fit for a morning deal roundup.")
    return reasons


def _suggest_platform(category: str) -> str:
    if category in {"flight", "hotel", "cruise", "local"}:
        return "Instagram and Facebook"
    if category == "finance":
        return "Facebook"
    return "Instagram"

