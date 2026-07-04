from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from content_engine.signals.schema import SignalValidationError, validate_signal_payload  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a Morning Content Engine signal JSON file.")
    parser.add_argument("--source-project", required=True)
    parser.add_argument("--source-type", required=True)
    parser.add_argument("--brand", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--url", default="")
    parser.add_argument("--category", required=True)
    parser.add_argument("--priority", required=True, type=int)
    parser.add_argument("--confidence", required=True, type=float)
    parser.add_argument("--description", default="")
    parser.add_argument("--affiliate-url", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--expiration", default="")
    parser.add_argument("--image-prompt", default="")
    parser.add_argument("--metadata", default="{}")
    parser.add_argument("--outbox", default="signals/inbox")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        metadata = json.loads(args.metadata)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid --metadata JSON: {exc}") from exc

    payload = {
        "source_project": args.source_project,
        "source_type": args.source_type,
        "brand": args.brand,
        "title": args.title,
        "summary": args.summary,
        "description": args.description,
        "url": args.url,
        "affiliate_url": args.affiliate_url,
        "category": args.category,
        "priority": args.priority,
        "confidence": args.confidence,
        "tags": args.tags,
        "expiration": args.expiration,
        "image_prompt": args.image_prompt,
        "metadata": metadata,
    }

    try:
        signal = validate_signal_payload(payload)
    except SignalValidationError as exc:
        raise SystemExit(f"Invalid signal: {exc}") from exc

    output_dir = (ROOT / args.outbox).resolve() if not Path(args.outbox).is_absolute() else Path(args.outbox)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_source = signal["source_project"].lower().replace(" ", "-").replace("_", "-")
    path = output_dir / f"{timestamp}-{safe_source}-{signal['id'][:40]}.json"
    path.write_text(json.dumps(signal, indent=2) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()

