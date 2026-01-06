# Campaign Intel

A semantic search and retrieval system for political consulting focus groups and strategy memos. Surfaces institutional knowledge from historical qualitative research without pulling in senior staff.

## The Problem

Political consulting firms run hundreds of focus groups over years, but that qualitative insight gets buried in Dropbox folders. Junior analysts spend hours searching for relevant quotes, or interrupt senior staff who have the context in their heads.

**Campaign Intel** lets analysts query the archive naturally:

- *"What did Ohio voters say about the economy?"* → Returns relevant voter quotes
- *"What went wrong in Montana?"* → Returns strategy memo lessons
- *"What messaging worked with working-class voters?"* → Returns both quotes AND strategic analysis

## Features

- **LLM-powered query routing** — Automatically decides whether to search focus group quotes, strategy memos, or both
- **Semantic search** — OpenAI embeddings (production) or BGE-M3 (local dev) with optional cross-encoder reranking
- **Multi-level synthesis** — Light summaries, deep per-source analysis, cross-source themes
- **Demo caching** — 4 suggested queries permanently cached via JSON file for instant demo experience
- **Zero hallucination design** — Retrieval-focused with source citations; "I don't know" is acceptable, wrong answers are not
- **Streaming UI** — Real-time search progress and synthesis generation

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.12 |
| Embeddings | OpenAI text-embedding-3-small (prod) / BGE-M3 (local) |
| Reranking | cross-encoder/ms-marco-MiniLM-L6-v2 (optional) |
| Vector DB | Pinecone (two indexes: focus-groups, strategy-memos) |
| LLM | Gemini Flash (via OpenRouter) |
| Caching | JSON file (suggested queries only) |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Pinecone account
- OpenRouter API key (for LLM routing/synthesis)
- OpenAI API key (for embeddings in production)

### Setup

```bash
# Clone
git clone https://github.com/tanayvenkata/campaign-intel.git
cd campaign-intel

# Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Edit .env with your API keys (PINECONE_API_KEY, OPENROUTER_API_KEY, OPENAI_API_KEY)

# Frontend
cd web && npm install && cd ..
```

### Run

```bash
# Terminal 1: Backend
source venv/bin/activate
uvicorn api.main:app --reload

# Terminal 2: Frontend
cd web && npm run dev
```

Open http://localhost:3000

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Next.js Frontend (Vercel)                        │
│            Streaming search, synthesis panels, markdown export       │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend (Railway)                       │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              Demo Cache (data/demo_cache.json)                 │  │
│  │         4 suggested queries only — all else uncached           │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                │                                     │
│  ┌─────────────┐  ┌────────────┴───────────┐  ┌──────────────────┐  │
│  │ LLM Router  │  │  FocusGroup Retriever  │  │ Strategy Retriever│  │
│  │  (Gemini)   │  │  (hierarchical search) │  │ (semantic search) │  │
│  └──────┬──────┘  └────────────┬───────────┘  └─────────┬────────┘  │
│         └──────────────────────┼────────────────────────┘           │
│                                ▼                                     │
│              ┌─────────────────────────────────────┐                │
│              │  Pinecone + OpenAI Embeddings       │                │
│              │  (2 indexes: focus-groups, memos)   │                │
│              └─────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

## Corpus

The included corpus is **synthetic demo data** representing 12 races (2022-2024), 37 focus groups, and ~3,100 searchable chunks. It demonstrates the system with realistic but fictional political consulting scenarios.

## Project Structure

```
campaign-intel/
├── api/                    # FastAPI backend
│   ├── main.py            # REST endpoints + caching
│   └── schemas.py         # Pydantic models
├── web/                    # Next.js frontend
│   └── app/               # App router pages
├── scripts/
│   ├── retrieval/         # Router + retrievers
│   ├── preprocess.py      # Transcript → chunks
│   ├── embed.py           # Chunks → Pinecone
│   ├── retrieve.py        # Retrieval classes
│   └── synthesize.py      # LLM synthesis
├── political-consulting-corpus/  # Synthetic demo data
├── prompts/               # Externalized LLM prompts
└── eval/                  # Evaluation scripts
```

## Development

```bash
# Run E2E tests (requires backend running)
python eval/test_backend_e2e.py

# Frontend type-check
cd web && npm run build

# Router prompt A/B testing
./eval/router_eval/run_eval.sh
```

## License

MIT
