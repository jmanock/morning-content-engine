# Signal Contract

A signal is an important thing worth turning into content. Any project can export a JSON signal into an outbox folder, and Morning Content Engine can collect, validate, queue, and transform it into reviewable content.

## Required Fields

- `source_project`: Project or system that produced the signal.
- `source_type`: Signal type, such as `flight_deal`, `credit_card_offer`, `business_opportunity`, `website_milestone`, or `affiliate_alert`.
- `brand`: Brand that should publish or review the content.
- `title`: Short human-readable headline.
- `summary`: One or two sentence summary.
- `url`: Recommended destination URL. The validator allows this to be blank for internal milestones, but it must be valid `http` or `https` when present.
- `category`: Broad content category.
- `priority`: Integer from `1` to `10`.
- `confidence`: Number from `0` to `100`. Values like `90` are preferred; legacy fractional values like `0.9` are accepted and normalized.

## Optional Fields

- `description`: Longer details. Defaults to `summary`.
- `affiliate_url`: Affiliate or tracking link. Must be valid `http` or `https` when present.
- `tags`: List or comma-separated string.
- `expiration`: Date in `YYYY-MM-DD` format when useful.
- `image_prompt`: Future image generation prompt.
- `metadata`: Object for project-specific details.
- `created_at`: ISO timestamp. Added automatically if missing.
- `id`: Stable id. Added automatically if missing.

## Florida Deals Example

```json
{
  "source_project": "Florida Deals",
  "source_type": "hotel_deal",
  "brand": "Florida Deals",
  "title": "Orlando hotel deal under $150",
  "summary": "Strong hotel deal for Florida travelers with family-friendly dates.",
  "url": "https://hoteldealsflorida.org/orlando-under-150",
  "category": "hotels",
  "priority": 8,
  "confidence": 90,
  "tags": ["orlando", "hotels", "florida"]
}
```

## Offer Radar Example

```json
{
  "source_project": "Offer Radar",
  "source_type": "credit_card_offer",
  "brand": "Offer Radar",
  "title": "$200 cash bonus card offer",
  "summary": "Cash back welcome offer after qualifying spend.",
  "url": "https://example.com/offer-radar/cash-bonus",
  "affiliate_url": "https://example.com/go/offer-radar/cash-bonus",
  "category": "finance",
  "priority": 9,
  "confidence": 92,
  "metadata": {"bonus_value": 200}
}
```

## Bend Score Example

```json
{
  "source_project": "Bend Score",
  "source_type": "business_opportunity",
  "brand": "Bend Score",
  "title": "Retail corridor shows improving local demand",
  "summary": "Local activity suggests a possible business opportunity report.",
  "url": "https://example.com/bend-score/retail-corridor",
  "category": "business",
  "priority": 8,
  "confidence": 84,
  "metadata": {"market": "Bend", "score_delta": 12}
}
```

## Website Milestone Example

```json
{
  "source_project": "Florida Deals",
  "source_type": "website_milestone",
  "brand": "Florida Deals",
  "title": "Florida Deals crossed 10,000 monthly visitors",
  "summary": "The site reached a traffic milestone that may be worth a newsletter note.",
  "url": "https://example.com/florida-deals",
  "category": "milestone",
  "priority": 6,
  "confidence": 95,
  "metadata": {"monthly_visitors": 10000}
}
```

## Affiliate Alert Example

```json
{
  "source_project": "Offer Radar",
  "source_type": "affiliate_alert",
  "brand": "Offer Radar",
  "title": "New affiliate approval for travel rewards offers",
  "summary": "A new partner approval can support future comparison content.",
  "url": "https://example.com/offer-radar",
  "category": "affiliate",
  "priority": 7,
  "confidence": 88,
  "metadata": {"partner": "Travel Rewards Network"}
}
```

## Lifecycle

Files collected or created locally enter:

```text
signals/inbox/
```

When imported:

- Valid new signals move to `signals/processed/`.
- Invalid files move to `signals/archive/errors/`.
- Duplicate-only files move to `signals/archive/duplicates/`.

External projects should write signals to their own `signals/outbox/` folder. Morning Content Engine reads enabled outboxes from `config/signal_sources.yaml` with:

```bash
python main.py collect-signals
```

