from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


REQUIRED_FIELDS = [
    "source_project",
    "source_type",
    "brand",
    "title",
    "summary",
    "category",
    "priority",
    "confidence",
]

OPTIONAL_FIELDS = [
    "description",
    "url",
    "affiliate_url",
    "tags",
    "expiration",
    "image_prompt",
    "metadata",
    "created_at",
    "id",
]


class SignalValidationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def validate_signal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    normalized = dict(payload)

    for field in REQUIRED_FIELDS:
        if field not in normalized or normalized[field] in (None, ""):
            errors.append(f"{field} is required")

    priority = _coerce_int(normalized.get("priority"), "priority", errors)
    if priority is not None and not 1 <= priority <= 10:
        errors.append("priority must be between 1 and 10")

    confidence = _coerce_float(normalized.get("confidence"), "confidence", errors)
    if confidence is not None:
        if not 0 <= confidence <= 100:
            errors.append("confidence must be between 0 and 100")
        elif confidence > 1:
            confidence = confidence / 100

    url = str(normalized.get("url", "") or "").strip()
    affiliate_url = str(normalized.get("affiliate_url", "") or "").strip()
    if url and not _valid_url(url):
        errors.append("url must be a valid http(s) URL when present")
    if affiliate_url and not _valid_url(affiliate_url):
        errors.append("affiliate_url must be a valid http(s) URL when present")

    metadata = normalized.get("metadata", {})
    if metadata in (None, ""):
        metadata = {}
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")

    if errors:
        raise SignalValidationError(errors)

    normalized["priority"] = int(priority or 1)
    normalized["confidence"] = float(confidence or 0)
    normalized["url"] = url
    normalized["affiliate_url"] = affiliate_url
    normalized["description"] = str(normalized.get("description", "") or normalized.get("summary", ""))
    normalized["tags"] = _normalize_tags(normalized.get("tags", []))
    normalized["metadata"] = metadata
    normalized["expiration"] = str(normalized.get("expiration", "") or "")
    normalized["image_prompt"] = str(normalized.get("image_prompt", "") or "")
    normalized["created_at"] = str(normalized.get("created_at", "") or datetime.now(timezone.utc).isoformat())
    normalized["id"] = str(normalized.get("id", "") or _make_signal_id(normalized))
    return normalized


def _coerce_int(value: Any, field: str, errors: list[str]) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(f"{field} must be an integer")
        return None


def _coerce_float(value: Any, field: str, errors: list[str]) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append(f"{field} must be a number")
        return None


def _valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_tags(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [tag.strip() for tag in value.split(",") if tag.strip()]
    if isinstance(value, list | tuple | set):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    return [str(value).strip()]


def _make_signal_id(payload: dict[str, Any]) -> str:
    raw = f"{payload.get('source_project', 'signal')}-{payload.get('title', 'untitled')}-{payload.get('created_at', '')}"
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return slug[:96] or "signal"
