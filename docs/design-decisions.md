# Design Decisions & UX Ideas

This document captures architectural and UX decisions made during development, especially ideas for future phases.

---

## V1 Retrieval Architecture

### Per-Focus-Group Retrieval (Implemented)

**Problem:** Global top-k retrieval causes one focus group to dominate results when content is similarly relevant across groups.

**Solution:** Query each focus group separately, return grouped results.

```
Query → Router selects FGs → Query each FG independently → Return {fg: [chunks]}
```

**Why this makes sense:**
- Output format is grouped by FG (mod notes + quotes per group)
- Focus groups are natural boundaries - same quote from different demographics has different meaning
- Matches how analysts think: "What did EACH group say about X?"
- Prevents embedding similarity from hiding relevant content

**Tradeoffs:**
- Router accuracy becomes more critical (it's a gate, not a hint)
- Slight latency increase (parallelizable)
- Need to tune score threshold

---

## UX Ideas for Future Phases

### 1. User-Controlled Relevance Threshold

**Concept:** Let users adjust how strict the filtering is.

```
Relevance: [====|======]
           More results ← → Stricter matches
```

**Implementation:**
- Default threshold from testing (e.g., 0.75)
- Simple slider or dropdown: "Show more / Show less"
- Mental model: "Lower = cast wider net, Higher = only best matches"

**Why:** Users can self-serve when they feel results are too few/too many without understanding embeddings.

---

### 2. Transparent Router Decisions

**Concept:** Show users which focus groups were searched and why.

**UI Example:**
```
┌─────────────────────────────────────────────────────┐
│ Query: "What did Ohio voters say about the economy?"│
├─────────────────────────────────────────────────────┤
│ Searched focus groups:                              │
│   ✓ Ohio 2024 - Cleveland Suburbs                   │
│   ✓ Ohio 2024 - Columbus Educated                   │
│   ✓ Ohio 2024 - Youngstown Working Class            │
│                                                     │
│ Why: Query mentions "Ohio" → filtered to Ohio 2024  │
│                                                     │
│ [+ Add more focus groups]                           │
└─────────────────────────────────────────────────────┘
```

**Why:**
- Builds trust through transparency
- User can catch router mistakes
- Analyst stays in control

---

### 3. Manual Focus Group Override

**Concept:** Let users add/remove focus groups from search.

**Flow:**
1. User runs query
2. System shows which FGs were searched
3. User notices relevant FG is missing
4. User clicks "+ Add focus group" → selects from list
5. System re-runs retrieval with updated FG list

**Why:**
- Human-in-the-loop for when AI is wrong
- Analysts have domain knowledge system doesn't
- Empowers without requiring technical understanding

---

### 4. Explain Filtering Logic

**Concept:** Natural language explanation of how query was interpreted.

**Examples:**
- "Showing Ohio 2024 focus groups because your query mentioned 'Ohio'"
- "Filtered to working-class participants based on 'blue collar' in query"
- "No location filter applied - searching all focus groups"

**Why:**
- User understands system behavior
- Can rephrase query if interpretation is wrong
- Reduces "why didn't it find X?" confusion

---

## Technical Decisions

### Score Threshold

| Value | Behavior | Use Case |
|-------|----------|----------|
| 0.70 | Loose - more results, some noise | Exploratory queries |
| 0.75 | Balanced (default) | Most queries |
| 0.80 | Strict - fewer, higher quality | Precise queries |
| 0.85+ | Very strict - may miss relevant | Needle-in-haystack |

**Decision:** Default to 0.75, allow user adjustment.

### Max Chunks Per Focus Group

**Decision:** Cap at 5 per FG to prevent any single group from overwhelming.

**Rationale:**
- 3 FGs × 5 chunks = 15 max results (manageable)
- If FG has < 5 relevant chunks, return fewer
- Ensures diversity without artificial padding

### Reranking Strategy

**Decision:** Rerank within each focus group, not globally.

**Rationale:**
- Preserves per-FG diversity
- Cross-encoder picks best chunks within each group
- Global rerank would re-introduce dominance problem

---

## Client Context (Rachel's Feedback)

> "For the POC - for Sarah - keep it simple. She needs to answer questions like:
> - 'What did voters in Ohio 2024 say about the economy?'
> - 'Show me focus group quotes about working-class frustration.'
> - 'What did swing voters say about the Democratic candidate?'
>
> That's retrieval. That's what she actually needs to get up to speed before a call."

**V1 Scope:**
- Simple quote retrieval
- Grouped by focus group
- Zero hallucination tolerance
- Transparency over magic

**V2 Scope (future):**
- Semantic inference ("distrust in institutions" → party abandonment quotes)
- Strategy memo integration
- Cross-race synthesis
- Partner-level analytical queries

---

## Open Questions for Future

1. **Should threshold be per-query-type?** Exploratory vs precise queries might need different defaults.

2. **How to handle "no results"?** Show nothing? Suggest broadening? Auto-fallback to global search?

3. **Caching router decisions?** Same query pattern → same FG selection. Worth caching?

4. **Feedback loop?** If user manually adds FGs, should that inform future router behavior?
