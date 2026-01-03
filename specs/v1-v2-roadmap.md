# V1 vs V2 Roadmap

## V1 (POC) - Current Build

**Scope:** Simple quote retrieval for Sarah (junior analyst)

**What we're building:**
- Preprocess transcripts → dialogue chunks
- Per-utterance chunking with metadata
- Focus group metadata (includes moderator notes for display)
- Basic retrieval: "What did voters say about X"

**Test queries:**
1. "What did voters in Ohio 2024 say about the economy?"
2. "Show me moments where voters expressed distrust in institutions they used to support."

---

## V2 (Future) - Synthesis & Analysis

**Scope:** Cross-race analysis, lessons learned for Rachel/partners

**What to add:**
- Strategy memo preprocessing (already in corpus, just need to chunk)
- Query routing ("Is this a quotes query or analysis query?")
- LLM synthesis layer for cross-race patterns

**V2 queries:**
- "What went wrong in Ohio 2024 and what should we do differently?"
- "What patterns do we see across races we lost?"
- "What did we learn about working-class messaging?"

---

## V1 → V2 Upgrade Path

| Component | V1 | V2 | Change |
|-----------|----|----|--------|
| Transcript chunks | ✅ | ✅ | None |
| Focus group metadata | ✅ | ✅ | None |
| Strategy memo chunks | ❌ | ✅ | **Add** |
| Query routing | Simple | Smart | **Minor update** |
| Synthesis layer | ❌ | ✅ | **New component** |

**Key point:** V1 → V2 is additive. No rebuild required.

---

## Strategy Memo Chunking (for V2)

When we get to V2, strategy memos should be chunked by section:
- "What Worked" → one chunk
- "What Failed" → one chunk
- "Lessons for Future" → one chunk

Different from transcripts (per-utterance) because memos are analytical, not dialogue.

---

## Rachel's Words

> "For POC, index the transcripts only. Show me it works. Then we talk about adding strategy memos for V2."

> "What went wrong and what should we do differently - that's the V2 dream."
