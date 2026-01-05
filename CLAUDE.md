# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Campaign Intel is a semantic search and retrieval system for political consulting focus groups and strategy memos. It allows analysts to query archived qualitative research using natural language.

## Commands

### Development

```bash
# Backend (Terminal 1)
source venv/bin/activate
uvicorn api.main:app --reload

# Frontend (Terminal 2)
cd web && npm run dev
```

### Testing

```bash
# E2E backend tests (requires backend running)
python eval/test_backend_e2e.py

# Frontend type-check/build
cd web && npm run build

# Router prompt A/B testing with Promptfoo
./eval/router_eval/run_eval.sh

# Local Docker build test (before deploying)
docker build -t campaign-intel-test .
docker run --rm -p 8000:8000 -e OPENAI_API_KEY -e OPENROUTER_API_KEY -e PINECONE_API_KEY -e USE_OPENAI_EMBEDDINGS=true -e USE_RERANKER=false campaign-intel-test
```

### Data Pipeline

```bash
# Preprocess transcripts → chunks
python scripts/preprocess.py

# Embed chunks → Pinecone
python scripts/embed.py

# CLI search test
python scripts/retrieve.py "What did Ohio voters say about the economy?"
```

## Architecture

### Two-Index Design

The system uses two separate Pinecone indexes:
- **focus-group-v3**: Voter quotes from focus group transcripts (1024 dims)
- **strategy-memos-v1**: Campaign strategy lessons from strategy memos

### Embedding Modes

- **Production** (`USE_OPENAI_EMBEDDINGS=true`): OpenAI `text-embedding-3-small` via API (~2-3s queries)
- **Local dev** (`USE_OPENAI_EMBEDDINGS=false`): BGE-M3 local model (~12s queries on CPU)

Both use the same Pinecone index but different namespaces (`openai` vs default).

### Retrieval Pipeline

1. **LLM Router** (`scripts/retrieval/router.py`) — Gemini Flash analyzes query intent to determine:
   - Content type: "quotes" (focus groups), "lessons" (strategy memos), or "both"
   - Focus group filtering: which specific FGs to search (or all)
   - Outcome filtering: "win", "loss", or none

2. **Retrievers** — Two parallel retrieval paths:
   - `FocusGroupRetrieverV2`: Hierarchical search (parent chunks → child chunks)
   - `StrategyMemoRetriever`: Direct semantic search on strategy chunks

3. **Reranking** (optional) — Cross-encoder reranking (ms-marco-MiniLM-L6-v2), disabled in prod for speed

4. **Synthesis** — Multi-level LLM synthesis:
   - Light: 1-2 sentence per-source summaries
   - Deep: 2-3 paragraph per-source analysis
   - Macro: Cross-source thematic synthesis

### Caching Architecture

All synthesis endpoints use TTLCache (1 hour TTL) to avoid redundant LLM calls:

| Cache | Endpoint | Pre-warmed |
|-------|----------|------------|
| `search_cache` | `/search/unified` | ✓ (4 suggested queries) |
| `light_summary_cache` | `/synthesize/light` | ✓ |
| `deep_summary_cache` | `/synthesize/deep` | ✓ |
| `macro_synthesis_cache` | `/synthesize/macro/light` | ✓ |
| `strategy_light_cache` | `/synthesize/strategy/light` | ✓ |
| `strategy_deep_cache` | `/synthesize/strategy/deep` | Lazy |
| `strategy_macro_cache` | `/synthesize/strategy/macro` | Lazy |
| `unified_macro_cache` | `/synthesize/unified/macro` | Lazy |

**Pre-warming**: On startup, the backend pre-warms caches for 4 suggested queries (defined in `EXAMPLE_QUERIES`) so demo clicks are instant. Controlled by `PREWARM_CACHE=true` env var.

### Key Files

| File | Purpose |
|------|---------|
| `scripts/retrieval/router.py` | LLM Router for query intent classification |
| `scripts/retrieval/base.py` | SharedResources singleton (embeddings, Pinecone) |
| `scripts/retrieve.py` | FocusGroupRetrieverV2, StrategyMemoRetriever |
| `scripts/synthesize.py` | LLM synthesis (light, deep, macro) |
| `api/main.py` | FastAPI endpoints wrapping retrieval/synthesis |
| `eval/config.py` | Central configuration: API keys, models, paths, thresholds |
| `prompts/router_unified.txt` | Externalized router prompt |

### Environment Variables

Required in `.env`:
- `PINECONE_API_KEY` — Vector database
- `OPENROUTER_API_KEY` — LLM calls (routing, synthesis)
- `OPENAI_API_KEY` — Embeddings (production)

Production settings:
- `USE_OPENAI_EMBEDDINGS=true` — Use fast OpenAI API instead of slow local BGE-M3
- `USE_RERANKER=false` — Disable heavy reranker model for speed

Optional model overrides:
- `ROUTER_MODEL`, `SYNTHESIS_MODEL` — Default: `google/gemini-3-flash-preview`

### Deployment

- **Frontend**: Vercel at `campaign-intel.vercel.app` (requires `NEXT_PUBLIC_API_URL`)
- **Backend**: Railway at `campaign-intel-production.up.railway.app` (Dockerfile, auto-deploys from main)
- **CORS**: Backend allows `*.vercel.app` via `allow_origin_regex`

Production uses lightweight `requirements-prod.txt` (no torch/sentence-transformers) for fast cold starts.

## Design Principles

- **Zero hallucination**: Retrieval-focused with source citations. "I don't know" is acceptable.
- **Fewer high-confidence insights > comprehensive**: Top 2 results per source, strict score thresholds (0.50)
- **Streaming UX**: All LLM endpoints support streaming responses

## Corpus

The included corpus is **synthetic demo data** (12 races, 37 focus groups, ~3,100 chunks). Located in `political-consulting-corpus/` and `data/`.
