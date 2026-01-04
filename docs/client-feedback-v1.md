# Client Feedback: V1 Complete - Rachel Okonkwo Session

**Date:** January 2025
**Client:** Rachel Okonkwo, SVP at Meridian Strategies
**Session Type:** Discovery + Demo

---

## Overview

Practice client discovery session with Rachel Okonkwo, SVP at Meridian Strategies (mid-sized Democratic political consulting firm, ~40 staff, DC-based). Goal: pressure-test the "focus group institutional memory" concept and surface real requirements.

## Key Characters

**Rachel Okonkwo (Client)**
- SVP, 9 years at firm, leads Midwest practice
- Manages 4 associates, interfaces with candidates/campaign managers
- Skeptical but open-minded; burned by past AI vendor experiences
- Key races: Michigan 2024 (won), Ohio 2024 (lost - still bothers her), Wisconsin 2024 (won), PA Governor 2022 (won)

**Sarah (Junior Associate)**
- 3 months at firm, still learning
- Target user for V1 POC
- Pain point: spends hours in Dropbox, doesn't know what questions to ask, relies on Marcus/Rachel for context

**Marcus** - Senior associate, best focus group analyst, stretched thin
**David Chen** - Founding partner, 30 years experience, pattern recognition lives in his head

---

## Discovery Findings

### Pain Points Surfaced
(Rachel didn't volunteer these - they emerged through conversation)

1. **Focus group transcripts are a black hole** - hundreds of docs, no way to search meaningfully
2. **Institutional knowledge walks out the door** - senior people leave, pattern recognition goes with them
3. **Cycle crunch** - August-November is brutal, can't onboard fast enough
4. **Cross-race learning doesn't happen** - running 8 Midwest races, no time to synthesize
5. **Partners have intuition they can't articulate** - "this feels like Colorado 2018" but can't point to evidence

### Skepticism Addressed

| Concern | Response |
|---------|----------|
| "We tried AI transcription and it was garbage" | You're not doing transcription, you're doing semantic retrieval |
| "My job is nuance, not summaries" | System returns quotes with citations, not summaries; synthesis is optional layer |
| "Confidentiality is everything" | Local model, nothing leaves machine, can run offline |
| "We don't have time to implement new tools" | Works like Google search, Sarah can learn in a day |

### What Would Actually Excite Her

- "What did swing voters in Ohio say about immigration across 6 Midwest races" - actual semantic search
- New associates getting context without bothering seniors
- "What did we learn when our candidate got hit on crime" - rapid response support
- Speed over comprehensiveness - "good enough in 10 minutes"

---

## Technical Requirements Captured

### Output Format (Option C - confirmed)
- Group results by focus group
- Show moderator summary as header
- Display relevant quotes underneath with citations
- Include line numbers so user can find full transcript context

### Query Types Identified

| Type | Example | Complexity |
|------|---------|------------|
| Topic + location | "What did Ohio voters say about the economy?" | V1 - Simple |
| Thematic search | "Show me quotes about working-class frustration" | V1 - Simple |
| Demographic filter | "What did swing voters say about the Democratic candidate?" | V1 - Simple |
| Pattern search | "Moments where voters expressed distrust in institutions they used to support" | V1 - Advanced |
| Strategic | "What worked when our candidate got attacked on being too liberal?" | V2 - Requires strategy memos |
| Synthesis | "What went wrong in Ohio 2024 and what should we do differently?" | V2 - Requires strategy memos |

### Trust Requirements

- Must show source every time - no synthesis without citations
- One hallucination kills trust - rather say "I don't know" than make something up
- Faster than asking Marcus - or she won't use it
- Faster than Ctrl+F - or not worth learning

### Workflow Context

- **Morning prep** - reviewing before strategy calls
- **During calls** - quick context lookup
- **Rapid response** - only after tool is proven in lower-stakes situations

### Value Prop

- For juniors: Get up to speed without bothering seniors
- Real value: Junior + tool = 70% of what a senior can do → frees senior for higher-value work
- That's leverage, not just efficiency

---

## Demo Results

### Corpus Structure
- 37 focus groups across 12 races (2022-2024)
- ~37,000 transcript lines
- 9 wins, 3 losses
- Key loss races: Wisconsin 2022, Ohio 2024, Montana 2024

### Queries Tested

| Query | Result | Notes |
|-------|--------|-------|
| "What did voters in Ohio 2024 say about the economy?" | ✅ Worked well | Grouped by FG, showed demographics. Rachel: "P7 from Youngstown should've been a red flag" |
| "Show me moments where voters expressed distrust in institutions they used to support" | ✅ Exceeded expectations | 160 quotes from 35 FGs. Caught union betrayal without searching "union" |
| "What issues mattered most to swing voters in Ohio?" | ✅ Worked well | Sarah: "This is literally what Rachel was telling me last week" |
| "Tell me about Wisconsin 2024" | ✅ Worked for exploration | Broad queries important for juniors who don't know what to ask |
| "What worked when our candidate got attacked on being too liberal?" | ⚠️ Partial | Needs V2 with strategy memos |

---

## V2 Requirements (Strategy Layer)

### Current Workflow for Strategic Questions

1. Rachel asks David (founding partner) "what does this remind you of?"
2. David gives pattern match from memory ("feels like Wisconsin 2022")
3. Someone digs through Dropbox for strategy memos (inconsistently named, often not found)
4. Read "lessons learned" section, try to apply
5. Half the time, reinvent the wheel because steps 2-3 failed

### V2 Queries Rachel Wants

1. "We just picked up an Ohio Senate race with working-class district. What should we learn from past similar races?"
2. "What worked in races where we were defending against 'too liberal' attacks?"
3. "What did we learn from races we lost in the Midwest?"
4. "Show me races where working-class defection was a problem and what we tried"
5. "What's our best messaging on the economy for blue-collar voters?"

### Key Distinction

> "V1 tells me what voters said. V2 tells me what we learned. V1 is research. V2 is institutional knowledge."

### Data Needed

- Strategy memos (post-mortems, lessons learned, what worked/didn't)
- Currently exist but inconsistent format, buried in Dropbox

---

## Business Terms Discussed

### Pricing Shared

| Usage Level | Queries/day | Monthly Cost |
|-------------|-------------|--------------|
| Light (testing) | 10 | ~$1-3 |
| Moderate (internal use) | 50 | ~$5-15 |
| Heavy (production) | 200 | ~$20-60 |

- Uses Claude 3 Haiku (cheapest)
- Heavy lifting (embeddings, reranking) runs locally

### Engagement Structure

- **POC:** 2 days to build, 1 day for Sarah to learn
- **V2:** TBD, needs proposal
- **Ongoing:** Consultant relationship possible, pricing TBD

### Rachel's Ask

- One-page proposal: V2 scope, timeline, cost
- Confidentiality in writing before real transcripts go in

---

## Client Feedback

> "You listened more than you pitched. That's rare."

> "I appreciate that you didn't try to oversell me. Most vendors would've promised me the moon by now."

> "The fact that you kept coming back to 'simple' and 'what Sarah actually needs' - that tells me you're actually listening."

**Sarah:** "You actually listened to what she was saying... that's real. That's my life."

---

## Next Steps

1. Sarah tests V1 demo on real queries, reaches out with questions
2. Tanay sends one-page proposal for V2
3. If V1 proves out with Sarah, schedule V2 conversation
4. Rachel will pitch to David (founding partner) if V2 proposal is solid
