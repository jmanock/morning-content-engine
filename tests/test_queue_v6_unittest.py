from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from content_engine.archive.store import ContentArchive
from content_engine.config.brands import load_brands
from content_engine.config.queue import QueueConfig
from content_engine.models import Signal
from content_engine.platform.pipeline import generate_posts
from content_engine.queue.builder import build_daily_queue, content_type_for


ROOT = Path(__file__).resolve().parents[1]


class QueueV6Tests(unittest.TestCase):
    def test_queue_limit(self) -> None:
        with _runtime_dir() as temp_path:
            queue, stats = build_daily_queue(
                _signals(),
                date(2026, 7, 4),
                config=QueueConfig(max_posts_per_day=3),
                return_stats=True,
            )
        self.assertEqual(len(queue), 3)
        self.assertEqual(stats.total_queued, 3)

    def test_brand_limit(self) -> None:
        with _runtime_dir() as temp_path:
            queue, stats = build_daily_queue(
                _signals(extra_bend=4),
                date(2026, 7, 4),
                config=QueueConfig(max_posts_per_day=10, max_posts_per_brand=1),
                return_stats=True,
            )
        brand_counts = {}
        for item in queue:
            brand_counts[item.brand] = brand_counts.get(item.brand, 0) + 1
        self.assertTrue(all(count <= 1 for count in brand_counts.values()))
        self.assertGreater(stats.skipped_brand_limits, 0)

    def test_platform_assignment(self) -> None:
        with _runtime_dir():
            queue, _ = build_daily_queue(_signals(), date(2026, 7, 4), return_stats=True)
        by_brand = {item.brand: item.platform for item in queue}
        self.assertIn(by_brand["Bend Score"], {"linkedin", "twitter", "newsletter", "blog"})
        self.assertIn(by_brand["Florida Deals"], {"facebook", "instagram", "newsletter"})
        self.assertIn(by_brand["Offer Radar"], {"facebook", "newsletter", "twitter", "linkedin"})

    def test_bend_score_template_generation(self) -> None:
        with _runtime_dir() as temp_path:
            archive = ContentArchive(temp_path / "data/archive.sqlite3")
            signal = _bend_signal("bend-saas", "SaaS automation opportunity", category="business-opportunity")
            queue, _ = build_daily_queue([signal], date(2026, 7, 4), return_stats=True)
            posts = generate_posts(load_brands(), date(2026, 7, 4), archive, queue=queue)
        self.assertEqual(content_type_for(signal), "saas_opportunity")
        self.assertIn("Bend Score", posts[0].content)
        self.assertIn("SaaS opportunity", posts[0].content)

    def test_mixed_source_queue_generation(self) -> None:
        with _runtime_dir():
            queue, _ = build_daily_queue(_signals(extra_bend=2), date(2026, 7, 4), return_stats=True)
        brands = {item.brand for item in queue}
        categories = {item.signal.category for item in queue}
        self.assertTrue({"Florida Deals", "Offer Radar", "Bend Score"} <= brands)
        self.assertTrue({"travel", "finance", "business-opportunity"} & categories)

    def test_low_confidence_filtering(self) -> None:
        low = _signal(
            id="low-confidence",
            brand="Florida Deals",
            source_project="Florida Deals",
            source_type="flight_deal",
            title="Low confidence flight deal",
            category="travel",
            confidence=45,
            priority=9,
        )
        with _runtime_dir():
            queue, stats = build_daily_queue(
                [low],
                date(2026, 7, 4),
                config=QueueConfig(min_confidence=60),
                return_stats=True,
            )
        self.assertEqual(queue, [])
        self.assertEqual(stats.skipped_low_confidence, 1)


def _signals(extra_bend: int = 0) -> list[Signal]:
    signals = [
        _signal(
            id="florida-flight",
            brand="Florida Deals",
            source_project="Florida Deals",
            source_type="flight_deal",
            title="Orlando to NYC flights under $150",
            category="travel",
            confidence=91,
            priority=9,
            tags=["flight", "travel"],
        ),
        _signal(
            id="offer-cashback",
            brand="Offer Radar",
            source_project="Offer Radar",
            source_type="credit_card_offer",
            title="$200 cash bonus card offer",
            category="finance",
            confidence=90,
            priority=9,
            tags=["finance", "credit"],
        ),
        _bend_signal("bend-business", "Bend Score found SaaS automation upside"),
    ]
    for index in range(extra_bend):
        signals.append(_bend_signal(f"bend-extra-{index}", f"Bend Score business opportunity {index}"))
    return signals


def _bend_signal(id: str, title: str, category: str = "business-opportunity") -> Signal:
    return _signal(
        id=id,
        brand="Bend Score",
        source_project="bend-score",
        source_type="opportunity",
        title=title,
        category=category,
        confidence=85,
        priority=8,
        tags=["bend-score", "saas", "opportunity"],
    )


def _signal(
    id: str,
    brand: str,
    source_project: str,
    source_type: str,
    title: str,
    category: str,
    confidence: int,
    priority: int,
    tags: list[str] | None = None,
) -> Signal:
    return Signal.from_dict(
        {
            "id": id,
            "source_project": source_project,
            "source_type": source_type,
            "brand": brand,
            "title": title,
            "summary": f"Useful signal for {brand}.",
            "description": f"Longer description for {title}.",
            "url": f"https://example.com/{id}",
            "category": category,
            "tags": tags or [],
            "priority": priority,
            "confidence": confidence,
            "metadata": {},
            "created_at": "2026-07-04T08:00:00+00:00",
        }
    )


class _runtime_dir:
    def __enter__(self) -> Path:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        shutil.copytree(ROOT / "config", self.path / "config")
        shutil.copytree(ROOT / "templates", self.path / "templates")
        self.current = Path.cwd()
        os.chdir(self.path)
        return self.path

    def __exit__(self, *_args) -> None:
        os.chdir(self.current)
        self.temp.cleanup()


if __name__ == "__main__":
    unittest.main()

