# Political Consulting Focus Group Corpus

A synthetic dataset representing institutional knowledge from political consulting focus groups. Designed to demonstrate semantic search and pattern-matching across qualitative research archives.

## Purpose

Political consulting firms run hundreds of focus groups over years, but that qualitative insight often gets buried. This corpus demonstrates a tool that surfaces institutional knowledge:

> "New client is a Democratic challenger for Ohio Senate 2026. Show me what we've learned from similar races."

## Corpus Overview

| Metric | Count |
|--------|-------|
| Races | 3 |
| Focus Groups | 9 |
| Strategy Memos | 3 |
| Total Transcript Lines | ~9,000 |

### Races Included

| Race ID | State | Office | Year | Outcome | Key Learning |
|---------|-------|--------|------|---------|--------------|
| 001 | Michigan | Governor | 2022 | Win (+3.2%) | Abortion + specific economic policies |
| 002 | Pennsylvania | Senate | 2022 | Win (+4.8%) | Candidate quality and hometown roots |
| 003 | Wisconsin | Senate | 2022 | Loss (-1.1%) | Economic messaging failure |

## Directory Structure

```
political-consulting-corpus/
├── races/
│   ├── race-001-michigan-gov-2022/
│   │   ├── metadata.json
│   │   ├── focus-groups/
│   │   │   ├── fg-001-detroit-suburbs.md
│   │   │   ├── fg-002-grand-rapids.md
│   │   │   └── fg-003-swing-voters-statewide.md
│   │   └── strategy-memo.md
│   ├── race-002-pennsylvania-senate-2022/
│   │   └── [same structure]
│   └── race-003-wisconsin-senate-2022/
│       └── [same structure]
├── race-index.json
└── README.md
```

## File Formats

### Focus Group Transcripts (Markdown)

Each transcript includes:
- Header with race, location, date, moderator, participant demographics
- Participant profiles (10 per group)
- Timestamped discussion sections
- Message testing with numerical scores
- Moderator notes with key themes and recommendations
- Verbatim quotes flagged for campaign use

### Metadata (JSON)

Race-level information including:
- Candidate and opponent details
- Demographics and key constituencies
- Key issues
- Outcome and margin
- Focus group count and summary

### Strategy Memos (Markdown)

Post-race analysis including:
- What worked / What didn't work
- Key learnings for future races
- Voter segment analysis
- Geographic insights
- Recommendations

### Race Index (JSON)

Filterable index of all races with:
- Basic race information
- Focus group metadata
- Themes for cross-corpus search
- Example queries

## Key Themes Across Corpus

1. **Economic Messaging**: How cost of living, inflation, and jobs messaging performed
2. **Reproductive Rights**: Post-Dobbs abortion messaging effectiveness
3. **Candidate Authenticity**: Working-class backgrounds vs. elite perception
4. **Union Voters**: Persuadability and cross-pressures
5. **Message Specificity**: Generic "fight for families" vs. "$35 insulin cap"
6. **Suburban Voters**: Movement patterns in WOW, collar counties, etc.

## Semantic Search Examples

The corpus is designed for semantic search to outperform keyword search:

| Query | Returns |
|-------|---------|
| "economic anxiety" | Discussions of inflation, cost of living, "can't afford groceries," "prices through the roof" |
| "abortion messaging" | Freedom framing, healthcare decisions, Dobbs reactions |
| "working class credibility" | Biography discussions, "one of us," manufacturing roots |
| "what went wrong in losses" | Wisconsin strategy memo, Fox Valley focus group |

## Demo Scenarios

### 1. Similar Race Lookup

> "Democratic challenger for Ohio Senate 2026 - what should they know?"

Returns: Michigan Gov 2022 and Wisconsin Senate 2022 (both Midwest, non-incumbent Democrat)

### 2. Theme Pattern

> "How did economic messaging perform across races?"

Returns: Message testing sections showing generic populism failing, specific policies succeeding

### 3. Learning from Losses

> "What did we learn from races we lost?"

Returns: Wisconsin strategy memo with explicit failure analysis

### 4. Voter Segment Deep Dive

> "How do union voters behave under economic pressure?"

Returns: Pittsburgh focus group (solid D), Fox Valley focus group (persuadable to R)

## Data Notes

- All candidate names, participant profiles, and focus group details are fictional
- Geographic and demographic details are realistic for demonstration purposes
- Transcripts reflect authentic focus group dynamics (interruptions, contradictions, tangents)
- Strategy memos include candid analysis including self-criticism

## Expansion

This is Phase 1 of a planned 12-race corpus. Future additions will include:
- 2022 races: Georgia Senate, Arizona Governor, Nevada Senate
- 2024 races: Ohio Senate, Montana Senate, Michigan Senate, Pennsylvania Senate, North Carolina Governor, Wisconsin Senate

---

*Generated for demo purposes. Not real focus group data.*
