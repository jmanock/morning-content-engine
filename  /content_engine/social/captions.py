from __future__ import annotations

from content_engine.models import RankedDeal


def generate_instagram_caption(selected: list[RankedDeal]) -> str:
    lead = selected[0].deal if selected else None
    if lead is None:
        return "Fresh deals are coming soon. Check today's Florida deals."

    lines = [
        f"Morning deal check: {lead.short_title} is standing out today.",
        f"I found {len(selected)} solid offers worth a look, from travel finds to everyday savings.",
        "",
    ]
    for ranked in selected[:5]:
        deal = ranked.deal
        lines.append(f"- {deal.short_title}: ${deal.price:,.0f} ({deal.savings_percent}% off)")
    lines.extend(["", "Check today's Florida deals."])
    return "\n".join(lines)


def generate_facebook_caption(selected: list[RankedDeal]) -> str:
    if not selected:
        return "Today's deal list is being updated. See the full list on the site."

    top = selected[0].deal
    lines = [
        f"Today's deal list has a strong one up top: {top.short_title}.",
        "I pulled together the best finds across flights, hotels, cruises, local offers, and money deals.",
        "",
    ]
    for ranked in selected[:5]:
        deal = ranked.deal
        lines.append(f"- {deal.short_title} - ${deal.price:,.0f}, usually ${deal.original_price:,.0f}")
    lines.extend(["", "See the full list on the site."])
    return "\n".join(lines)

