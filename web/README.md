# Campaign Intel Frontend

Next.js frontend for the Campaign Intel search system.

## Setup

```bash
npm install
npm run dev
```

Requires the backend running on port 8000:
```bash
# From project root
uvicorn api.main:app --reload
```

Open http://localhost:3000

## Structure

```
app/
├── page.tsx              # Main search page
├── components/
│   ├── SearchResults.tsx # Results container
│   ├── QuoteBlock.tsx    # Individual quote display
│   ├── SynthesisPanel.tsx# Per-FG synthesis
│   └── StrategySection.tsx# Strategy lessons display
├── hooks/
│   ├── useStreamingSearch.ts  # NDJSON streaming
│   └── useUnifiedSearch.ts    # Unified search API
└── utils/
    └── exportMarkdown.ts # Export results to .md
```

## Key Features

- Streaming search with progress indicators
- Auto-generated light summaries per focus group
- Deep synthesis on demand
- Cross-FG theme analysis
- Markdown export
