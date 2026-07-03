from __future__ import annotations

from content_engine.models import RankedDeal


BASE_TAGS = [
    "#FloridaDeals",
    "#TravelDeals",
    "#OrlandoDeals",
    "#CruiseDeals",
    "#HotelDeals",
    "#FlightDeals",
    "#MoneyDeals",
]

CATEGORY_TAGS = {
    "flight": ["#CheapFlights", "#FloridaTravel", "#WeekendGetaway", "#VacationDeals"],
    "hotel": ["#HotelDeals", "#BeachVacation", "#StaycationDeals", "#FloridaHotels"],
    "cruise": ["#CruiseDeals", "#PortCanaveral", "#CaribbeanCruise", "#FamilyTravel"],
    "local": ["#LocalDeals", "#ThingsToDoInFlorida", "#OrlandoLife", "#FloridaFun"],
    "finance": ["#CreditCardOffers", "#CashBack", "#FinanceDeals", "#SmartMoney"],
}


def generate_hashtags(selected: list[RankedDeal], limit: int = 22) -> list[str]:
    tags: list[str] = []
    for tag in BASE_TAGS:
        _append_unique(tags, tag)
    for ranked in selected:
        for tag in CATEGORY_TAGS.get(ranked.deal.category.lower(), []):
            _append_unique(tags, tag)
        location = ranked.deal.destination_or_brand.replace(" ", "")
        if location:
            _append_unique(tags, f"#{location}Deals")
    fallback = [
        "#DealAlert",
        "#DailyDeals",
        "#FloridaVacation",
        "#SaveMoney",
        "#DealFinder",
        "#BudgetTravel",
        "#SunshineState",
        "#FamilyDeals",
    ]
    for tag in fallback:
        _append_unique(tags, tag)
    return tags[:limit]


def format_hashtags(tags: list[str]) -> str:
    return " ".join(tags)


def _append_unique(tags: list[str], tag: str) -> None:
    clean = "".join(character for character in tag if character.isalnum() or character == "#")
    if clean and clean not in tags:
        tags.append(clean)

