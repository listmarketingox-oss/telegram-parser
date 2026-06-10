# Smart Search with Typo Tolerance — Design Spec

**Date:** 2026-01-09  
**Status:** Design Approved  
**Priority:** Medium  

---

## Overview

Enhance the Telegram Parser search functionality to support:
1. **Lemmatization** — find words by their root form
2. **Typo detection** — generate common misspellings
3. **Fuzzy matching** — find similar words using Levenshtein distance
4. **Truncated words** — find partial word matches

Currently, search only uses Claude API for synonyms and word forms. New approach adds local Python-based processing for better performance and cost efficiency.

---

## User Requirements

**Search modes:**
- **Exact**: Only the exact keyword (fast, precise)
- **Smart** (default): Synonyms + lemma + typos with fuzzy threshold 85%
- **Aggressive**: Smart + fuzzy threshold 75% + truncated words

**User controls:**
- Radio button on Search page to select mode
- Mode persists for current search session
- Display expanded terms above results (like currently)

**Success criteria:**
- User can find "ставка" when document contains "ставки", "ставку", "процент", "стакка", etc.
- Toggle between modes is easy and visible
- No performance degradation (local processing is fast)
- Cost-neutral (no additional Claude API calls)

---

## Architecture

### Query Processing Pipeline

```
User Input (keyword)
    ↓
[Query Processor]
    ├─ Mode: exact | smart | aggressive
    ├─ Step 1: Include original keyword
    ├─ Step 2: Claude expand_query() → synonyms, word forms
    ├─ Step 3: Lemmatizer → root form
    ├─ Step 4: Typo Generator → common misspellings
    ├─ Step 5: Fuzzy Matcher → similar words (threshold 85% for smart, 75% for aggressive)
    ├─ Step 6: Word Truncations → partial matches (aggressive only)
    ↓
[Combined Terms List]
    ↓
[live_search()] → regex pattern with all terms
    ↓
[Results] → display with expanded terms shown
```

### Data Flow

1. User enters keyword and selects mode on `/search-page`
2. JavaScript sends: `keyword`, `mode`, `date_from`, `date_to`, `source_ids`
3. API endpoint `/api/search` receives mode parameter
4. Backend `process_query(keyword, mode)` returns expanded terms list
5. `live_search()` searches with combined regex pattern
6. Results displayed with expanded terms as tags (existing UI)

---

## Implementation Details

### New Module: `app/services/query_processor.py`

**Exports:**
```python
async def process_query(keyword: str, mode: str = "smart") -> list[str]:
    """
    Process keyword into search terms based on mode.
    
    Args:
        keyword: User input (e.g., "ставка")
        mode: "exact" | "smart" | "aggressive"
    
    Returns:
        Sorted list of unique search terms
    
    Processing order:
    1. Original keyword (always included)
    2. Claude synonyms/forms (if mode >= "smart")
    3. Lemmatized form (if mode >= "smart")
    4. Generated typos (if mode >= "smart")
    5. Fuzzy matches 85% (if mode >= "smart")
    6. Fuzzy matches 75% (if mode == "aggressive")
    7. Truncated words (if mode == "aggressive")
    
    Deduplication: all results stored in set
    Limit: max 50 terms (avoid regex explosion)
    """
```

**Sub-functions:**

```python
def get_lemma(word: str) -> str:
    """Get root form using pymorphy2. Returns original if no lemma found."""
    
def generate_typos(word: str, max_typos: int = 5) -> set[str]:
    """
    Generate common typos using character substitution/omission.
    
    Strategy:
    - Adjacent keyboard keys (ё↔е, й↔ы)
    - Omit one character (ставка → става, ствка)
    - Duplicate character (ставка → ставвка, стаавка)
    - Swap adjacent chars (ставка → стакка)
    
    Return top 5 most plausible.
    """
    
def fuzzy_search(word: str, threshold: int = 85) -> set[str]:
    """
    Find similar words from a predefined Russian word list.
    
    Uses fuzzywuzzy.token_set_ratio() for robustness.
    Threshold: 0-100 (higher = stricter)
    
    Challenge: No built-in Russian dictionary. Solutions:
    - Option A: Use words from indexed messages (from DB)
    - Option B: Use external Russian word list (pymorphy2 dictionary)
    - Recommended: Option B (pymorphy2 has ~260k Russian words)
    """
    
def find_word_roots(word: str) -> set[str]:
    """
    Find words that have this word as prefix (truncation search).
    
    Example: "став" → ["ставка", "ставил", "ставка"]
    Uses pymorphy2 to find all inflections of potential root words.
    """
```

### Dependencies to Add

**`requirements.txt`:**
```
pymorphy2==0.9.1              # Russian lemmatization
fuzzywuzzy==0.18.0            # Fuzzy string matching
python-Levenshtein==0.21.1    # Fast Levenshtein distance
```

### Modified: `app/api/search.py`

**Changes:**
1. Import `process_query` from query_processor
2. Add `mode` parameter to `/api/search` endpoint
3. Call `process_query(keyword, mode)` before `live_search()`
4. Pass expanded terms to `live_search()`

```python
@router.get("")
async def search(
    keyword: str = Query(..., min_length=1),
    mode: str = Query("smart", pattern="^(exact|smart|aggressive)$"),
    source_ids: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    smart: bool = Query(True),  # existing Claude expansion toggle
    limit: int = Query(500),
    db: AsyncSession = Depends(get_db),
):
    # ... existing code ...
    
    # Process with mode
    expanded_terms = await process_query(keyword, mode)
    
    # Search with expanded terms
    results = await live_search(
        keyword=keyword,
        source_ids=parsed_source_ids,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        limit_per_source=limit,
        expanded_terms=expanded_terms,  # existing parameter
    )
    
    # Return with mode info
    return {
        "results": results,
        "total": len(results),
        "keyword": keyword,
        "mode": mode,
        "expanded_terms": expanded_terms,
        "expanded_terms_count": len(expanded_terms),
        "history_id": str(history.id),
    }
```

### Modified: `templates/search.html`

**Add mode selector:**
```html
<div class="search-options">
    <!-- existing code -->
    
    <div class="search-option">
        <label class="form-label">Режим поиска:</label>
        <div class="search-modes">
            <label class="radio-label">
                <input type="radio" name="searchMode" value="exact"> 
                🎯 Точный
            </label>
            <label class="radio-label">
                <input type="radio" name="searchMode" value="smart" checked> 
                🧠 Умный (лемма, опечатки)
            </label>
            <label class="radio-label">
                <input type="radio" name="searchMode" value="aggressive"> 
                🚀 Очень умный (+ fuzzy)
            </label>
        </div>
    </div>
</div>
```

**Update JavaScript:**
```javascript
function buildSearchParams() {
    const params = new URLSearchParams();
    // ... existing code ...
    
    const mode = document.querySelector('input[name="searchMode"]:checked').value;
    params.set('mode', mode);
    
    return params;
}
```

### Display Results

**Existing behavior preserved:**
- Expanded terms shown as tags above results
- Example: `🧠 Искали: ставка, ставки, ставку, процент, стакка, ставкa...`
- New: prepend with mode indicator: `[Умный поиск]` or `[Точный поиск]`

---

## Testing Strategy

**Unit tests** (`tests/services/test_query_processor.py`):
- `test_exact_mode`: returns [keyword] only
- `test_smart_mode`: includes lemma, typos, fuzzy 85%
- `test_aggressive_mode`: includes all options
- `test_lemmatizer`: Russian word lemmatization
- `test_typo_generator`: realistic typos only
- `test_fuzzy_matching`: threshold edge cases

**Integration tests** (`tests/api/test_search_with_modes.py`):
- Search with each mode returns expected result count
- Expanded terms properly displayed
- No performance degradation (< 2s per search)

**Manual testing**:
- Search "ставка" in exact → only matches "ставка"
- Search "ставка" in smart → matches "ставки", "ставку", "процент", "стакка"
- Search "ставка" in aggressive → broader matches
- Verify UI toggle works smoothly

---

## Performance Considerations

**Lemmatization** (pymorphy2):
- ~1-5ms per word (cached)
- Memory: ~30MB for Russian dictionary

**Typo generation**:
- ~2-5ms per word
- CPU-bound, not IO-bound

**Fuzzy matching**:
- ~10-50ms for 1000 candidate words
- Threshold 85% faster than 75%

**Combined processing:**
- Exact mode: <1ms
- Smart mode: ~20-50ms
- Aggressive mode: ~100-200ms

**Optimization:**
- Cache lemmas and typos per keyword
- Limit fuzzy matching to top 1000 most common Russian words (not entire dictionary)
- Set max_terms = 50 to avoid regex explosion

---

## Rollback Plan

If issues arise:
1. Disable mode selector: users see only "smart" (default)
2. Revert `process_query()` call in API
3. Keep dependencies installed (minimal bloat)
4. No data migration needed (new field in API response)

---

## Scope Clarifications

**Explicitly NOT included:**
- Machine learning-based semantic search (too heavy)
- Spell-checker (too complex for this phase)
- Multi-language support (Russian only, as per spec)
- User-configurable fuzzy thresholds (fixed 85%/75%)

**Future enhancements:**
- Cache frequently searched terms
- Learn user's preferred mode over time
- Add "Search tips" tooltip
- Support English/other languages

---

## Acceptance Criteria

✅ Mode selector visible on search page  
✅ API accepts `mode` parameter  
✅ Process query returns expanded terms list  
✅ Results match expected expanded terms  
✅ UI displays expanded terms as tags  
✅ No performance regression  
✅ Unit tests pass (>90% coverage)  
✅ Manual testing on 10+ Cyrillic keywords works  

---

## Timeline

- **Effort:** ~6-8 hours implementation + 2 hours testing
- **Complexity:** Medium (new module, no architecture changes)
- **Risk:** Low (isolated to query processing, live_search untouched)
