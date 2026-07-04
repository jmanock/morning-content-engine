from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from content_engine.archive.store import ContentArchive
from content_engine.models import Signal
from content_engine.signals.schema import SignalValidationError, validate_signal_payload


INBOX_DIR = Path("signals/inbox")
PROCESSED_DIR = Path("signals/processed")
ERROR_DIR = Path("signals/archive/errors")
DUPLICATE_DIR = Path("signals/archive/duplicates")
SOURCE_CONFIG = Path("config/signal_sources.yaml")


@dataclass(frozen=True)
class SignalImportSummary:
    files_seen: int
    files_processed: int
    files_failed: int
    files_duplicates: int
    signals_valid: int
    signals_saved: int
    duplicates: int
    sources_used: list[str]
    errors: list[str]

    def lines(self) -> list[str]:
        lines = [
            f"Files seen: {self.files_seen}",
            f"Files processed: {self.files_processed}",
            f"Files failed: {self.files_failed}",
            f"Duplicate files: {self.files_duplicates}",
            f"Valid signals: {self.signals_valid}",
            f"New signals saved: {self.signals_saved}",
            f"Duplicate signals: {self.duplicates}",
            f"Sources used: {', '.join(self.sources_used) if self.sources_used else 'none'}",
        ]
        lines.extend([f"Error: {error}" for error in self.errors])
        return lines


@dataclass(frozen=True)
class CollectSummary:
    sources_seen: int
    sources_enabled: int
    files_seen: int
    files_copied: int
    duplicates: int
    warnings: list[str]

    def lines(self) -> list[str]:
        lines = [
            f"Sources seen: {self.sources_seen}",
            f"Sources enabled: {self.sources_enabled}",
            f"Files seen: {self.files_seen}",
            f"Files copied: {self.files_copied}",
            f"Duplicates skipped: {self.duplicates}",
        ]
        lines.extend([f"Warning: {warning}" for warning in self.warnings])
        return lines


def import_signals_from_inbox(
    inbox_dir: Path | str = INBOX_DIR,
    processed_dir: Path | str = PROCESSED_DIR,
    error_dir: Path | str = ERROR_DIR,
    archive: ContentArchive | None = None,
    duplicate_dir: Path | str = DUPLICATE_DIR,
) -> SignalImportSummary:
    inbox = Path(inbox_dir)
    processed = Path(processed_dir)
    errors = Path(error_dir)
    duplicates_dir = Path(duplicate_dir)
    processed.mkdir(parents=True, exist_ok=True)
    errors.mkdir(parents=True, exist_ok=True)
    duplicates_dir.mkdir(parents=True, exist_ok=True)
    archive = archive or ContentArchive()

    json_files = sorted(inbox.glob("*.json"))
    files_processed = 0
    files_failed = 0
    files_duplicates = 0
    signals_valid = 0
    signals_saved = 0
    duplicate_signals = 0
    sources_used: set[str] = set()
    error_messages: list[str] = []

    for path in json_files:
        try:
            signals = _load_signal_file(path)
        except Exception as exc:
            error_messages.append(f"{path.name}: {exc}")
            _move_file(path, errors / path.name)
            files_failed += 1
            continue

        existing_ids = archive.existing_signal_ids()
        new_signals = [signal for signal in signals if signal.id not in existing_ids]
        duplicate_count = len(signals) - len(new_signals)
        duplicate_signals += duplicate_count
        signals_valid += len(signals)
        sources_used.update(signal.source_project for signal in new_signals)
        saved = archive.save_signals(new_signals)
        signals_saved += saved

        if new_signals:
            _move_file(path, processed / path.name)
            files_processed += 1
        else:
            _move_file(path, duplicates_dir / path.name)
            files_duplicates += 1

    return SignalImportSummary(
        files_seen=len(json_files),
        files_processed=files_processed,
        files_failed=files_failed,
        files_duplicates=files_duplicates,
        signals_valid=signals_valid,
        signals_saved=signals_saved,
        duplicates=duplicate_signals,
        sources_used=sorted(sources_used),
        errors=error_messages,
    )


def collect_signals_from_sources(
    config_path: Path | str = SOURCE_CONFIG,
    inbox_dir: Path | str = INBOX_DIR,
    archive: ContentArchive | None = None,
) -> CollectSummary:
    path = Path(config_path)
    inbox = Path(inbox_dir)
    inbox.mkdir(parents=True, exist_ok=True)
    archive = archive or ContentArchive()
    warnings: list[str] = []
    if not path.exists():
        return CollectSummary(0, 0, 0, 0, 0, [f"{path} not found"])

    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = list(config.get("sources", []))
    enabled = [source for source in sources if source.get("enabled")]
    copied = 0
    duplicates = 0
    files_seen = 0
    known_ids = archive.existing_signal_ids()

    for source in enabled:
        source_name = str(source.get("name", "unknown"))
        source_path = Path(str(source.get("path", ""))).expanduser()
        if not source_path.is_absolute():
            source_path = (Path.cwd() / source_path).resolve()
        if not source_path.exists():
            warnings.append(f"{source_name}: {source_path} does not exist")
            continue
        for signal_file in sorted(source_path.glob("*.json")):
            files_seen += 1
            try:
                signals = _load_signal_file(signal_file)
            except Exception as exc:
                warnings.append(f"{source_name}/{signal_file.name}: invalid signal file ({exc})")
                continue
            signal_ids = {signal.id for signal in signals}
            destination = inbox / f"{source_name}-{signal_file.name}"
            if signal_ids <= known_ids or destination.exists():
                duplicates += 1
                continue
            shutil.copy2(signal_file, destination)
            known_ids.update(signal_ids)
            copied += 1

    return CollectSummary(
        sources_seen=len(sources),
        sources_enabled=len(enabled),
        files_seen=files_seen,
        files_copied=copied,
        duplicates=duplicates,
        warnings=warnings,
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
        try:
            signals.append(Signal.from_dict(validate_signal_payload(enriched)))
        except SignalValidationError:
            raise
    return signals


def _move_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination = destination.with_name(f"{destination.stem}-{datetime.now().strftime('%H%M%S')}{destination.suffix}")
    shutil.move(str(source), str(destination))
