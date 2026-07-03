from __future__ import annotations

import re


CTA_PATTERNS = ["check", "see the full list", "read more", "visit", "compare"]
EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAFF]")


def score_content(content: str, platform: str, hashtags: list[str], prior_contents: set[str] | None = None) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    words = content.split()
    char_count = len(content)
    lower = content.lower()

    if _length_ok(char_count, platform):
        score += 20
        reasons.append("Length fits the platform.")
    else:
        reasons.append("Length may need platform-specific trimming.")

    avg_word_length = sum(len(word.strip(".,!?;:")) for word in words) / max(len(words), 1)
    if avg_word_length <= 7 and len(words) >= 8:
        score += 15
        reasons.append("Readable wording.")
    else:
        reasons.append("Readability could be simpler.")

    if any(pattern in lower for pattern in CTA_PATTERNS):
        score += 15
        reasons.append("CTA present.")
    else:
        reasons.append("CTA missing or too subtle.")

    if _hashtags_ok(platform, hashtags):
        score += 15
        reasons.append("Hashtags fit the platform.")
    else:
        reasons.append("Hashtag count may not fit the platform.")

    emoji_count = len(EMOJI_PATTERN.findall(content))
    if platform in {"linkedin", "newsletter"}:
        if emoji_count <= 1:
            score += 10
            reasons.append("Emoji use is restrained.")
    elif emoji_count <= 4:
        score += 10
        reasons.append("Emoji use fits social copy.")

    previous = prior_contents or set()
    if content.strip().lower() not in previous:
        score += 15
        reasons.append("Unique compared with archive.")
    else:
        reasons.append("Duplicate content found in archive.")

    if _platform_suitable(content, platform):
        score += 10
        reasons.append("Platform suitability looks good.")
    else:
        reasons.append("Platform suitability could be improved.")

    return min(100, score), reasons


def _length_ok(char_count: int, platform: str) -> bool:
    ranges = {
        "instagram": (80, 1200),
        "facebook": (80, 1400),
        "linkedin": (120, 1300),
        "twitter": (40, 280),
        "newsletter": (80, 2200),
    }
    low, high = ranges.get(platform, (60, 1200))
    return low <= char_count <= high


def _hashtags_ok(platform: str, hashtags: list[str]) -> bool:
    count = len(hashtags)
    if platform == "newsletter":
        return count <= 5
    if platform == "linkedin":
        return 2 <= count <= 6
    if platform == "twitter":
        return 1 <= count <= 4
    return 5 <= count <= 25


def _platform_suitable(content: str, platform: str) -> bool:
    if platform == "twitter":
        return len(content) <= 280
    if platform == "linkedin":
        return "\n" in content and len(content.split()) >= 18
    return len(content.split()) >= 10

