from __future__ import annotations

from pathlib import Path

import yaml

from content_engine.models import BrandProfile


DEFAULT_BRANDS_DIR = Path("config/brands")


def load_brands(config_dir: Path | str = DEFAULT_BRANDS_DIR) -> list[BrandProfile]:
    path = Path(config_dir)
    if not path.exists():
        return []

    brands: list[BrandProfile] = []
    for yaml_path in sorted(path.glob("*.yaml")) + sorted(path.glob("*.yml")):
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        brands.append(BrandProfile.from_dict(yaml_path.stem, data))
    return brands

