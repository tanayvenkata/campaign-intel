# V1 POC Requirements

**Source:** Client conversation with Rachel (Managing Partner)
**Date:** December 2024
**Primary User:** Sarah (junior analyst)

---

## Context

Rachel needs a tool that lets junior analysts (Sarah) access institutional knowledge from past focus groups without constantly pulling in senior staff (Marcus). The goal is leverage: if Sarah can do 70% of Marcus's research work with this tool, Marcus is freed up for higher-value work.

---

## Requirements Summary

| Dimension | Requirement |
|-----------|-------------|
| **Starting scope** | "What did voters say about X" queries - the bread and butter |
| **Output format** | Raw quotes + citations + link to full transcript. Synthesis okay but verification required |
| **Trust threshold** | Zero hallucination tolerance. "I don't have enough information" > confident wrong answer |
| **Speed** | Faster than asking Marcus (the senior analyst) |
| **Workflow** | Morning prep before strategy calls. Low-stakes first, rapid response later |
| **Success metric** | Sarah (junior) can do 70% of Marcus's research work |
| **Proof of concept** | Nail the simple case, earn the advanced features |

---

## Query Types (Prioritized)

### V1: "What did voters say about X"
Day-to-day bread and butter. Sarah needs quick access to what voters said about:
- Economy, inflation, cost of living
- Immigration
- Candidate character
- Healthcare
- Any issue that comes up

**This is the starting point.**

### V2: "Find me races similar to Y"
Pattern-matching across the corpus. Used by Rachel and David (senior partners) for strategic planning.

Example: "New client is a Democratic challenger for Ohio Senate 2026. What similar races have we run?"

### V3: "What worked when we got hit on X"
Rapid response / crisis mode. September, debate prep, when attacks land.

Example: "Client just got hit on crime. What responses tested well in past races?"

**V2 and V3 are earned features - prove V1 first.**

---

## Output Requirements

### Mandatory
1. **Raw quotes** - Actual participant quotes from transcripts
2. **Citations** - Which focus group, which race, participant ID
3. **Link to source** - Ability to pull up full transcript for context

### Optional
- Synthesis/summary on top of quotes
- But user must be able to verify everything

### Anti-pattern
- Synthesized answer without showing sources = untrustworthy
- Confident wrong answer = tool is dead to them

---

## Trust & Confidence

**Zero tolerance for hallucination.** Rachel was explicit:

> "One bad hallucination and I'm done. If it confidently tells Sarah something that's wrong, and she repeats it to me or worse, to a client - that's it. Trust is gone."

Design implications:
- If retrieval confidence is low, say so
- "I don't have enough information" > making something up
- Consider showing confidence scores or thresholding results

---

## Workflow Integration

**When:** Morning prep before strategy calls

**How:** Sarah reviewing what she needs to know before a call. Quick context lookup if something comes up during the call.

**Later:** Rapid response (high-pressure, needs proven trust first)

---

## Success Criteria

1. Sarah uses it regularly
2. Actually saves time vs. asking Marcus
3. Rachel doesn't hear complaints
4. No hallucination incidents

If those are met → conversation about advanced features (pattern-matching, cross-race synthesis, partner-level tools)

---

## Design Implications

1. **Retrieval-focused, not synthesis-focused** - Surface relevant excerpts with clear citations
2. **Confidence calibration matters** - Threshold results or show confidence scores
3. **Link to source is mandatory** - Every result points back to transcript
4. **Speed is critical** - Faster than the human workaround (asking Marcus)
5. **Start simple** - "What did swing voters say about immigration?" → relevant quotes with citations

---

## V1 MVP Spec

**Input:** Natural language query about what voters said about a topic

**Output:**
- Relevant quotes from focus group transcripts
- For each quote:
  - Participant context (demographics, political lean)
  - Focus group source (race, location, date)
  - Link/reference to full transcript
- Optional: Brief synthesis if multiple quotes returned

**Example:**

Query: "What did swing voters say about immigration?"

Response:
```
Found 8 relevant quotes across 4 focus groups:

**Race 007: Ohio Senate 2024 - Youngstown Working Class**
> "Immigration wasn't even on my radar until gas hit $4. Now I'm thinking - who's
> competing for these jobs?" - P6 (M, 41, warehouse worker, independent)
[View full transcript: fg-003-youngstown-working-class.md]

**Race 005: Arizona Governor 2022 - Maricopa Suburbs**
> "I live 100 miles from the border. It's not abstract to me." - P3 (F, 52,
> real estate agent, Romney→Biden voter)
[View full transcript: fg-001-maricopa-suburbs.md]

...
```

---

## Raw Conversation Notes

*Rachel, checking watch at the door:*

> "On the queries. Honestly? It's all three of those, but they're different situations. Day-to-day, Sarah needs 'what did voters say about X' - economy, immigration, candidate character, whatever the issue is. That's the bread and butter."

> "Output format. I need to see the source. Every time. If this thing gives me a synthesized answer without showing me exactly where it came from, I won't trust it."

> "What kills it? One bad hallucination and I'm done."

> "If it's slower than me just asking Marcus, she won't use it."

> "The real value is - can Sarah, with this tool, give me the kind of context that only Marcus can give me right now? Because Marcus is stretched thin."

> "Show me it works on the simple case first."
