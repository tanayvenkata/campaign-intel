# Focus Group Search System - Manual QA Testing Prompt

## Context

You are testing a political consulting search system that retrieves two types of content:

1. **Focus Group Quotes** - Direct quotes from voter focus groups (conversational, emotional)
2. **Campaign Lessons** - Strategy memo excerpts analyzing what worked/failed in past races (analytical, formal)

The system uses an LLM router to decide what content type to return:
- `quotes` - Focus group quotes only
- `lessons` - Strategy memos only
- `both` - Both types (for queries that benefit from voter voice + strategic analysis)

## System Under Test

**URL:** http://localhost:3000

**Expected UI Layout:**
1. Search bar at top
2. Stats bar showing: X quotes, Y lessons, Z focus groups, latency
3. **Campaign Lessons section** (collapsed by default, amber/yellow styling) - shows strategy memo insights grouped by race
4. **Cross-Focus Group Analysis** panel - for synthesizing across multiple sources
5. **Focus Group cards** - individual cards per focus group with quotes

---

## Test Queries & Expected Results

### Test 1: Race-Specific Loss Analysis
**Query:** "What went wrong in Ohio 2024?"

**Expected Behavior:**
- Content type: `both` or `lessons`
- Should return: Ohio 2024 strategy memo (race-007)
- Key sections to find: "What Failed", "The Collapse: What Happened"
- If quotes present: Ohio focus group quotes about voter frustration

**Record:**
- [ ] Campaign Lessons section appeared?
- [ ] Ohio 2024 race visible?
- [ ] Summary mentions specific failures?
- [ ] Focus group quotes (if any) are from Ohio?
- Latency: ___ms
- Total quotes: ___
- Total lessons: ___

---

### Test 2: Thematic Loss Analysis
**Query:** "Why did our economic messaging fail?"

**Expected Behavior:**
- Content type: `lessons` or `both`
- Should return: Wisconsin 2022 (race-003) and Ohio 2024 (race-007)
- Key insight: "corporate greed" messaging scored 1.5/5 in Wisconsin
- Should NOT return winning races prominently

**Record:**
- [ ] Multiple races returned?
- [ ] Wisconsin 2022 mentioned?
- [ ] Ohio 2024 mentioned?
- [ ] Specific failure reasons cited?
- Latency: ___ms

---

### Test 3: Ignored Warnings
**Query:** "What warning signs did focus groups show that we ignored?"

**Expected Behavior:**
- Content type: `both` (needs FG quotes + strategy analysis)
- Should return: Races where focus group warnings were documented but ignored
- Key sections: "What the Focus Groups Told Us (And We Didn't Fix)"

**Record:**
- [ ] Both Campaign Lessons AND Focus Group quotes returned?
- [ ] Strategy memos reference focus group findings?
- [ ] Quotes show the actual warnings?
- Latency: ___ms

---

### Test 4: What Worked (Win Analysis)
**Query:** "What messaging worked with working-class voters?"

**Expected Behavior:**
- Content type: `both` or `lessons`
- Should return: Michigan 2024 (race-009), Pennsylvania races
- Should prioritize WINNING races
- Key insight: authentic biography, specific policy (not generic attacks)

**Record:**
- [ ] Winning races prioritized?
- [ ] Michigan 2024 appears?
- [ ] Specific tactics mentioned (not vague)?
- [ ] If quotes present, working-class voters quoted?
- Latency: ___ms

---

### Test 5: Specific Message Failure
**Query:** "Why did corporate greed messaging fail?"

**Expected Behavior:**
- Content type: `lessons`
- Should return: Wisconsin 2022 (race-003)
- Key insight: "fighting corporate greed" scored 1.5/5 with working-class voters
- Should explain WHY it failed (too generic, no credibility)

**Record:**
- [ ] Wisconsin 2022 returned?
- [ ] Specific score mentioned (1.5/5)?
- [ ] Explanation of failure included?
- Latency: ___ms

---

### Test 6: State-Specific Loss
**Query:** "What went wrong in Montana?"

**Expected Behavior:**
- Content type: `both` or `lessons`
- Should return: Montana 2024 (race-008)
- Should explain loss despite strong incumbent

**Record:**
- [ ] Montana 2024 returned?
- [ ] Loss explanation provided?
- [ ] If quotes, Montana voters represented?
- Latency: ___ms

---

### Test 7: Comparative Analysis
**Query:** "How to improve Wisconsin performance?"

**Expected Behavior:**
- Content type: `lessons`
- Should return: Wisconsin 2022 (loss) AND Wisconsin 2024 (win)
- Key insight: What changed between the two races

**Record:**
- [ ] Both Wisconsin races returned?
- [ ] 2022 loss vs 2024 win contrast visible?
- [ ] Specific improvements noted?
- Latency: ___ms

---

### Test 8: Voter Segment Query
**Query:** "What messages worked with Latino voters?"

**Expected Behavior:**
- Content type: `both`
- Should return: Arizona (race-005), Nevada (race-006)
- Should include focus group quotes from Latino participants

**Record:**
- [ ] Southwest races returned?
- [ ] Latino-specific insights?
- [ ] If quotes, Latino participants quoted?
- Latency: ___ms

---

### Test 9: Forward-Looking Strategy
**Query:** "What should we do differently in 2026?"

**Expected Behavior:**
- Content type: `lessons`
- Should return: Ohio 2024 recommendations
- Key sections: "Lessons for Ohio 2026", "What 2026 Candidate Must Do Differently"

**Record:**
- [ ] Future recommendations returned?
- [ ] Actionable advice (not just analysis)?
- [ ] Ohio 2026 specifically mentioned?
- Latency: ___ms

---

### Test 10: Pure Focus Group Query
**Query:** "What did Ohio voters say about the economy?"

**Expected Behavior:**
- Content type: `quotes` (pure FG query)
- Should return: Ohio focus group quotes about economy
- Should NOT return strategy memos prominently

**Record:**
- [ ] Focus group quotes returned?
- [ ] Ohio voters specifically?
- [ ] Economy topic covered?
- [ ] Campaign Lessons section empty or minimal?
- Latency: ___ms

---

## Evaluation Criteria

### Pass Criteria:
1. **Routing Accuracy**: Correct content type returned (quotes vs lessons vs both)
2. **Relevance**: Top results are directly relevant to query
3. **Race Coverage**: Expected races appear in results
4. **No Hallucination**: All content traceable to source (no made-up quotes/insights)
5. **Latency**: < 3000ms for search, < 5000ms with synthesis

### Fail Criteria:
1. Wrong content type (e.g., returning wins for "what went wrong")
2. Missing expected races entirely
3. Generic/vague summaries without specific insights
4. Latency > 10000ms
5. Empty results for valid queries

---

## Summary Table

| Test | Query | Expected Type | Expected Races | Pass/Fail | Notes |
|------|-------|---------------|----------------|-----------|-------|
| 1 | What went wrong in Ohio 2024? | both/lessons | race-007 | | |
| 2 | Why did our economic messaging fail? | lessons | race-003, race-007 | | |
| 3 | What warning signs did focus groups show that we ignored? | both | race-003, race-007 | | |
| 4 | What messaging worked with working-class voters? | both/lessons | race-009 | | |
| 5 | Why did corporate greed messaging fail? | lessons | race-003 | | |
| 6 | What went wrong in Montana? | both/lessons | race-008 | | |
| 7 | How to improve Wisconsin performance? | lessons | race-003, race-012 | | |
| 8 | What messages worked with Latino voters? | both | race-005, race-006 | | |
| 9 | What should we do differently in 2026? | lessons | race-007 | | |
| 10 | What did Ohio voters say about the economy? | quotes | Ohio FGs | | |

---

## Instructions for Tester

1. Open http://localhost:3000
2. For each test query:
   - Enter the query in the search bar
   - Wait for results to load
   - Check if Campaign Lessons section appears (expand it if collapsed)
   - Check Focus Group cards below
   - Record observations in the checklist
   - Note any issues or unexpected behavior
3. After all tests, fill in the summary table
4. Report any patterns (e.g., "routing always returns 'both'" or "latency spikes on X queries")
