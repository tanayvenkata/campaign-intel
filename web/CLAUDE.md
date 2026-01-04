# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This is the Next.js frontend for the focus group search system. See `../CLAUDE.md` for full project context including API endpoints and data flow.

## Development Commands

```bash
npm install          # First-time setup
npm run dev          # Dev server (port 3000) - requires API on port 8000
npm run build        # Production build (includes TypeScript type-checking)
npm run lint         # ESLint
```

## Architecture

Single-page app with streaming search and multi-level synthesis.

```
page.tsx                    # Main search page, orchestrates all state
├── useStreamingSearch      # Hook: NDJSON streaming from /search/stream
├── SearchResults           # Results container, manages synthesis state
│   ├── QuoteBlock          # Individual quote with participant metadata
│   └── SynthesisPanel      # Deep synthesis per focus group
├── StepLoader              # Animated progress during search
└── EmptyState              # No results guidance
```

### State Flow

1. **Search**: `useStreamingSearch` streams NDJSON status events → `StepLoader` shows progress
2. **Light summaries**: Auto-generated on results load (staggered 200ms per FG)
3. **Macro synthesis**: User selects FGs → clicks "Synthesize Selected" → waits for light summaries → streams cross-FG analysis
4. **Deep synthesis**: Per-FG "Deep Synthesis" button in `SynthesisPanel`

### Key Patterns

- **Streaming**: All synthesis endpoints use `ReadableStream` for progressive rendering
- **Summary queue**: Macro synthesis is queued until all selected FG light summaries complete
- **Collapsible quotes**: Collapsed by default to reduce cognitive load
- **Export**: `exportMarkdown.ts` generates downloadable `.md` report with all synthesis

## API Configuration

`app/config/api.ts` centralizes all endpoints. For production, set `NEXT_PUBLIC_API_URL`.

```typescript
import { ENDPOINTS } from './config/api';
// ENDPOINTS.search, ENDPOINTS.synthesizeLight, etc.
```

## Types

`app/types.ts` defines the API response shapes:
- `RetrievalChunk` - Individual quote with metadata (participant, source_file, line_number)
- `GroupedResult` - Focus group with its chunks and metadata
- `SearchResponse` - Full search response with stats
