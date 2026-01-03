# Client Notes & Email Thread

Running log of client questions, answers, and decisions.

---

## 2024-12 - Initial Requirements (Rachel, in-person)

**Source:** Conversation as Rachel was leaving for a call

### Key Requirements
- **Starting scope:** "What did voters say about X" queries
- **Output format:** Raw quotes + citations + link to full transcript
- **Trust threshold:** Zero hallucination tolerance
- **Speed:** Faster than asking Marcus
- **Workflow:** Morning prep before strategy calls
- **Success metric:** Sarah can do 70% of Marcus's research work
- **Proof of concept:** Nail simple case first, earn advanced features

### Quotes
> "One bad hallucination and I'm done."

> "If it's slower than me just asking Marcus, she won't use it."

> "Show me it works on the simple case first."

---

## 2024-12 - Corpus Structure Clarification (Email)

**From:** Tanay
**To:** Rachel

> Looked through the focus group archives. Before we build retrieval, quick clarification on what you'd want returned:
>
> **The corpus has two layers per focus group:**
>
> 1. **Raw dialogue** - What participants actually said
> 2. **Moderator notes** - Human-written summary at the end of each transcript
>
> **Question:** When Sarah searches "what did voters say about working-class defection" - do you want:
> - A) Raw quotes only
> - B) Moderator summaries
> - C) Both - Quotes first, summary as context
>
> Also worth noting: if this tool works, future focus groups might skip the manual moderator notes entirely. Should we design assuming raw transcripts only?
>
> Strategy memos - useful for V2?

---

**From:** Rachel
**To:** Tanay

> Good questions. Quick answers:
>
> **C - Both.** Quotes first, summary as context. I need to see the actual words - that's where the insight lives. But the moderator notes help me know if something was a big moment or a throwaway comment. Don't skip either.
>
> **On designing for raw only** - don't assume that yet. Marcus still writes good notes and I'm not ready to change our process mid-cycle. Build for what we have now.
>
> **Strategy memos** - yes, V2. But don't forget about them. That's where the real lessons are.
>
> Sarah's in a meeting but I've got 20 minutes. Show me what you've got.

---

## 2024-12 - Results Display Clarification (In-person)

**Context:** Clarifying what "summary as context" means

**Question:** When you said 'summary as context' - do you want moderator notes as:
- A) Metadata tags enriching quotes
- B) Separate searchable results ranked below quotes
- C) Header when grouping quotes by focus group

**Rachel's Answer:**

> It's C. That's what I want.
>
> Here's why: when I'm looking at results, I need to know which focus group this came from. Youngstown is different from Columbus suburbs. Union workers are different from suburban moms. If you just give me floating quotes without that context, I can't interpret them correctly.
>
> So group it by focus group, give me the moderator summary as a header so I know what that session was about, then show me the relevant quotes underneath. That way I can see "oh, this is from the Youngstown group where we were already losing - that's different from if the same sentiment showed up in a swing suburb."
>
> And definitely not B. I don't want moderator notes competing with quotes in my results. The notes are about the quotes - they shouldn't be ranked alongside them like they're the same thing.

---

## 2024-12 - Scope Clarification (In-person)

**Context:** Discussing whether to build for V1 simple queries or V2 synthesis

**Rachel's clarification:**

> "What went wrong and what should we do differently" - that's what I *wish* I could ask. That's the V2 dream. That requires the strategy memos, synthesis across multiple focus groups, and honestly some level of reasoning that's probably harder to get right.
>
> For the POC - for Sarah - keep it simple. She needs to answer questions like:
> - "What did voters in Ohio 2024 say about the economy?"
> - "Show me focus group quotes about working-class frustration."
> - "What did swing voters say about the Democratic candidate?"
>
> That's retrieval. That's the focus group transcripts. That's what she actually needs to get up to speed before a call.
>
> But... don't throw away the strategy memo idea. If the simple retrieval works, the *next* thing I'd want is exactly that synthesis layer.
>
> **For POC, index the transcripts only. Show me it works. Then we talk about adding strategy memos for V2.**

**Test queries for POC:**
1. "What did voters in Ohio 2024 say about the economy?"
2. "Show me moments where voters expressed distrust in institutions they used to support."

Rachel's note on query #2: "That's testing whether your system catches meaning, not just keywords."

---

## Decisions Log

| Decision | Answer | Source |
|----------|--------|--------|
| Raw quotes vs. summaries | Both - quotes first, summary as context | Rachel email |
| How to show context | Group by focus group, moderator summary as header | Rachel in-person |
| Index moderator notes? | No - context only, not searchable | Rachel in-person |
| Design for raw-only future? | No - build for current process | Rachel email |
| Strategy memos | V2 - don't index for POC | Rachel in-person |
| POC scope | Transcripts only, simple retrieval | Rachel in-person |
| Hallucination handling | "I don't know" > wrong answer | Rachel in-person |
| Citation requirement | Mandatory - every result needs source link | Rachel in-person |
