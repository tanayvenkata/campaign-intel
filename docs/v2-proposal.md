# V2 Proposal: Strategy Memo Layer

**For:** Rachel Okonkwo, Meridian Strategies
**From:** Tanay Venkata
**Date:** January 2025

---

## The Problem V2 Solves

V1 answers: *"What did voters say?"*
V2 answers: *"What did we learn?"*

Right now, when you pick up a new race, the pattern-matching lives in David's head and the lessons learned are buried in Dropbox. V2 makes that institutional knowledge searchable.

---

## What V2 Enables

| Query Type | Example |
|------------|---------|
| Race pattern matching | "We just picked up an Ohio Senate race with a working-class district. What should we learn from past similar races?" |
| Attack response playbook | "What worked in races where we were defending against 'too liberal' attacks?" |
| Loss analysis | "What did we learn from races we lost in the Midwest?" |
| Messaging lookup | "What's our best messaging on the economy for blue-collar voters?" |

Every answer cites the source memo. No synthesis without attribution.

---

## What I Need From You

**Strategy memos** - post-mortems, lessons learned, what worked/didn't. Whatever format they're in now is fine; I'll handle the parsing. Estimate: 10-20 docs to start, covering your key Midwest races.

---

## Scope

1. **Ingest strategy memos** - parse whatever format you have, chunk by lesson/insight
2. **Unified search** - query returns both voter quotes (V1) AND strategic lessons (V2)
3. **Cross-reference** - link lessons to the focus group evidence that supports them
4. **Same UI** - Sarah's workflow doesn't change, just richer results

**Out of scope for V2:** Auto-generating strategy memos, competitor analysis, polling data integration.

---

## Timeline

- **Week 1:** Receive memos, build ingestion pipeline, index alongside transcripts
- **Week 2:** Extend retrieval to surface lessons, test with your real queries
- **Week 3:** Sarah + Rachel test, iterate based on feedback

Usable prototype in 2 weeks. Polished version in 3.

---

## Cost

**Build:** Flat project fee, TBD based on memo volume and iteration cycles. Ballpark: 15-25 hours of work.

**Run:** Same as V1 (~$5-60/month depending on usage). Strategy memos add minimal cost since the heavy lifting is local.

---

## Confidentiality

Happy to sign whatever you need. The system runs locally - nothing leaves your machine unless you choose to deploy it. Can demo air-gapped operation if that helps.

---

## Next Step

Send me 3-5 strategy memos (can be redacted/anonymized for now). I'll show you a working prototype of V2 search on that corpus before we commit to the full build.

---

*Questions? I'd rather scope this right than scope it fast.*
