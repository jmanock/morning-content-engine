# Morning Content Engine

Private Python terminal app for generating a daily social media content package for deal websites.

V1 is intentionally offline. It loads sample deal data, ranks the best offers, creates friendly Instagram and Facebook captions, writes a daily report, and renders simple placeholder images for manual review.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Commands

Generate today's package:

```bash
python3 main.py generate
```

Show the latest report path:

```bash
python3 main.py report
```

Preview top ranked deals:

```bash
python3 main.py top
```

Clear generated output:

```bash
python3 main.py clean
```

## Output

Generated files are written to:

```text
output/YYYY-MM-DD/
```

Each daily folder includes:

- `daily_report.md`
- `instagram_caption.txt`
- `facebook_caption.txt`
- `hashtags.txt`
- `selected_deals.json`
- `instagram_square.png`
- `facebook_post.png`
- `image_prompts.txt`

## Roadmap

- Replace sample data with private deal feeds.
- Add richer templates per website and category.
- Add optional image generation provider support.
- Add quality checks for expired or missing affiliate links.
- Add manual approval workflow.
- Later, explore posting integrations only after review workflows are solid.

