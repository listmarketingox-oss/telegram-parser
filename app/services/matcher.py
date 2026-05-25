"""Keyword matching logic — pure function, covered by unit tests."""
import re
from datetime import datetime

from app.models.keyword import MatchType


def match_message(
    text: str,
    posted_at: datetime,
    keywords: list[dict],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[str]:
    """Check if message matches any keywords within the date range.

    Args:
        text: message text
        posted_at: when the message was posted
        keywords: list of dicts with keys: pattern, match_type, is_case_sensitive
        date_from: lower bound (inclusive), None = no limit
        date_to: upper bound (inclusive), None = no limit

    Returns:
        List of matched keyword patterns (empty = no match).
    """
    if date_from and posted_at < date_from:
        return []
    if date_to and posted_at > date_to:
        return []

    matched = []
    for kw in keywords:
        pattern = kw["pattern"]
        match_type = kw["match_type"]
        case_sensitive = kw.get("is_case_sensitive", False)

        if _check_keyword(text, pattern, match_type, case_sensitive):
            matched.append(pattern)

    return matched


def _check_keyword(
    text: str, pattern: str, match_type: str, case_sensitive: bool
) -> bool:
    if match_type == MatchType.substring:
        if case_sensitive:
            return pattern in text
        return pattern.lower() in text.lower()

    if match_type == MatchType.whole_word:
        flags = 0 if case_sensitive else re.IGNORECASE
        return bool(re.search(rf"\b{re.escape(pattern)}\b", text, flags))

    if match_type == MatchType.regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            return bool(re.search(pattern, text, flags))
        except re.error:
            return False

    return False
