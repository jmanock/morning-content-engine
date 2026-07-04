from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from content_engine.archive.store import ContentArchive
from content_engine.models import Signal
from content_engine.platform.pipeline import create_queue
from content_engine.signals.importer import collect_signals_from_sources, import_signals_from_inbox
from content_engine.signals.schema import SignalValidationError, validate_signal_payload


ROOT = Path(__file__).resolve().parents[1]


class SignalV4Tests(unittest.TestCase):
    def test_schema_validation_normalizes_confidence_tags_and_created_at(self) -> None:
        payload = {
            "source_project": "florida-deals",
            "source_type": "deal",
            "brand": "Florida Deals",
            "title": "Orlando hotel deal under $150",
            "summary": "Strong hotel deal for Florida travelers",
            "url": "https://hoteldealsflorida.org",
            "category": "hotels",
            "priority": "8",
            "confidence": 90,
            "tags": "orlando, hotels",
            "metadata": {"price": 149},
        }
        signal = validate_signal_payload(payload)
        self.assertEqual(signal["confidence"], 0.9)
        self.assertEqual(signal["tags"], ["orlando", "hotels"])
        self.assertIn("created_at", signal)
        self.assertIn("id", signal)

    def test_schema_validation_returns_clear_errors(self) -> None:
        with self.assertRaises(SignalValidationError) as context:
            validate_signal_payload({"title": "Bad", "priority": 20, "confidence": 120, "metadata": []})
        message = str(context.exception)
        self.assertIn("source_project is required", message)
        self.assertIn("priority must be between 1 and 10", message)
        self.assertIn("confidence must be between 0 and 100", message)
        self.assertIn("metadata must be an object", message)

    def test_create_signal_helper_writes_inbox_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            outbox = Path(temp) / "inbox"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/create_signal.py"),
                    "--source-project",
                    "florida-deals",
                    "--source-type",
                    "deal",
                    "--brand",
                    "Florida Deals",
                    "--title",
                    "Orlando hotel deal under $150",
                    "--summary",
                    "Strong hotel deal for Florida travelers",
                    "--url",
                    "https://hoteldealsflorida.org",
                    "--category",
                    "hotels",
                    "--priority",
                    "8",
                    "--confidence",
                    "90",
                    "--outbox",
                    str(outbox),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            path = Path(result.stdout.strip())
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["confidence"], 0.9)

    def test_external_outbox_collection_copies_enabled_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            outbox = temp_path / "external/signals/outbox"
            outbox.mkdir(parents=True)
            shutil.copy(ROOT / "examples/signals/florida_deals_sample.json", outbox / "florida.json")
            config = temp_path / "signal_sources.yaml"
            config.write_text(
                f"sources:\n  - name: florida\n    path: \"{outbox}\"\n    enabled: true\n  - name: missing\n    path: \"{temp_path / 'missing'}\"\n    enabled: true\n",
                encoding="utf-8",
            )
            inbox = temp_path / "signals/inbox"
            summary = collect_signals_from_sources(config, inbox, ContentArchive(temp_path / "data/archive.sqlite3"))
            self.assertEqual(summary.files_copied, 1)
            self.assertEqual(summary.files_seen, 1)
            self.assertTrue(summary.warnings)
            self.assertTrue(list(inbox.glob("*.json")))

    def test_duplicate_signal_file_moves_to_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            inbox = temp_path / "signals/inbox"
            processed = temp_path / "signals/processed"
            errors = temp_path / "signals/archive/errors"
            duplicates = temp_path / "signals/archive/duplicates"
            inbox.mkdir(parents=True)
            source = ROOT / "examples/signals/offer_radar_sample.json"
            archive = ContentArchive(temp_path / "data/archive.sqlite3")
            shutil.copy(source, inbox / "offer.json")
            import_signals_from_inbox(inbox, processed, errors, archive, duplicates)
            shutil.copy(source, inbox / "offer.json")
            summary = import_signals_from_inbox(inbox, processed, errors, archive, duplicates)
            self.assertEqual(summary.files_duplicates, 1)
            self.assertTrue((duplicates / "offer.json").exists())

    def test_invalid_signal_archiving(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            inbox = temp_path / "signals/inbox"
            inbox.mkdir(parents=True)
            (inbox / "bad.json").write_text('{"title": "Bad"}', encoding="utf-8")
            errors = temp_path / "signals/archive/errors"
            summary = import_signals_from_inbox(
                inbox,
                temp_path / "signals/processed",
                errors,
                ContentArchive(temp_path / "data/archive.sqlite3"),
                temp_path / "signals/archive/duplicates",
            )
            self.assertEqual(summary.files_failed, 1)
            self.assertTrue((errors / "bad.json").exists())

    def test_signal_filtering_and_queue_reason_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            _copy_runtime_files(temp_path)
            current = Path.cwd()
            try:
                os.chdir(temp_path)
                archive = ContentArchive(temp_path / "data/archive.sqlite3")
                archive.save_signals(_signals_from_examples())
                florida = archive.recent_signals(brand_filter="florida-deals")
                high = archive.recent_signals(high_priority=True)
                queue, _ = create_queue(date(2026, 7, 3), archive)
            finally:
                os.chdir(current)
            self.assertTrue(florida)
            self.assertTrue(all(signal.brand == "Florida Deals" for signal in florida))
            self.assertTrue(all(signal.priority >= 8 for signal in high))
            self.assertTrue(all(item.reason for item in queue))


def _signals_from_examples() -> list[Signal]:
    signals: list[Signal] = []
    for path in sorted((ROOT / "examples/signals").glob("*.json")):
        for item in json.loads(path.read_text(encoding="utf-8")):
            signals.append(Signal.from_dict(item))
    return signals


def _copy_runtime_files(temp_path: Path) -> None:
    shutil.copytree(ROOT / "config", temp_path / "config")
    shutil.copytree(ROOT / "templates", temp_path / "templates")
    shutil.copytree(ROOT / "examples", temp_path / "examples")
    (temp_path / "signals/inbox").mkdir(parents=True)


if __name__ == "__main__":
    unittest.main()

