from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from content_engine.archive.store import ContentArchive
from content_engine.config.brands import load_brands
from content_engine.models import GeneratedPost
from content_engine.platform.pipeline import generate_posts, run_morning
from content_engine.quality.scorer import score_content
from content_engine.templates.renderer import render_template


ROOT = Path(__file__).resolve().parents[1]


class PlatformTests(unittest.TestCase):
    def test_loads_all_brand_yaml_files(self) -> None:
        brands = load_brands(ROOT / "config/brands")
        self.assertGreaterEqual(len(brands), 2)
        self.assertIn("Florida Deals", {brand.name for brand in brands})
        self.assertIn("Offer Radar", {brand.name for brand in brands})

    def test_template_renderer_replaces_variables(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "template.txt"
            path.write_text("Hello {{name}}, see {{thing}}.", encoding="utf-8")
            rendered = render_template(path, {"name": "Florida", "thing": "today's deals"})
        self.assertEqual(rendered, "Hello Florida, see today's deals.")

    def test_quality_score_returns_reasons(self) -> None:
        score, reasons = score_content(
            "Check today's Florida deals and compare the full list before booking.",
            "facebook",
            ["#FloridaDeals", "#TravelDeals", "#HotelDeals", "#FlightDeals", "#CruiseDeals"],
            set(),
        )
        self.assertGreater(score, 50)
        self.assertTrue(reasons)

    def test_archive_does_not_save_identical_content_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = ContentArchive(Path(temp) / "archive.sqlite3")
            post = GeneratedPost(
                date="2026-07-03",
                brand="Florida Deals",
                brand_slug="florida_deals",
                platform="facebook",
                content_type="deal_post",
                content="Check today's Florida deals.",
                hashtags=["#FloridaDeals"],
                score=80,
                score_reasons=["CTA present."],
                template_used="templates/deal_post/variation_1.txt",
                variables={},
            )
            self.assertEqual(archive.save_posts([post]), 1)
            self.assertEqual(archive.save_posts([post]), 0)

    def test_generates_posts_for_configured_brands(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            shutil.copytree(ROOT / "config", temp_path / "config")
            shutil.copytree(ROOT / "templates", temp_path / "templates")
            shutil.copytree(ROOT / "examples", temp_path / "examples")
            current = Path.cwd()
            try:
                os.chdir(temp_path)
                archive = ContentArchive(temp_path / "data/archive.sqlite3")
                posts = generate_posts(load_brands(), date(2026, 7, 3), archive)
            finally:
                os.chdir(current)
        self.assertGreaterEqual(len(posts), 8)
        self.assertTrue(all(post.score >= 0 for post in posts))

    def test_morning_pipeline_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            shutil.copytree(ROOT / "config", temp_path / "config")
            shutil.copytree(ROOT / "templates", temp_path / "templates")
            shutil.copytree(ROOT / "examples", temp_path / "examples")
            current = Path.cwd()
            try:
                os.chdir(temp_path)
                report_dir = run_morning(today=date(2026, 7, 3))
                expected = {
                    "instagram.md",
                    "facebook.md",
                    "linkedin.md",
                    "twitter.md",
                    "newsletter.md",
                    "summary.md",
                    "preview.html",
                    "statistics.json",
                }
                self.assertTrue(expected <= {path.name for path in report_dir.iterdir()})
            finally:
                os.chdir(current)

    def test_repeated_generation_avoids_identical_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            shutil.copytree(ROOT / "config", temp_path / "config")
            shutil.copytree(ROOT / "templates", temp_path / "templates")
            shutil.copytree(ROOT / "examples", temp_path / "examples")
            current = Path.cwd()
            try:
                os.chdir(temp_path)
                archive = ContentArchive(temp_path / "data/archive.sqlite3")
                brands = load_brands()
                first = generate_posts(brands, date(2026, 7, 3), archive)
                archive.save_posts(first)
                second = generate_posts(brands, date(2026, 7, 3), archive)
            finally:
                os.chdir(current)
        first_content = {post.archive_key() for post in first}
        second_content = {post.archive_key() for post in second}
        self.assertFalse(first_content & second_content)


if __name__ == "__main__":
    unittest.main()
