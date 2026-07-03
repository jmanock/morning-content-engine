from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from content_engine.archive.store import ContentArchive
from content_engine.platform.pipeline import create_queue, run_morning
from content_engine.signals.importer import import_signals_from_inbox


ROOT = Path(__file__).resolve().parents[1]


class SignalWorkflowTests(unittest.TestCase):
    def test_import_signals_moves_files_and_saves_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            inbox = temp_path / "signals/inbox"
            processed = temp_path / "signals/processed"
            errors = temp_path / "signals/archive/errors"
            inbox.mkdir(parents=True)
            shutil.copy(ROOT / "examples/signals/florida_deals_sample.json", inbox / "florida.json")
            archive = ContentArchive(temp_path / "data/archive.sqlite3")

            summary = import_signals_from_inbox(inbox, processed, errors, archive)

            self.assertEqual(summary.files_processed, 1)
            self.assertEqual(summary.files_failed, 0)
            self.assertEqual(summary.signals_valid, 3)
            self.assertTrue((processed / "florida.json").exists())
            self.assertEqual(len(archive.recent_signals()), 3)

    def test_invalid_signal_moves_to_error_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            inbox = temp_path / "signals/inbox"
            processed = temp_path / "signals/processed"
            errors = temp_path / "signals/archive/errors"
            inbox.mkdir(parents=True)
            (inbox / "bad.json").write_text('{"title": "Missing required fields"}', encoding="utf-8")
            archive = ContentArchive(temp_path / "data/archive.sqlite3")

            summary = import_signals_from_inbox(inbox, processed, errors, archive)

            self.assertEqual(summary.files_failed, 1)
            self.assertTrue((errors / "bad.json").exists())

    def test_queue_uses_imported_signals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            _copy_runtime_files(temp_path)
            current = Path.cwd()
            try:
                os.chdir(temp_path)
                archive = ContentArchive(temp_path / "data/archive.sqlite3")
                archive.save_signals(import_signals_from_examples())
                queue, skipped = create_queue(date(2026, 7, 3), archive)
            finally:
                os.chdir(current)

            self.assertGreaterEqual(len(queue), 4)
            self.assertEqual(skipped, 0)
            self.assertTrue({item.platform for item in queue} & {"facebook", "instagram", "newsletter", "blog", "twitter", "linkedin"})

    def test_morning_pipeline_imports_signals_and_writes_v3_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            _copy_runtime_files(temp_path)
            inbox = temp_path / "signals/inbox"
            inbox.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / "examples/signals/florida_deals_sample.json", inbox / "florida.json")
            shutil.copy(ROOT / "examples/signals/offer_radar_sample.json", inbox / "offer.json")
            shutil.copy(ROOT / "examples/signals/bend_score_sample.json", inbox / "bend.json")
            current = Path.cwd()
            try:
                os.chdir(temp_path)
                report_dir = run_morning(today=date(2026, 7, 3))
                names = {path.name for path in report_dir.iterdir()}
            finally:
                os.chdir(current)

            self.assertIn("publishing_schedule.md", names)
            self.assertIn("preview.html", names)
            self.assertIn("statistics.json", names)
            self.assertIn("queue.json", names)


def import_signals_from_examples():
    from content_engine.models import Signal
    import json

    signals = []
    for path in sorted((ROOT / "examples/signals").glob("*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            item.setdefault("created_at", "2026-07-03T08:00:00+00:00")
            signals.append(Signal.from_dict(item))
    return signals


def _copy_runtime_files(temp_path: Path) -> None:
    shutil.copytree(ROOT / "config", temp_path / "config")
    shutil.copytree(ROOT / "templates", temp_path / "templates")
    shutil.copytree(ROOT / "examples", temp_path / "examples")
    (temp_path / "signals/inbox").mkdir(parents=True)


if __name__ == "__main__":
    unittest.main()

