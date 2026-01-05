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
- **focus-group-v3**: Voter quotes from focus group transcripts (BGE-M3 embeddings, 1024 dims)
- **strategy-memos-v1**: Campaign strategy lessons from strategy memos

### Retrieval Pipeline

1. **LLM Router** (`scripts/retrieve.py:LLMRouter`) — Gemini Flash analyzes query intent to determine:
   - Content type: "quotes" (focus groups), "lessons" (strategy memos), or "both"
   - Focus group filtering: which specific FGs to search (or all)
   - Outcome filtering: "win", "loss", or none

2. **Retrievers** — Two parallel retrieval paths:
   - `FocusGroupRetrieverV2`: Hierarchical search (parent chunks → child chunks)
   - `StrategyMemoRetriever`: Direct semantic search on strategy chunks

3. **Reranking** — Cross-encoder reranking (ms-marco-MiniLM-L6-v2) for precision

4. **Synthesis** — Multi-level LLM synthesis:
   - Light: 1-2 sentence per-source summaries
   - Deep: 2-3 paragraph per-source analysis
   - Macro: Cross-source thematic synthesis

### Key Files

| File | Purpose |
|------|---------|
| `scripts/retrieve.py` | Core retrieval logic: LLMRouter, FocusGroupRetrieverV2, StrategyMemoRetriever |
| `scripts/synthesize.py` | LLM synthesis (light, deep, macro) |
| `api/main.py` | FastAPI endpoints wrapping retrieval/synthesis |
| `eval/config.py` | Central configuration: API keys, models, paths, thresholds |
| `web/app/config/api.ts` | Frontend API configuration |

### Environment Variables

Required in `.env`:
- `PINECONE_API_KEY` — Vector database
- `OPENROUTER_API_KEY` — LLM calls (routing, synthesis)
- `OPENAI_API_KEY` — Embeddings

Optional model overrides:
- `ROUTER_MODEL`, `SYNTHESIS_MODEL` — Default: `google/gemini-3-flash-preview`
- `USE_RERANKER` — Enable/disable cross-encoder reranking (default: false in prod)

### Deployment

- **Frontend**: Vercel (requires `NEXT_PUBLIC_API_URL` env var pointing to backend)
- **Backend**: Railway (auto-deploys from main branch)
- **CORS**: Backend allows `*.vercel.app` via `allow_origin_regex`

## Design Principles

- **Zero hallucination**: Retrieval-focused with source citations. "I don't know" is acceptable.
- **Fewer high-confidence insights > comprehensive**: Top 2 results per source, strict score thresholds (0.50)
- **Streaming UX**: All LLM endpoints support streaming responses

## Corpus

The included corpus is **synthetic demo data** (12 races, 37 focus groups, ~3,100 chunks). Located in `political-consulting-corpus/` and `data/`.
