"""Expand search queries using Claude API for semantic search.

Given a keyword like "ставка", returns related terms:
["ставка", "ставки", "ставку", "ставкой", "процент", "процентная", "кредит", ...]
"""
import json
import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

EXPAND_PROMPT = """Ты — помощник для расширения поисковых запросов на русском языке.

Пользователь ищет сообщения в Telegram по ключевому слову.
Твоя задача — вернуть расширенный список слов/фраз для поиска.

Включи:
1. Все словоформы (падежи, числа, времена): ставка → ставки, ставку, ставкой, ставке
2. Однокоренные слова: ставка → ставочный, ставить (если по смыслу)
3. Синонимы и связанные по смыслу слова: ставка → процент, тариф, rate
4. Устойчивые выражения: ставка → ключевая ставка, процентная ставка
5. Сокращения и сленг, если есть

НЕ включай:
- Слова с другим значением (омонимы с другим смыслом)
- Слишком общие слова (деньги, экономика)
- Больше 20 вариантов

Верни ТОЛЬКО JSON-массив строк, без пояснений.

Ключевое слово: {keyword}"""


async def expand_query(keyword: str) -> list[str]:
    """Expand keyword into related search terms using Claude."""
    if not settings.ANTHROPIC_API_KEY:
        logger.info("No ANTHROPIC_API_KEY — using keyword as-is")
        return [keyword]

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            temperature=0.2,
            messages=[
                {"role": "user", "content": EXPAND_PROMPT.format(keyword=keyword)}
            ],
        )

        text = response.content[0].text.strip()
        # Parse JSON array from response
        if text.startswith("["):
            terms = json.loads(text)
        else:
            # Try to extract JSON from markdown code block
            import re
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                terms = json.loads(match.group())
            else:
                terms = [keyword]

        # Always include original keyword
        if keyword.lower() not in [t.lower() for t in terms]:
            terms.insert(0, keyword)

        logger.info("Expanded '%s' → %d terms: %s", keyword, len(terms), terms[:5])
        return terms[:20]

    except Exception as e:
        logger.error("Query expansion failed: %s", e)
        return [keyword]
