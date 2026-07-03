from __future__ import annotations

import json
from pathlib import Path

from content_engine.models import Deal


DEFAULT_SAMPLE_PATH = Path("examples/sample_deals.json")


def load_sample_deals(path: Path | str = DEFAULT_SAMPLE_PATH) -> list[Deal]:
    sample_path = Path(path)
    with sample_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return [Deal.from_dict(item) for item in data]

