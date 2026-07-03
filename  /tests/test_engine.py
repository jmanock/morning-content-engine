from __future__ import annotations

from datetime import date

from content_engine.engine import generate
from content_engine.ranking.scorer import rank_deals, select_top_deals
from content_engine.reports.writer import ensure_daily_output_dir, write_daily_report
from content_engine.social.captions import generate_facebook_caption, generate_instagram_caption
from content_engine.social.hashtags import format_hashtags, generate_hashtags
from content_engine.sources.sample_loader import load_sample_deals


def test_load_sample_deals() -> None:
    deals = load_sample_deals()
    assert len(deals) >= 10
    assert {deal.category for deal in deals} >= {"flight", "hotel", "cruise", "local", "finance"}


def test_rank_deals_scores_between_zero_and_one_hundred() -> None:
    ranked = rank_deals(load_sample_deals(), today=date(2026, 7, 3))
    assert ranked
    assert all(0 <= item.score <= 100 for item in ranked)
    assert ranked[0].score >= ranked[-1].score


def test_generate_captions() -> None:
    selected = select_top_deals(load_sample_deals(), today=date(2026, 7, 3))
    instagram = generate_instagram_caption(selected)
    facebook = generate_facebook_caption(selected)
    assert "Check today's Florida deals" in instagram
    assert "See the full list on the site" in facebook


def test_create_output_folder(tmp_path) -> None:
    output_dir = ensure_daily_output_dir(tmp_path, today=date(2026, 7, 3))
    assert output_dir.exists()
    assert output_dir.name == "2026-07-03"


def test_generate_report(tmp_path) -> None:
    selected = select_top_deals(load_sample_deals(), today=date(2026, 7, 3))
    hashtags = format_hashtags(generate_hashtags(selected))
    report_path = write_daily_report(
        selected,
        date(2026, 7, 3),
        generate_instagram_caption(selected),
        generate_facebook_caption(selected),
        hashtags,
        tmp_path,
    )
    report = report_path.read_text(encoding="utf-8")
    assert "Morning Content Report" in report
    assert "Top 5 Deals" in report
    assert "Manual Posting Notes" in report


def test_generate_full_package(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    from pathlib import Path
    import shutil

    source_examples = Path(__file__).resolve().parents[1] / "examples"
    shutil.copytree(source_examples, tmp_path / "examples")
    output_dir = generate(today=date(2026, 7, 3))
    expected = {
        "daily_report.md",
        "instagram_caption.txt",
        "facebook_caption.txt",
        "hashtags.txt",
        "selected_deals.json",
        "instagram_square.png",
        "facebook_post.png",
        "image_prompts.txt",
    }
    assert expected <= {path.name for path in output_dir.iterdir()}

