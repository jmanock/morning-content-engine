from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


DEFAULT_QUEUE_CONFIG = Path("config/queue.yaml")


@dataclass(frozen=True)
class QueueConfig:
    max_posts_per_day: int = 10
    max_posts_per_brand: int = 4
    max_posts_per_platform: int = 4
    min_confidence: int = 60
    min_priority: int = 5
    allow_multiple_same_brand: bool = True
    allow_multiple_same_source_project: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "QueueConfig":
        return cls(
            max_posts_per_day=int(data.get("max_posts_per_day", cls.max_posts_per_day)),
            max_posts_per_brand=int(data.get("max_posts_per_brand", cls.max_posts_per_brand)),
            max_posts_per_platform=int(data.get("max_posts_per_platform", cls.max_posts_per_platform)),
            min_confidence=int(data.get("min_confidence", cls.min_confidence)),
            min_priority=int(data.get("min_priority", cls.min_priority)),
            allow_multiple_same_brand=bool(data.get("allow_multiple_same_brand", cls.allow_multiple_same_brand)),
            allow_multiple_same_source_project=bool(data.get("allow_multiple_same_source_project", cls.allow_multiple_same_source_project)),
        )


def load_queue_config(path: Path | str = DEFAULT_QUEUE_CONFIG) -> QueueConfig:
    config_path = Path(path)
    if not config_path.exists():
        return QueueConfig()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return QueueConfig.from_dict(data)

