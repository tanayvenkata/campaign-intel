# Fallback: Revert to E5 Embeddings

If BGE-m3 causes issues, here's how to quickly revert to E5-base-v2.

## What Changed (BGE-m3 Upgrade)

| Setting | E5 (Old) | BGE-m3 (Current) |
|---------|----------|------------------|
| Pinecone Index | `focus-group-v2` | `focus-group-v3` |
| Embedding Model | `intfloat/e5-base-v2` | `BAAI/bge-m3` |
| Dimensions | 768 | 1024 |
| Score Range | 0.75-0.85 | 0.50-0.65 |
| Threshold | 0.75 works | Need 0.50 |
| Eval Recall | 73% | 91% |

## Quick Reversion Steps

### 1. Update `scripts/retrieve.py` (line 34)
```python
# Change from:
INDEX_NAME = "focus-group-v3"

# To:
INDEX_NAME = "focus-group-v2"
```

### 2. Update `eval/config.py`
```python
# Change from:
EMBEDDING_MODEL_LOCAL = os.getenv("EMBEDDING_MODEL_LOCAL", "BAAI/bge-m3")
FG_SCORE_THRESHOLD = float(os.getenv("FG_SCORE_THRESHOLD", "0.50"))

# To:
EMBEDDING_MODEL_LOCAL = os.getenv("EMBEDDING_MODEL_LOCAL", "intfloat/e5-base-v2")
FG_SCORE_THRESHOLD = float(os.getenv("FG_SCORE_THRESHOLD", "0.75"))
```

### 3. Note on Query Prefixes
E5 requires query prefixes. Check that retrieve.py has:
```python
# E5 needs "query: " prefix
if "e5" in self.model_name.lower():
    query = f"query: {query}"
```

## Verification
```bash
# Test that FG retrieval works
python -c "
from scripts.retrieve import FocusGroupRetrieverV2
r = FocusGroupRetrieverV2(use_router=False, use_reranker=True, verbose=False)
results = r.retrieve_per_focus_group('What did Ohio voters say?', top_k_per_fg=5, score_threshold=0.75)
print(f'Found {len(results)} focus groups')
"
```

## Why We Upgraded to BGE-m3
- 18% recall improvement (73% → 91%)
- Better semantic understanding
- rachel-002 (semantic inference query) now passes

## Why You Might Revert
- Score threshold issues not resolved
- Client prefers simpler setup
- Strategy integration causing conflicts
