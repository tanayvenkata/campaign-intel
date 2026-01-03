# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a semantic search and retrieval system for political consulting focus group transcripts. It enables junior analysts to surface institutional knowledge from historical focus groups without pulling in senior staff.

**Current State:** V2 with LLM router, synthesis layer, and production web UI (FastAPI + Next.js). Legacy Streamlit UI also available.

**Core User Scenario:** "What did Ohio voters say about the economy?" → Returns relevant quotes with participant context, focus group source, and transcript links.

## Development Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Data pipeline (run in order)
python scripts/preprocess.py              # Parse transcripts → JSON chunks
python scripts/embed.py                   # V1: OpenAI embeddings + BM25 → Pinecone
python scripts/embed_e5.py                # V2: E5-base local embeddings → Pinecone

# CLI search
python scripts/retrieve.py "query"        # V1 hybrid search
python scripts/retrieve_v2.py "query"     # V2 with LLM router + reranker

# Web interfaces (production stack)
cd api && uvicorn main:app --reload       # FastAPI backend (port 8000)
cd web && npm run dev                     # Next.js frontend (port 3000)

# Legacy UI
streamlit run app.py                      # Streamlit UI (port 8501)

# Evaluation
python eval/run_retrieval_eval.py                # V1 retrieval eval
python eval/run_retrieval_eval_v2.py             # V2 retrieval eval
./eval/router_eval/run_eval.sh                   # Router prompt A/B testing (promptfoo)
```

## Architecture

### Data Flow
```
political-consulting-corpus/        # Raw markdown transcripts (37 focus groups, 12 races)
    ↓ preprocess.py
data/chunks/                        # Per-utterance JSON chunks (~3,126 total)
data/focus-groups/                  # Focus group metadata with moderator notes
data/manifest.json                  # Index of all chunks
    ↓ embed.py / embed_e5.py
Pinecone                            # V1: focus-group-v1 (hybrid dense+BM25)
                                    # V2: focus-group-v2 (E5 768-dim + hierarchical)
    ↓ retrieve.py / retrieve_v2.py
scripts/synthesize.py               # LLM synthesis layer (light/deep/macro)
    ↓
app.py (Streamlit)                  # Full-featured UI with synthesis
api/main.py (FastAPI)               # REST API with streaming synthesis
web/ (Next.js)                      # React frontend (TypeScript + Tailwind)
```

### Component Relationships
```
┌─────────────────────────────────────────────────────────────────────┐
│                           User Interfaces                           │
├───────────────────┬────────────────────┬────────────────────────────┤
│ app.py (Streamlit)│ api/main.py (Fast) │ web/ (Next.js)             │
│ Port 8501         │ Port 8000          │ Port 3000 → calls API      │
└────────┬──────────┴─────────┬──────────┴────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         scripts/                                     │
│  retrieve_v2.py    →  LLMRouter (routes to relevant focus groups)   │
│                    →  FocusGroupRetrieverV2 (E5 + reranker)         │
│  synthesize.py     →  FocusGroupSynthesizer (light/deep/macro)      │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Pinecone (focus-group-v2)  │  OpenRouter (LLM calls)               │
│  E5-base embeddings         │  Claude Haiku for router/synthesis    │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Per-utterance chunking:** Every participant statement is its own chunk for maximum retrieval granularity
2. **LLM Router:** Routes queries to relevant focus groups before retrieval (reduces noise, improves precision)
3. **Hierarchical indexing (V2):** Parent vectors (FG-level) for routing, child vectors (utterance-level) for retrieval
4. **Synthesis layers:** Light (1-sentence), deep (per-FG analysis), macro (cross-FG themes)
5. **Lazy imports:** Optional dependencies (openai, pinecone, sentence-transformers) loaded only when needed

### Configuration

Environment variables (see `.env.example`):
- `OPENAI_API_KEY` - For V1 embeddings
- `PINECONE_API_KEY` - For vector storage
- `OPENROUTER_API_KEY` - For LLM router, synthesis, and evaluation

Model configuration in `eval/config.py`:
- `ROUTER_MODEL` - LLM for query routing (default: `anthropic/claude-3-haiku`)
- `SYNTHESIS_MODEL` - LLM for synthesis (default: `anthropic/claude-3-haiku`)
- `OPENROUTER_MODEL` - LLM for evaluation (default: `google/gemini-3-flash-preview`)

Pinecone indexes:
- `focus-group-v1` - Hybrid search (OpenAI + BM25)
- `focus-group-v2` - E5-base embeddings (768-dim, hierarchical)

## Corpus Structure

12 races (2022-2024), 37 focus groups, ~3,126 searchable chunks.

Key races for demo scenario (Ohio 2026 challenger):
- **Race 007 (Ohio 2024):** Lost by 6.2% - working-class defection analysis
- **Race 009 (Michigan 2024):** Won - working-class authenticity messaging that worked
- **Race 012 (Wisconsin 2024):** Won - corrected 2022 mistakes

## Trust Requirements

Zero hallucination tolerance. From client requirements:
- "I don't have enough information" is acceptable; confident wrong answer is not
- Every result must link to source transcript
- Retrieval-focused, not synthesis-focused (synthesis is V2)

---

## Query Scope

**Supported query types:**
- Topic + location: "What did Ohio voters say about X?"
- Participant filtering: "What did working-class voters think about Y?"
- Cross-FG synthesis: "Compare what different focus groups said about Z"

**Eval test sets** (`eval/test_queries_*.json`):
- `ohio_2024_focused` (10 queries): Primary test set
- `rachel-001`: Simple Ohio economy query
- `rachel-002`: Semantic inference query (stretch goal)

**Router eval** (`eval/router_eval/`): Promptfoo-based A/B testing for router prompt variations.

---

## Key Imports

```python
# V2 retrieval (recommended)
from scripts.retrieve_v2 import FocusGroupRetrieverV2, LLMRouter, RetrievalResult
from scripts.synthesize import FocusGroupSynthesizer

# V1 retrieval
from scripts.retrieve import FocusGroupRetriever

# Configuration
from eval.config import PINECONE_API_KEY, OPENROUTER_API_KEY, DATA_DIR
```

---

## Pinecone Notes

- Package: `pip install pinecone` (not `pinecone-client`)
- Metadata: 40KB max, flat JSON only
- Consistency: Eventually consistent (~1-5s after upsert)

## Frontend Notes

The Next.js frontend (`web/`) is a separate npm project:
```bash
cd web && npm install    # First-time setup
cd web && npm run dev    # Development server
```

Key frontend patterns:
- Streaming synthesis via `ReadableStream` from FastAPI `StreamingResponse`
- Auto-generated light summaries on search results load
- Skeleton loaders for perceived performance
- Collapsible quotes (collapsed by default to reduce cognitive load)
