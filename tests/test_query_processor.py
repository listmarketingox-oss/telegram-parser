import pytest

from app.services.query_processor import get_lemma, process_query


def test_get_lemma_uses_russian_morphology():
    assert get_lemma("ставки") == "ставка"


@pytest.mark.asyncio
async def test_process_query_exact_returns_original_keyword():
    assert await process_query("ставка", "exact") == ["ставка"]


@pytest.mark.asyncio
async def test_process_query_smart_includes_original_keyword():
    terms = await process_query("ставка", "smart")
    assert "ставка" in terms
