from __future__ import annotations

import random
import re
from pathlib import Path


TOKEN_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


class TemplateCatalog:
    def __init__(self, root: Path | str = "templates") -> None:
        self.root = Path(root)

    def variations_for(self, content_type: str) -> list[Path]:
        folder = self.root / content_type
        if not folder.exists():
            return []
        return sorted(folder.glob("*.txt"))

    def choose(self, content_type: str, seed: str, used_templates: set[str] | None = None) -> Path:
        variations = self.variations_for(content_type)
        if not variations:
            raise ValueError(f"No templates found for content type: {content_type}")

        used = used_templates or set()
        available = [path for path in variations if str(path) not in used] or variations
        rng = random.Random(seed)
        return rng.choice(available)


def render_template(path: Path, variables: dict[str, str]) -> str:
    template = path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        return str(variables.get(match.group(1), ""))

    rendered = TOKEN_PATTERN.sub(replace, template)
    lines = [line.rstrip() for line in rendered.splitlines()]
    return "\n".join(lines).strip()

