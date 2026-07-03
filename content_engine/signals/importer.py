from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from content_engine.archive.store import ContentArchive
from content_engine.models import Signal


INBOX_DIR = Path("signals/inbox")
PROCESSED_DIR = Path("signals/processed")
ERROR_DIR = Path("signals/archive/errors")


@dataclass(frozen=True)
class SignalImportSummary:
    files_seen: int
    files_processed: int
    files_failed: int
    signals_valid: int
    signals_saved: int
    errors: list[str]

    def lines(self) -> list[str]:
        lines = [
            f"Files seen: {self.files_seen}",
            f"Files processed: {self.files_processed}",
            f"Files failed: {self.files_failed}",
            f"Valid signals: {self.signals_valid}",
            f"New signals saved: {self.signals_saved}",
        ]
        lines.extend([f"Error: {error}" for error in self.errors])
        return lines


def import_signals_from_inbox(
    inbox_dir: Path | str = INBOX_DIR,
    processed_dir: Path | str = PROCESSED_DIR,
    error_dir: Path | str = ERROR_DIR,
    archive: ContentArchive | None = None,
) -> SignalImportSummary:
    inbox = Path(inbox_dir)
    processed = Path(processed_dir)
    errors = Path(error_dir)
    processed.mkdir(parents=True, exist_ok=True)
    errors.mkdir(parents=True, exist_ok=True)
    archive = archive or ContentArchive()

    json_files = sorted(inbox.glob("*.json"))
    files_processed = 0
    files_failed = 0
    valid_signals: list[Signal] = []
    error_messages: list[str] = []

    for path in json_files:
        try:
            signals = _load_signal_file(path)
            valid_signals.extend(signals)
            _move_file(path, processed / path.name)
            files_processed += 1
        except Exception as exc:
            error_messages.append(f"{path.name}: {exc}")
            _move_file(path, errors / path.name)
            files_failed += 1

    saved = archive.save_signals(valid_signals)
    return SignalImportSummary(
        files_seen=len(json_files),
        files_processed=files_processed,
        files_failed=files_failed,
        signals_valid=len(valid_signals),
        signals_saved=saved,
        errors=error_messages,
    )


def _load_signal_file(path: Path) -> list[Signal]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict[str, Any]]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("signals"), list):
        items = payload["signals"]
    elif isinstance(payload, dict):
        items = [payload]
    else:
        raise ValueError("JSON must be an object, an array, or an object with a signals array")

    now = datetime.now(timezone.utc).isoformat()
    signals = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Signal entries must be JSON objects")
        enriched = dict(item)
        enriched.setdefault("created_at", now)
        signals.append(Signal.from_dict(enriched))
    return signals


def _move_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination = destination.with_name(f"{destination.stem}-{datetime.now().strftime('%H%M%S')}{destination.suffix}")
    shutil.move(str(source), str(destination))

