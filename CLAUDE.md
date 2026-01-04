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
python scripts/embed.py                   # bge-m3 embeddings → Pinecone (focus-group-v3)

# CLI search
python scripts/retrieve.py "query"        # LLM router + reranker

# Web interfaces (production stack - run both in separate terminals)
uvicorn api.main:app --reload             # FastAPI backend (port 8000)
cd web && npm run dev                     # Next.js frontend (port 3000)

# Legacy UI
streamlit run app.py                      # Streamlit UI (port 8501)

# Evaluation
python eval/run_retrieval_eval_v2.py             # Retrieval eval
./eval/router_eval/run_eval.sh                   # Router prompt A/B testing (promptfoo)

# Testing & linting
python eval/test_components.py                   # Unit tests for retrieval components
cd web && npm run lint                           # Frontend lint
cd web && npm run build                          # Frontend production build (type-checks)
```

## Architecture

### Data Flow
```
political-consulting-corpus/        # Raw markdown transcripts (37 focus groups, 12 races)
    ↓ preprocess.py
data/chunks/                        # Per-utterance JSON chunks (~3,126 total)
data/focus-groups/                  # Focus group metadata with moderator notes
data/manifest.json                  # Index of all chunks
    ↓ embed.py
Pinecone (focus-group-v3)           # bge-m3 embeddings (1024-dim, hierarchical)
    ↓ retrieve.py
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
│  retrieve.py       →  LLMRouter (routes to relevant focus groups)   │
│                    →  FocusGroupRetrieverV2 (bge-m3 + reranker)     │
│  synthesize.py     →  FocusGroupSynthesizer (light/deep/macro)      │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Pinecone (focus-group-v3)  │  OpenRouter (LLM calls)               │
│  bge-m3 embeddings          │  Gemini Flash for router/synthesis    │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Per-utterance chunking:** Every participant statement is its own chunk for maximum retrieval granularity
2. **LLM Router:** Routes queries to relevant focus groups before retrieval (reduces noise, improves precision)
3. **Hierarchical indexing (V2):** Parent vectors (FG-level) for routing, child vectors (utterance-level) for retrieval
4. **Synthesis layers:** Light (1-sentence), deep (per-FG analysis), macro (cross-FG themes)
5. **Lazy imports:** Optional dependencies (openai, pinecone, sentence-transformers) loaded only when needed

### Configuration

Required environment variables in `.env`:
- `PINECONE_API_KEY` - Vector storage (required)
- `OPENROUTER_API_KEY` - LLM router, synthesis, and evaluation (required)
- `OPENAI_API_KEY` - For V1 embeddings only (optional for V2)

Model configuration in `eval/config.py` (all overridable via `.env`):
- `ROUTER_MODEL` - LLM for query routing (default: `google/gemini-3-flash-preview`)
- `SYNTHESIS_MODEL` - LLM for synthesis (default: `google/gemini-3-flash-preview`)
- `OPENROUTER_MODEL` - LLM for evaluation (default: `google/gemini-3-flash-preview`)
- `EMBEDDING_MODEL_LOCAL` - Local embeddings (default: `BAAI/bge-m3`)
- `RERANKER_MODEL` - Cross-encoder reranker (default: `cross-encoder/ms-marco-MiniLM-L6-v2`)

Pinecone index:
- `focus-group-v3` - bge-m3 embeddings (1024-dim, hierarchical)

## Corpus Structure

12 races (2022-2024), 37 focus groups, ~3,126 searchable chunks.

Key races for demo scenario (Ohio 2026 challenger):
- **Race 007 (Ohio 2024):** Lost by 6.2% - working-class defection analysis
- **Race 009 (Michigan 2024):** Won - working-class authenticity messaging that worked
- **Race 012 (Wisconsin 2024):** Won - corrected 2022 mistakes

## Trust Requirements

Zero hallucination tolerance. From client requirements (see `docs/client-feedback-v1.md`):
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
# Retrieval
from scripts.retrieve import FocusGroupRetrieverV2, LLMRouter, RetrievalResult
from scripts.synthesize import FocusGroupSynthesizer

# Configuration
from eval.config import PINECONE_API_KEY, OPENROUTER_API_KEY, DATA_DIR
```

---

## Pinecone Notes

- Package: `pip install pinecone` (not `pinecone-client`)
- Metadata: 40KB max, flat JSON only
- Consistency: Eventually consistent (~1-5s after upsert)

## Frontend Notes

The Next.js frontend (`web/`) is a separate npm project. See `web/CLAUDE.md` for detailed frontend guidance.
```bash
cd web && npm install    # First-time setup
cd web && npm run dev    # Development server (port 3000)
```

Key frontend patterns:
- Streaming synthesis via `ReadableStream` from FastAPI `StreamingResponse`
- Auto-generated light summaries on search results load (staggered 200ms per FG)
- Skeleton loaders for perceived performance
- Collapsible quotes (collapsed by default to reduce cognitive load)
- Markdown export for search results (includes all synthesis)

### API Configuration (`web/app/config/api.ts`)

Centralized API endpoint configuration. Uses `NEXT_PUBLIC_API_URL` env var for production.

```typescript
import { ENDPOINTS } from './config/api';
// ENDPOINTS.search, ENDPOINTS.synthesizeLight, etc.
```

### Markdown Export (`web/app/utils/exportMarkdown.ts`)

Client-side markdown report generation. Exports all search results and synthesis to a `.md` file.

**What gets exported:**
- Query and stats header
- Macro synthesis (cross-FG "Synthesize Selected" results)
- Deep macro themes (if generated)
- Per-focus group sections with:
  - Deep synthesis (if user clicked "Deep Synthesis") OR light summary (auto-generated)
  - All quotes with participant attribution

**Key function:** `exportToMarkdown(data: ExportData)` - generates and downloads the markdown file.

The markdown can be viewed in any editor or converted to PDF via Pandoc, VS Code, or online tools.

## API Endpoints

FastAPI backend (`api/main.py`) endpoints:
- `GET /health` - Health check
- `POST /search` - Main search endpoint (returns grouped results by focus group)
- `POST /search/stream` - Streaming search with NDJSON status events
- `POST /synthesize/light` - Light 1-sentence summary (JSON response)
- `POST /synthesize/deep` - Deep per-FG analysis (streaming text)
- `POST /synthesize/macro/light` - Light cross-FG synthesis (streaming text)
- `POST /synthesize/macro/deep` - Deep theme-based synthesis (streaming NDJSON)

### Streaming Response Formats

**`/search/stream`** (NDJSON):
```json
{"type": "status", "step": "routing|filtering|searching|ranking", "message": "..."}
{"type": "results", "data": SearchResponse}
```

**`/synthesize/macro/deep`** (NDJSON):
```json
{"type": "stage", "message": "Discovering themes..."}
{"type": "theme_start", "name": "Theme Name", "focus_groups": ["FG1", "FG2"]}
{"type": "theme_content", "name": "Theme Name", "content": "..."}
{"type": "theme_complete", "name": "Theme Name"}
{"type": "complete"}
```
