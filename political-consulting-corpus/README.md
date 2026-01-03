# Political Consulting Focus Group Corpus

A synthetic dataset representing institutional knowledge from political consulting focus groups. Designed to demonstrate semantic search and pattern-matching across qualitative research archives.

## Purpose

Political consulting firms run hundreds of focus groups over years, but that qualitative insight often gets buried. This corpus demonstrates a tool that surfaces institutional knowledge:

> "New client is a Democratic challenger for Ohio Senate 2026. Show me what we've learned from similar races."

## Corpus Overview

| Metric | Count |
|--------|-------|
| Races | 12 |
| Focus Groups | 37 |
| Strategy Memos | 12 |
| Total Transcript Lines | ~37,000 |
| Years Covered | 2022-2024 |
| Wins | 9 |
| Losses | 3 |

### Races Included

| Race ID | State | Office | Year | Outcome | Key Learning |
|---------|-------|--------|------|---------|--------------|
| 001 | Michigan | Governor | 2022 | Win (+3.2%) | Abortion + specific economic policies |
| 002 | Pennsylvania | Senate | 2022 | Win (+4.8%) | Candidate quality and hometown roots |
| 003 | Wisconsin | Senate | 2022 | **Loss (-1.1%)** | Economic messaging failure - generic populism fails |
| 004 | Georgia | Senate | 2022 | Win (+2.8%) | Character contrast and candidate quality |
| 005 | Arizona | Governor | 2022 | Win (+0.5%) | Election denial as disqualifying, McCain Republicans |
| 006 | Nevada | Senate | 2022 | Win (+0.8%) | Union turnout machine, Culinary Union |
| 007 | Ohio | Senate | 2024 | **Loss (-6.2%)** | Working-class defection, "what have you done lately?" |
| 008 | Montana | Senate | 2024 | **Loss (-4.8%)** | Personal brand limits in nationalized environment |
| 009 | Michigan | Senate | 2024 | Win (+4.2%) | Working-class authenticity beats CEO credentials |
| 010 | Pennsylvania | Senate | 2024 | Win (+3.1%) | Healthcare costs message, pharma executive liability |
| 011 | North Carolina | Governor | 2024 | Win (+8.5%) | Opponent scandal collapse, character decisive |
| 012 | Wisconsin | Senate | 2024 | Win (+2.8%) | Learned from 2022 loss - specific healthcare message |

## Critical for Ohio 2026 Demo

The corpus is specifically designed for the demo scenario: **Democratic challenger for Ohio Senate 2026**.

Most relevant races:
- **Race 007 (Ohio 2024)**: The previous Ohio Senate race we LOST. What went wrong?
- **Race 009 (Michigan 2024)**: Working-class auto industry messaging that worked
- **Race 012 (Wisconsin 2024)**: How we corrected 2022's mistakes

Key themes for Ohio 2026:
- Manufacturing anxiety and plant closures
- Working-class defection from Democrats
- "What have you done lately?" vs. past accomplishments
- Economic specificity beats generic populism
- Union dynamics and endorsement value

## Directory Structure

```
political-consulting-corpus/
├── races/
│   ├── race-001-michigan-gov-2022/
│   │   ├── metadata.json
│   │   ├── focus-groups/
│   │   │   ├── fg-001-detroit-suburbs.md
│   │   │   ├── fg-002-grand-rapids.md
│   │   │   ├── fg-003-swing-voters-statewide.md
│   │   │   └── fg-004-northern-rural.md
│   │   └── strategy-memo.md
│   ├── race-002-pennsylvania-senate-2022/
│   ├── race-003-wisconsin-senate-2022/          # LOSS
│   ├── race-004-georgia-senate-2022/
│   ├── race-005-arizona-gov-2022/
│   ├── race-006-nevada-senate-2022/
│   ├── race-007-ohio-senate-2024/               # LOSS - Critical for demo
│   ├── race-008-montana-senate-2024/            # LOSS
│   ├── race-009-michigan-senate-2024/
│   ├── race-010-pennsylvania-senate-2024/
│   ├── race-011-north-carolina-gov-2024/
│   └── race-012-wisconsin-senate-2024/
├── race-index.json
└── README.md
```

## Key Themes Across Corpus

### 1. Economic Messaging
- Generic populism ("fighting for families") fails
- Specific policies ($35 insulin, 10,000 jobs) succeed
- "What have you done lately?" defeats past accomplishments

### 2. Working-Class Defection
- Key quotes: "The Democrats had decades to help us. They didn't."
- "The party left us. We didn't leave it."
- Requires acknowledgment, not just messaging

### 3. Healthcare Costs
- Nurse backgrounds provide authenticity
- Pharma executive backgrounds are toxic
- Specific drug pricing wins

### 4. Candidate Authenticity
- Working-class biography > business credentials
- "One of us" matters more than resume
- CEO identity is often liability

### 5. Abortion Rights
- Remains mobilizing post-Dobbs
- Suburban women activated
- Even Republicans crossing over on extremism

### 6. Character and Scandal
- Can be decisive (NC Governor 2024)
- Election denial disqualifying for McCain Republicans
- Character can override partisanship when breach is severe

## Semantic Search Examples

| Query | Returns |
|-------|---------|
| "economic anxiety" | Youngstown working class, Scranton NEPA, Fox Valley |
| "working class defection" | Ohio 2024 Youngstown, Montana 2024 rural |
| "healthcare costs messaging" | PA 2024 Philly suburbs, WI 2024 Milwaukee suburbs |
| "what went wrong in losses" | Strategy memos from WI 2022, OH 2024, MT 2024 |
| "persuadable Republicans" | AZ 2022 Maricopa, NC 2024 Charlotte suburbs |

## Demo Scenarios

### 1. Ohio 2026 Challenger
> "We have a new client running for Ohio Senate in 2026. What should they know?"

Returns:
- OH 2024 strategy memo (what failed)
- Youngstown focus group (working-class voice)
- MI 2024 strategy memo (what worked in similar state)

### 2. Learning from Losses
> "What did we learn from races we lost?"

Returns:
- WI 2022: Generic economic message failed
- OH 2024: Working class felt abandoned, "what's changed?"
- MT 2024: Personal brand can't overcome party brand

### 3. Healthcare Messaging
> "How do we message on healthcare costs?"

Returns:
- PA 2024 Philly suburbs (pharma attack)
- WI 2024 Milwaukee suburbs (nurse credibility)
- NV 2022 Las Vegas union (worker healthcare)

### 4. Winning Back Working Class
> "How do we win back voters who feel the party abandoned them?"

Returns:
- OH 2024 Youngstown (the defection)
- MI 2024 Flint (what worked)
- PA 2022 Scranton (hometown connection)

## Data Notes

- All candidate names, participant profiles, and focus group details are fictional
- Geographic and demographic details are realistic for demonstration purposes
- Transcripts reflect authentic focus group dynamics (interruptions, contradictions, tangents)
- Strategy memos include candid analysis including self-criticism
- Loss races contain explicit failure analysis

## Key Quotes from the Corpus

### On Economic Anxiety
> "I make $25 an hour with tips. My rent is $1,800. Do the math." - NV 2022 Vegas Union

> "I have a college degree and I manage a Dollar General. That's the economy here." - GA 2022 Rural

### On Working-Class Defection
> "The Democrats had decades to help us. They didn't. They focused on the cities, on minorities, on college kids. We got nothing." - OH 2024 Youngstown

> "The party left us. We didn't leave it." - PA 2024 Scranton

### On Authenticity
> "She's not parachuting in. She lives here. Shops here. Knows people." - WI 2024 Fox Valley

> "CEOs create jobs by cutting workers. I've seen it." - MI 2024 Detroit Suburbs

### On Character
> "I've voted Republican my whole life. I can't vote for him. Period." - NC 2024 Charlotte

> "Jack is a good man. But his party isn't." - MT 2024 Rural

---

*Generated for demo purposes. Not real focus group data.*
