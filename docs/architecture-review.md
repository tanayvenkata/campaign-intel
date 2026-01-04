# Architecture Review

**Date:** 2025-01-04
**Status:** Issues Identified - Fixes Pending

---

## Executive Summary

The codebase has grown organically and has several architectural issues that could lead to bugs and maintenance problems. Key issues:

1. **Configuration Fragmentation** - Hardcoded values scattered across files
2. **Monolithic Files** - `retrieve.py` (1266 lines) does too much
3. **Duplicated Code** - Same initialization logic in multiple classes
4. **Inconsistent Index Names** - Different files use different Pinecone indexes

---

## Issue 1: Configuration Fragmentation

### Problem
Configuration values are defined in multiple places, leading to inconsistencies:

| Setting | `eval/config.py` | `scripts/retrieve.py` | `api/main.py` |
|---------|------------------|----------------------|---------------|
| Pinecone Index | `focus-group-v1` (default) | `focus-group-v3` (hardcoded) | imports from retrieve.py |
| Score Threshold | `FG_SCORE_THRESHOLD=0.50` | Not used | Uses request param |
| MAX_TOTAL_QUOTES | - | - | `40` (hardcoded) |

### Files with Hardcoded Index Names
```
scripts/embed.py:27           → "focus-group-v3"
scripts/retrieve.py:34        → "focus-group-v3"
eval/config.py:39             → "focus-group-v1" (default, never used)
experiments/build_v2_index.py → "focus-group-v2"
experiments/retrieve_doc2query.py → "focus-group-v2"
```

### Recommendation
1. Move ALL configuration to `eval/config.py`
2. Add `PINECONE_INDEX_NAME_V3` for current index
3. Remove all hardcoded values from scripts

---

## Issue 2: Monolithic `retrieve.py`

### Problem
`scripts/retrieve.py` is 1266 lines with 3 major classes:
- `LLMRouter` (190 lines) - Query routing logic
- `FocusGroupRetrieverV2` (520 lines) - FG retrieval
- `StrategyMemoRetriever` (300 lines) - Strategy memo retrieval

These should be separate modules for maintainability.

### Current Structure
```
scripts/retrieve.py
├── Data classes (RetrievalResult, GroupedResults, etc.)
├── LLMRouter
├── FocusGroupRetrieverV2
├── StrategyMemoRetriever
└── CLI main()
```

### Recommended Structure
```
scripts/
├── retrieval/
│   ├── __init__.py          # Exports all public classes
│   ├── types.py              # Data classes
│   ├── router.py             # LLMRouter
│   ├── focus_group.py        # FocusGroupRetrieverV2
│   ├── strategy.py           # StrategyMemoRetriever
│   └── base.py               # Shared base class for retrievers
├── retrieve.py               # CLI wrapper (imports from retrieval/)
└── synthesize.py
```

---

## Issue 3: Duplicated Initialization

### Problem
Both `FocusGroupRetrieverV2` and `StrategyMemoRetriever` have nearly identical initialization:

```python
# FocusGroupRetrieverV2.__init__ (line 329-334)
self.model = SentenceTransformer(EMBEDDING_MODEL_LOCAL)
self.pc = Pinecone(api_key=PINECONE_API_KEY)
self.index = self.pc.Index(INDEX_NAME)

# StrategyMemoRetriever.__init__ (line 841-846)
self.model = SentenceTransformer(EMBEDDING_MODEL_LOCAL)
self.pc = Pinecone(api_key=PINECONE_API_KEY)
self.index = self.pc.Index(INDEX_NAME)
```

This wastes memory (loads model twice) and is error-prone.

### Recommendation
Create a base class or shared resource manager:

```python
class BaseRetriever:
    _shared_model = None
    _shared_index = None

    @classmethod
    def get_embedding_model(cls):
        if cls._shared_model is None:
            cls._shared_model = SentenceTransformer(EMBEDDING_MODEL_LOCAL)
        return cls._shared_model
```

---

## Issue 4: Error Handling Gaps

### Problem
API endpoints have minimal error handling:

```python
# api/main.py - No try/catch around LLM calls
route_result = router.route_unified(request.query)  # Can throw
results_by_fg = retriever.retrieve_per_focus_group(...)  # Can throw
```

If the LLM router fails or Pinecone times out, the user gets a 500 error with no helpful message.

### Recommendation
Add structured error handling:

```python
try:
    route_result = router.route_unified(request.query)
except RateLimitError:
    tracer.log("error", {"type": "rate_limit"})
    raise HTTPException(503, "LLM rate limited, please retry")
except TimeoutError:
    tracer.log("error", {"type": "timeout"})
    raise HTTPException(504, "Request timed out")
```

---

## Issue 5: Prompt Management

### Problem
LLM prompts are embedded as string literals in code:

```python
# scripts/retrieve.py:104
SYSTEM_PROMPT = """You are a political research assistant..."""
```

This makes prompts hard to version, test, and iterate on.

### Recommendation
Move prompts to files:
```
prompts/
├── router_system.txt
├── synthesis_light.txt
├── synthesis_deep.txt
└── unified_macro.txt
```

Load with: `ROUTER_PROMPT = Path("prompts/router_system.txt").read_text()`

---

## Priority Fixes

### High Priority (Breaking Risk)
1. **Fix Index Name Configuration** - Use `eval/config.py` everywhere
2. **Add Error Handling** - Prevent silent failures

### Medium Priority (Maintainability)
3. **Split `retrieve.py`** - Create `scripts/retrieval/` package
4. **Centralize Initialization** - Shared embedding model

### Low Priority (Nice to Have)
5. **Externalize Prompts** - Move to files
6. **Add Type Hints** - Improve IDE support

---

## Action Items

- [ ] Update `eval/config.py` with `PINECONE_INDEX_NAME = "focus-group-v3"`
- [ ] Replace hardcoded `INDEX_NAME` in `scripts/retrieve.py` with config import
- [ ] Add try/catch to `/search/unified` endpoint
- [ ] Create `scripts/retrieval/` package structure
- [ ] Add shared embedding model singleton

---

## Appendix: File Sizes

| File | Lines | Notes |
|------|-------|-------|
| scripts/retrieve.py | 1266 | Should be split |
| api/main.py | 848 | OK, well-organized |
| scripts/synthesize.py | 814 | Could use cleanup |
| eval/config.py | 86 | Should be larger (more config) |
