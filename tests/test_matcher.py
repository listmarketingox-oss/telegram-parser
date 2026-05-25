from datetime import datetime, timezone

import pytest

from app.services.matcher import match_message


@pytest.fixture
def keywords():
    return [
        {"pattern": "маркетинг", "match_type": "substring", "is_case_sensitive": False},
        {"pattern": "продажи", "match_type": "whole_word", "is_case_sensitive": False},
        {"pattern": r"\bSEO\b", "match_type": "regex", "is_case_sensitive": True},
    ]


def test_substring_match(keywords):
    result = match_message(
        "Курс по маркетингу и рекламе",
        datetime(2025, 1, 15, tzinfo=timezone.utc),
        keywords,
    )
    assert "маркетинг" in result


def test_substring_case_insensitive(keywords):
    result = match_message(
        "Курс по МАРКЕТИНГУ",
        datetime(2025, 1, 15, tzinfo=timezone.utc),
        keywords,
    )
    assert "маркетинг" in result


def test_whole_word_match(keywords):
    result = match_message(
        "Отдел продажи открыт",
        datetime(2025, 1, 15, tzinfo=timezone.utc),
        keywords,
    )
    assert "продажи" in result


def test_whole_word_no_partial():
    kws = [{"pattern": "test", "match_type": "whole_word", "is_case_sensitive": False}]
    result = match_message(
        "This is a testing environment",
        datetime(2025, 1, 15, tzinfo=timezone.utc),
        kws,
    )
    assert result == []


def test_regex_match(keywords):
    result = match_message(
        "Обучение SEO оптимизации",
        datetime(2025, 1, 15, tzinfo=timezone.utc),
        keywords,
    )
    assert r"\bSEO\b" in result


def test_regex_case_sensitive(keywords):
    result = match_message(
        "обучение seo оптимизации",
        datetime(2025, 1, 15, tzinfo=timezone.utc),
        keywords,
    )
    assert r"\bSEO\b" not in result


def test_no_match(keywords):
    result = match_message(
        "Погода в Москве сегодня",
        datetime(2025, 1, 15, tzinfo=timezone.utc),
        keywords,
    )
    assert result == []


def test_multiple_matches(keywords):
    result = match_message(
        "Маркетинг и продажи через SEO",
        datetime(2025, 1, 15, tzinfo=timezone.utc),
        keywords,
    )
    assert len(result) == 3


def test_date_from_filter(keywords):
    result = match_message(
        "Курс по маркетингу",
        datetime(2024, 12, 1, tzinfo=timezone.utc),
        keywords,
        date_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    assert result == []


def test_date_to_filter(keywords):
    result = match_message(
        "Курс по маркетингу",
        datetime(2025, 6, 1, tzinfo=timezone.utc),
        keywords,
        date_to=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )
    assert result == []


def test_date_within_range(keywords):
    result = match_message(
        "Курс по маркетингу",
        datetime(2025, 2, 1, tzinfo=timezone.utc),
        keywords,
        date_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
        date_to=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )
    assert "маркетинг" in result


def test_case_sensitive_substring():
    kws = [{"pattern": "Python", "match_type": "substring", "is_case_sensitive": True}]
    assert match_message("Learn Python today", datetime.now(timezone.utc), kws) == ["Python"]
    assert match_message("learn python today", datetime.now(timezone.utc), kws) == []


def test_invalid_regex():
    kws = [{"pattern": "[invalid", "match_type": "regex", "is_case_sensitive": False}]
    result = match_message("test text", datetime.now(timezone.utc), kws)
    assert result == []


def test_empty_keywords():
    result = match_message("any text", datetime.now(timezone.utc), [])
    assert result == []
