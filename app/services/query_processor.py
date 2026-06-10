"""Query processor for smart search with typo tolerance.

Supports three modes:
- exact: only the exact keyword
- smart: lemma + typos + fuzzy 85% + Claude synonyms
- aggressive: smart + fuzzy 75% + truncated words
"""
import logging
from typing import Set

import pymorphy2
from fuzzywuzzy import fuzz

from app.services.query_expander import expand_query

logger = logging.getLogger(__name__)

# Russian morphology analyzer
_morph = pymorphy2.MorphAnalyzer()

# Common Russian words for fuzzy matching (subset of pymorphy2 dictionary)
# In production, can be expanded or cached
_FUZZY_DICTIONARY = None


def _load_fuzzy_dictionary() -> Set[str]:
    """Lazy load Russian words from pymorphy2 dictionary."""
    global _FUZZY_DICTIONARY
    if _FUZZY_DICTIONARY is not None:
        return _FUZZY_DICTIONARY

    # Get unique lemmas from pymorphy2's dictionary
    words = set()
    for word_form in _morph.dict.items():
        lemma = _morph.parse(word_form.word)[0].normal_form
        if len(lemma) >= 3:  # Skip very short words
            words.add(lemma)
    _FUZZY_DICTIONARY = words
    logger.info("Loaded %d Russian words for fuzzy matching", len(words))
    return words


def get_lemma(word: str) -> str:
    """Get root form of Russian word using pymorphy2.

    Args:
        word: Input word

    Returns:
        Lemmatized form, or original word if not found
    """
    try:
        parsed = _morph.parse(word)
        if parsed:
            return parsed[0].normal_form
        return word
    except Exception as e:
        logger.debug("Lemmatization failed for '%s': %s", word, e)
        return word


def generate_typos(word: str, max_typos: int = 8) -> Set[str]:
    """Generate common Russian typos.

    Strategy:
    - Adjacent keyboard keys (ё↔е, й↔ы)
    - Omit one character (ставка → става, ствка)
    - Duplicate character (ставка → ставвка, стаавка)
    - Swap adjacent chars (ставка → стакка)

    Args:
        word: Input word
        max_typos: Max typos to generate

    Returns:
        Set of typo variants
    """
    if len(word) < 3:
        return set()

    typos = set()

    # Keyboard adjacency for Russian ЙЦУКЕН layout
    keyboard_map = {
        "а": ["я", "с"],
        "б": ["ю", "в"],
        "в": ["б", "г"],
        "г": ["в", "д"],
        "д": ["г", "е"],
        "е": ["д", "р", "ё"],
        "ё": ["е"],
        "ж": ["з"],
        "з": ["ж", "х"],
        "и": ["й", "у"],
        "й": ["и"],
        "к": ["л"],
        "л": ["к", "о"],
        "м": ["н"],
        "н": ["м", "б"],
        "о": ["л", "п"],
        "п": ["о", "р"],
        "р": ["п", "е"],
        "с": ["а", "т"],
        "т": ["с", "у"],
        "у": ["т", "и"],
        "ф": ["ы"],
        "х": ["з", "ц"],
        "ц": ["х", "ч"],
        "ч": ["ц", "ш"],
        "ш": ["ч", "щ"],
        "щ": ["ш", "ъ"],
        "ъ": ["щ", "ы"],
        "ы": ["ф", "ъ"],
        "ь": [],
    }

    # 1. Adjacent keyboard substitution
    for i, char in enumerate(word):
        if char in keyboard_map:
            for adj_char in keyboard_map[char]:
                typo = word[:i] + adj_char + word[i + 1 :]
                typos.add(typo)
                if len(typos) >= max_typos:
                    break

    # 2. Omit one character
    for i in range(len(word)):
        typo = word[:i] + word[i + 1 :]
        typos.add(typo)

    # 3. Duplicate adjacent character
    for i in range(len(word) - 1):
        typo = word[:i] + word[i] + word[i:]
        typos.add(typo)

    # 4. Swap adjacent characters
    for i in range(len(word) - 1):
        typo = word[:i] + word[i + 1] + word[i] + word[i + 2 :]
        typos.add(typo)

    return set(list(typos)[:max_typos])


def fuzzy_search(word: str, threshold: int = 85) -> Set[str]:
    """Find similar words using Levenshtein distance.

    Args:
        word: Input word
        threshold: Similarity threshold 0-100

    Returns:
        Set of similar words above threshold
    """
    if len(word) < 2:
        return set()

    try:
        dictionary = _load_fuzzy_dictionary()
        similar = set()

        # For performance, only check words of similar length
        word_len = len(word)
        candidates = [
            w for w in dictionary if abs(len(w) - word_len) <= 2
        ]

        for candidate in candidates:
            score = fuzz.token_set_ratio(word, candidate)
            if score >= threshold:
                similar.add(candidate)

        return similar
    except Exception as e:
        logger.debug("Fuzzy search failed for '%s': %s", word, e)
        return set()


def find_truncated_words(word: str) -> Set[str]:
    """Find words that contain this word as prefix.

    Example: "став" → ["ставка", "ставил", "ставка"]

    Args:
        word: Prefix/root word

    Returns:
        Set of words with this prefix
    """
    if len(word) < 3:
        return set()

    results = set()
    # Use pymorphy2 dictionary to find inflections
    for parsed in _morph.TaggedDict.get(word, []):
        if parsed:
            results.add(parsed.word)

    return results


async def process_query(keyword: str, mode: str = "smart") -> list[str]:
    """Process keyword into search terms based on mode.

    Args:
        keyword: User input (e.g., "ставка")
        mode: "exact" | "smart" | "aggressive"

    Returns:
        Sorted list of unique search terms

    Processing order:
    1. Original keyword (always)
    2. Claude synonyms/forms (if mode >= smart)
    3. Lemmatized form (if mode >= smart)
    4. Generated typos (if mode >= smart)
    5. Fuzzy matches 85% (if mode >= smart)
    6. Fuzzy matches 75% (if mode == aggressive)
    7. Truncated words (if mode == aggressive)
    """
    terms = {keyword}  # Always include original

    if mode not in ["exact", "smart", "aggressive"]:
        logger.warning("Invalid mode '%s', using 'smart'", mode)
        mode = "smart"

    if mode == "exact":
        return [keyword]

    # Lemmatization
    lemma = get_lemma(keyword)
    if lemma != keyword.lower():
        terms.add(lemma)

    # Claude synonyms & word forms
    try:
        expanded = await expand_query(keyword)
        terms.update(expanded)
    except Exception as e:
        logger.warning("Claude expansion failed: %s", e)

    # Typo generation (smart mode and above)
    if mode in ["smart", "aggressive"]:
        typos = generate_typos(keyword)
        terms.update(typos)

        # Fuzzy matching 85%
        fuzzy_85 = fuzzy_search(keyword, threshold=85)
        terms.update(fuzzy_85)

    # Aggressive mode: more fuzzy + truncations
    if mode == "aggressive":
        # Fuzzy matching 75%
        fuzzy_75 = fuzzy_search(keyword, threshold=75)
        terms.update(fuzzy_75)

        # Truncated words
        truncated = find_truncated_words(keyword)
        terms.update(truncated)

    # Limit to prevent regex explosion
    max_terms = 50
    if len(terms) > max_terms:
        logger.info(
            "Query expansion for '%s' produced %d terms, limiting to %d",
            keyword,
            len(terms),
            max_terms,
        )
        terms = set(sorted(list(terms))[:max_terms])

    result = sorted(list(terms))
    logger.info(
        "Processed query '%s' mode=%s: %d terms",
        keyword,
        mode,
        len(result),
    )
    return result
