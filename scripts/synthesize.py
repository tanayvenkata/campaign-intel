#!/usr/bin/env python3
"""
LLM synthesis layer for focus group retrieval.
Generates summaries and thematic analysis from retrieved quotes.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, Generator
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from eval.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, SYNTHESIS_MODEL


@dataclass
class RetrievalResult:
    """Mirror of the dataclass from retrieve.py"""
    chunk_id: str
    score: float
    content: str
    content_original: str
    focus_group_id: str
    participant: str
    participant_profile: str
    section: str
    source_file: str
    line_number: int
    preceding_moderator_q: str = ""


class FocusGroupSynthesizer:
    """Generate summaries and synthesis from retrieved focus group quotes."""

    def __init__(self, model: str = SYNTHESIS_MODEL, verbose: bool = False):
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )
        self.model = model
        self.verbose = verbose

    def light_summary(
        self,
        quotes: List[RetrievalResult],
        query: str,
        focus_group_name: str = ""
    ) -> str:
        """
        Generate a 1-2 sentence summary from retrieved quotes.
        Used for quick scanning of results.

        Args:
            quotes: List of retrieved quotes from a single focus group
            query: The user's original search query
            focus_group_name: Human-readable name of the focus group

        Returns:
            A concise summary (1-2 sentences)
        """
        if not quotes:
            return "No relevant quotes found."

        # Build context from quotes
        quote_texts = []
        for q in quotes[:5]:  # Limit to top 5 for light summary
            participant_info = f"{q.participant} ({q.participant_profile})"
            quote_texts.append(f'- "{q.content_original or q.content}" — {participant_info}')

        quotes_str = "\n".join(quote_texts)

        prompt = f"""You are analyzing focus group quotes for a political consulting firm.

User's question: "{query}"

Quotes from {focus_group_name or 'this focus group'}:
{quotes_str}

Summarize the key sentiment from these quotes in 1-2 sentences. Be specific about what voters said, not generic. Focus on the concrete themes that emerge.

Summary:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if self.verbose:
                print(f"Error generating light summary: {e}")
            return "Unable to generate summary."

    def deep_synthesis(
        self,
        quotes: List[RetrievalResult],
        source_context: List[str],
        query: str,
        focus_group_name: str = ""
    ) -> str:
        """
        Generate a rich synthesis with full conversational context.
        Used when user clicks "Deep Synthesis" button.

        Args:
            quotes: List of retrieved quotes
            source_context: Full Q&A blocks from source transcripts
            query: The user's original search query
            focus_group_name: Human-readable name of the focus group

        Returns:
            A detailed synthesis (2-4 paragraphs)
        """
        if not quotes:
            return "No quotes to synthesize."

        # Build context sections
        context_str = "\n\n---\n\n".join(source_context) if source_context else ""

        # If no source context provided, fall back to quotes
        if not context_str:
            quote_texts = []
            for q in quotes:
                mod_q = f'Moderator: "{q.preceding_moderator_q}"' if q.preceding_moderator_q else ""
                participant_info = f"{q.participant} ({q.participant_profile})"
                quote_texts.append(f'{mod_q}\n"{q.content_original or q.content}" — {participant_info}')
            context_str = "\n\n".join(quote_texts)

        prompt = f"""You are a senior political analyst synthesizing focus group insights.

User's question: "{query}"

Focus group: {focus_group_name or 'Unknown'}

Conversational context (moderator questions and participant responses):
{context_str}

Provide a synthesis that:
1. Identifies the dominant sentiment and any dissenting views
2. Notes specific language voters used (quote key phrases)
3. Highlights any emotional undertones or intensity
4. Connects findings to the user's question

Keep it to 2-3 paragraphs. Be analytical, not just descriptive."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1200,
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if self.verbose:
                print(f"Error generating deep synthesis: {e}")
            return "Unable to generate synthesis."

    def macro_synthesis(
        self,
        fg_summaries: Dict[str, str],
        top_quotes: Dict[str, List[RetrievalResult]],
        query: str
    ) -> str:
        """
        Generate cross-focus-group thematic synthesis.
        Used when user clicks "Synthesize Selected".

        Args:
            fg_summaries: Dict mapping focus_group_id to light summary
            top_quotes: Dict mapping focus_group_id to top quotes
            query: The user's original search query

        Returns:
            Thematic breakdown with citations
        """
        if not fg_summaries:
            return "No focus groups selected for synthesis."

        # Build summaries section
        summaries_str = ""
        for fg_id, summary in fg_summaries.items():
            summaries_str += f"\n**{fg_id}**: {summary}\n"

        # Build quotes section
        quotes_str = ""
        for fg_id, quotes in top_quotes.items():
            quotes_str += f"\n{fg_id}:\n"
            for q in quotes[:3]:  # Top 3 per FG
                quotes_str += f'- "{q.content_original or q.content}" — {q.participant}\n'

        prompt = f"""You are a senior political strategist synthesizing insights across multiple focus groups.

User's question: "{query}"

Summaries by focus group:
{summaries_str}

Key quotes:
{quotes_str}

Provide a thematic synthesis that:
1. Identifies 2-4 cross-cutting themes
2. For each theme, note which focus groups it appeared in
3. Include specific voter quotes as evidence
4. Note any geographic or demographic patterns

Format:
**Theme 1: [Name]**
[Description with citations]

**Theme 2: [Name]**
[Description with citations]

...

Be specific and analytical. Avoid generic observations."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if self.verbose:
                print(f"Error generating macro synthesis: {e}")
            return "Unable to generate synthesis."

    def light_macro_synthesis(
        self,
        fg_summaries: Dict[str, str],
        top_quotes: Dict[str, List[RetrievalResult]],
        fg_metadata: Dict[str, Dict[str, Any]],
        query: str
    ) -> str:
        """
        Light Macro Synthesis: Single LLM call with dynamic quote sampling.

        Ensures every focus group gets representation while capping total context.
        Formula: X quotes per FG where X = max(1, floor(40 / num_fgs))

        Args:
            fg_summaries: Dict mapping focus_group_id to light summary
            top_quotes: Dict mapping focus_group_id to top quotes
            fg_metadata: Dict mapping focus_group_id to metadata (location, race_name, outcome)
            query: The user's original search query

        Returns:
            Thematic synthesis with citations
        """
        if not fg_summaries:
            return "No focus groups selected for synthesis."

        num_fgs = len(fg_summaries)
        MAX_TOTAL_QUOTES = 40
        quotes_per_fg = max(1, MAX_TOTAL_QUOTES // num_fgs)

        # Build summaries section with metadata
        summaries_str = ""
        for fg_id, summary in fg_summaries.items():
            meta = fg_metadata.get(fg_id, {})
            location = meta.get("location", "Unknown location")
            outcome = meta.get("outcome", "unknown")
            summaries_str += f"- **{fg_id}** ({location}, {outcome}): {summary}\n"

        # Build quotes section with dynamic sampling
        quotes_str = ""
        total_quotes = 0
        for fg_id, quotes in top_quotes.items():
            meta = fg_metadata.get(fg_id, {})
            location = meta.get("location", "")
            for q in quotes[:quotes_per_fg]:
                content = q.content_original or q.content
                quotes_str += f'[{fg_id}] "{content}" — {q.participant}\n'
                total_quotes += 1

        prompt = f"""You are a senior political strategist synthesizing insights across {num_fgs} focus groups.

User's question: "{query}"

FOCUS GROUP SUMMARIES:
{summaries_str}

REPRESENTATIVE QUOTES ({total_quotes} from {num_fgs} focus groups):
{quotes_str}

Provide a thematic synthesis that:
1. Identifies 3-5 cross-cutting themes
2. For each theme, cite specific focus groups and quotes as evidence
3. Note any geographic, demographic, or outcome patterns (won vs lost races)
4. Highlight consensus vs divergence across groups

Format as markdown with **Theme: [Name]** headers.
Be specific and analytical. Every claim needs a citation. Avoid generic observations."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if self.verbose:
                print(f"Error generating light macro synthesis: {e}")
            return "Unable to generate synthesis."

    def light_macro_synthesis_stream(
        self,
        fg_summaries: Dict[str, str],
        top_quotes: Dict[str, List[RetrievalResult]],
        fg_metadata: Dict[str, Dict[str, Any]],
        query: str
    ) -> Generator[str, None, None]:
        """Streaming version of light_macro_synthesis."""
        if not fg_summaries:
            yield "No focus groups selected for synthesis."
            return

        num_fgs = len(fg_summaries)
        MAX_TOTAL_QUOTES = 40
        quotes_per_fg = max(1, MAX_TOTAL_QUOTES // num_fgs)

        # Build summaries section with metadata
        summaries_str = ""
        for fg_id, summary in fg_summaries.items():
            meta = fg_metadata.get(fg_id, {})
            location = meta.get("location", "Unknown location")
            outcome = meta.get("outcome", "unknown")
            summaries_str += f"- **{fg_id}** ({location}, {outcome}): {summary}\n"

        # Build quotes section with dynamic sampling
        quotes_str = ""
        total_quotes = 0
        for fg_id, quotes in top_quotes.items():
            for q in quotes[:quotes_per_fg]:
                content = q.content_original or q.content
                quotes_str += f'[{fg_id}] "{content}" — {q.participant}\n'
                total_quotes += 1

        prompt = f"""You are a senior political strategist synthesizing insights across {num_fgs} focus groups.

User's question: "{query}"

FOCUS GROUP SUMMARIES:
{summaries_str}

REPRESENTATIVE QUOTES ({total_quotes} from {num_fgs} focus groups):
{quotes_str}

Provide a thematic synthesis that:
1. Identifies 3-5 cross-cutting themes
2. For each theme, cite specific focus groups and quotes as evidence
3. Note any geographic, demographic, or outcome patterns (won vs lost races)
4. Highlight consensus vs divergence across groups

Format as markdown with **Theme: [Name]** headers.
Be specific and analytical. Every claim needs a citation. Avoid generic observations."""

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.4,
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            if self.verbose:
                print(f"Error generating light macro synthesis: {e}")
            yield "Unable to generate synthesis."

    def deep_macro_synthesis(
        self,
        fg_summaries: Dict[str, str],
        top_quotes: Dict[str, List[RetrievalResult]],
        fg_metadata: Dict[str, Dict[str, Any]],
        query: str
    ) -> Dict[str, Any]:
        """
        Deep Macro Synthesis: Two-stage theme discovery + per-theme synthesis.

        Stage 1: Discover 3-5 theme clusters from summaries + metadata
        Stage 2: For each theme, synthesize with relevant FG quotes

        Args:
            fg_summaries: Dict mapping focus_group_id to light summary
            top_quotes: Dict mapping focus_group_id to top quotes
            fg_metadata: Dict mapping focus_group_id to metadata
            query: The user's original search query

        Returns:
            Dict with themes and metadata:
            {
                "themes": [{"name": str, "focus_group_ids": List[str], "synthesis": str}],
                "metadata": {"stage1_time_ms": int, "stage2_time_ms": int, "llm_calls": int}
            }
        """
        import time

        if not fg_summaries:
            return {"themes": [], "metadata": {"error": "No focus groups selected"}}

        num_fgs = len(fg_summaries)

        # === STAGE 1: Theme Discovery ===
        stage1_start = time.time()

        # Build FG inventory for Stage 1
        inventory_str = ""
        for fg_id, summary in fg_summaries.items():
            meta = fg_metadata.get(fg_id, {})
            location = meta.get("location", "Unknown")
            race_name = meta.get("race_name", "Unknown race")
            outcome = meta.get("outcome", "unknown")
            inventory_str += f"""- {fg_id}
  Location: {location}
  Race: {race_name} ({outcome})
  Summary: {summary}
"""

        stage1_prompt = f"""Analyze {num_fgs} focus groups to identify thematic clusters.

User's question: "{query}"

FOCUS GROUP INVENTORY:
{inventory_str}

Identify 3-5 DISTINCT thematic clusters that emerge across these focus groups.
Themes should be mutually exclusive - each focus group should primarily belong to ONE theme.

For EACH theme:
1. Give it a specific, descriptive name (not generic like "economic concerns")
2. List which focus_group_ids belong to this theme cluster
3. Briefly explain why these FGs cluster together

OUTPUT FORMAT (valid JSON only, no markdown):
{{
  "themes": [
    {{
      "name": "Working-Class Defection from Democrats",
      "focus_group_ids": ["race-007-fg-001", "race-007-fg-003"],
      "rationale": "These FGs show union voters questioning party loyalty due to economic concerns"
    }}
  ]
}}"""

        try:
            stage1_response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": stage1_prompt}],
                max_tokens=1200,
                temperature=0.3,
            )
            stage1_text = stage1_response.choices[0].message.content.strip()

            # Parse JSON - handle potential markdown code blocks
            if "```" in stage1_text:
                stage1_text = stage1_text.split("```")[1]
                if stage1_text.startswith("json"):
                    stage1_text = stage1_text[4:]

            stage1_result = json.loads(stage1_text)
            discovered_themes = stage1_result.get("themes", [])

        except json.JSONDecodeError as e:
            if self.verbose:
                print(f"Stage 1 JSON parse error: {e}")
                print(f"Raw response: {stage1_text}")
            return {
                "themes": [],
                "metadata": {
                    "error": f"Stage 1 failed to parse JSON: {str(e)}",
                    "raw_response": stage1_text[:500]
                }
            }
        except Exception as e:
            if self.verbose:
                print(f"Stage 1 error: {e}")
            return {
                "themes": [],
                "metadata": {"error": f"Stage 1 failed: {str(e)}"}
            }

        stage1_time = (time.time() - stage1_start) * 1000

        # === STAGE 2: Per-Theme Synthesis ===
        stage2_start = time.time()
        llm_calls = 1  # Stage 1 was 1 call

        synthesized_themes = []

        for theme in discovered_themes:
            theme_name = theme.get("name", "Unknown Theme")
            theme_fg_ids = theme.get("focus_group_ids", [])

            if not theme_fg_ids:
                continue

            # Build quotes context for this theme
            theme_context = ""
            for fg_id in theme_fg_ids:
                if fg_id not in top_quotes:
                    continue

                meta = fg_metadata.get(fg_id, {})
                location = meta.get("location", "Unknown")
                outcome = meta.get("outcome", "unknown")

                theme_context += f"\n## {fg_id} - {location} ({outcome})\n"
                theme_context += "Quotes:\n"

                for q in top_quotes[fg_id][:10]:  # Up to 10 quotes per FG for deep analysis
                    content = q.content_original or q.content
                    theme_context += f'- "{content}" — {q.participant} ({q.participant_profile})\n'

            stage2_prompt = f"""Synthesize focus group insights for the theme: "{theme_name}"

User's question: "{query}"

FOCUS GROUPS IN THIS THEME:
{theme_context}

For this specific theme ({theme_name}):
1. What is the core insight across these focus groups?
2. What specific language do voters use? Quote key phrases.
3. Are there geographic or demographic patterns within this theme?
4. What are the strategic implications for a campaign?

Write 2-3 paragraphs with specific quote citations. Be analytical, not just descriptive."""

            try:
                stage2_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": stage2_prompt}],
                    max_tokens=1200,
                    temperature=0.4,
                )
                theme_synthesis = stage2_response.choices[0].message.content.strip()
                llm_calls += 1

                synthesized_themes.append({
                    "name": theme_name,
                    "focus_group_ids": theme_fg_ids,
                    "rationale": theme.get("rationale", ""),
                    "synthesis": theme_synthesis
                })

            except Exception as e:
                if self.verbose:
                    print(f"Stage 2 error for theme '{theme_name}': {e}")
                synthesized_themes.append({
                    "name": theme_name,
                    "focus_group_ids": theme_fg_ids,
                    "rationale": theme.get("rationale", ""),
                    "synthesis": f"Error generating synthesis: {str(e)}"
                })
                llm_calls += 1

        stage2_time = (time.time() - stage2_start) * 1000

        return {
            "themes": synthesized_themes,
            "metadata": {
                "stage1_time_ms": round(stage1_time),
                "stage2_time_ms": round(stage2_time),
                "total_time_ms": round(stage1_time + stage2_time),
                "llm_calls": llm_calls,
                "themes_discovered": len(discovered_themes),
                "themes_synthesized": len(synthesized_themes)
            }
        }

    def deep_macro_synthesis_stream(
        self,
        fg_summaries: Dict[str, str],
        top_quotes: Dict[str, List[RetrievalResult]],
        fg_metadata: Dict[str, Dict[str, Any]],
        query: str
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streaming version of deep_macro_synthesis.

        Yields status updates and theme content as they're generated:
        - {"type": "stage", "stage": "discovering_themes", "message": "..."}
        - {"type": "theme_start", "name": "...", "focus_groups": [...]}
        - {"type": "theme_content", "content": "..."}
        - {"type": "theme_complete", "name": "..."}
        - {"type": "complete", "metadata": {...}}
        """
        import time

        if not fg_summaries:
            yield {"type": "error", "message": "No focus groups selected for synthesis."}
            return

        num_fgs = len(fg_summaries)

        # === STAGE 1: Theme Discovery ===
        yield {"type": "stage", "stage": "discovering_themes", "message": f"Analyzing {num_fgs} focus groups for thematic patterns..."}

        stage1_start = time.time()

        # Build FG inventory for Stage 1
        inventory_str = ""
        for fg_id, summary in fg_summaries.items():
            meta = fg_metadata.get(fg_id, {})
            location = meta.get("location", "Unknown")
            race_name = meta.get("race_name", "Unknown race")
            outcome = meta.get("outcome", "unknown")
            inventory_str += f"""- {fg_id}
  Location: {location}
  Race: {race_name} ({outcome})
  Summary: {summary}
"""

        stage1_prompt = f"""Analyze {num_fgs} focus groups to identify thematic clusters.

User's question: "{query}"

FOCUS GROUP INVENTORY:
{inventory_str}

Identify 3-5 DISTINCT thematic clusters that emerge across these focus groups.
Themes should be mutually exclusive - each focus group should primarily belong to ONE theme.

For EACH theme:
1. Give it a specific, descriptive name (not generic like "economic concerns")
2. List which focus_group_ids belong to this theme cluster
3. Briefly explain why these FGs cluster together

OUTPUT FORMAT (valid JSON only, no markdown):
{{
  "themes": [
    {{
      "name": "Working-Class Defection from Democrats",
      "focus_group_ids": ["race-007-fg-001", "race-007-fg-003"],
      "rationale": "These FGs show union voters questioning party loyalty due to economic concerns"
    }}
  ]
}}"""

        try:
            stage1_response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": stage1_prompt}],
                max_tokens=1200,
                temperature=0.3,
            )
            stage1_text = stage1_response.choices[0].message.content.strip()

            # Parse JSON
            if "```" in stage1_text:
                stage1_text = stage1_text.split("```")[1]
                if stage1_text.startswith("json"):
                    stage1_text = stage1_text[4:]

            stage1_result = json.loads(stage1_text)
            discovered_themes = stage1_result.get("themes", [])

        except json.JSONDecodeError as e:
            yield {"type": "error", "message": f"Failed to parse theme discovery: {str(e)}", "raw": stage1_text[:500]}
            return
        except Exception as e:
            yield {"type": "error", "message": f"Theme discovery failed: {str(e)}"}
            return

        stage1_time = (time.time() - stage1_start) * 1000

        yield {
            "type": "stage",
            "stage": "themes_discovered",
            "message": f"Found {len(discovered_themes)} themes",
            "themes": [t.get("name") for t in discovered_themes]
        }

        # === STAGE 2: Per-Theme Synthesis ===
        stage2_start = time.time()
        llm_calls = 1

        for theme in discovered_themes:
            theme_name = theme.get("name", "Unknown Theme")
            theme_fg_ids = theme.get("focus_group_ids", [])

            if not theme_fg_ids:
                continue

            yield {
                "type": "theme_start",
                "name": theme_name,
                "focus_groups": theme_fg_ids,
                "rationale": theme.get("rationale", "")
            }

            # Build quotes context for this theme
            theme_context = ""
            for fg_id in theme_fg_ids:
                if fg_id not in top_quotes:
                    continue

                meta = fg_metadata.get(fg_id, {})
                location = meta.get("location", "Unknown")
                outcome = meta.get("outcome", "unknown")

                theme_context += f"\n## {fg_id} - {location} ({outcome})\n"
                theme_context += "Quotes:\n"

                for q in top_quotes[fg_id][:10]:
                    content = q.content_original or q.content
                    theme_context += f'- "{content}" — {q.participant} ({q.participant_profile})\n'

            stage2_prompt = f"""Synthesize focus group insights for the theme: "{theme_name}"

User's question: "{query}"

FOCUS GROUPS IN THIS THEME:
{theme_context}

For this specific theme ({theme_name}):
1. What is the core insight across these focus groups?
2. What specific language do voters use? Quote key phrases.
3. Are there geographic or demographic patterns within this theme?
4. What are the strategic implications for a campaign?

Write 2-3 paragraphs with specific quote citations. Be analytical, not just descriptive."""

            try:
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": stage2_prompt}],
                    max_tokens=1200,
                    temperature=0.4,
                    stream=True
                )

                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield {"type": "theme_content", "name": theme_name, "content": chunk.choices[0].delta.content}

                llm_calls += 1
                yield {"type": "theme_complete", "name": theme_name}

            except Exception as e:
                yield {"type": "theme_error", "name": theme_name, "message": str(e)}
                llm_calls += 1

        stage2_time = (time.time() - stage2_start) * 1000

        yield {
            "type": "complete",
            "metadata": {
                "stage1_time_ms": round(stage1_time),
                "stage2_time_ms": round(stage2_time),
                "total_time_ms": round(stage1_time + stage2_time),
                "llm_calls": llm_calls,
                "themes_discovered": len(discovered_themes)
            }
        }


# Quick test
if __name__ == "__main__":
    synthesizer = FocusGroupSynthesizer(verbose=True)

    # Test with mock data
    mock_quotes = [
        RetrievalResult(
            chunk_id="test1",
            score=0.85,
            content="The Democrats abandoned working people.",
            content_original="The Democrats abandoned working people. They talk about pronouns and climate while our towns die.",
            focus_group_id="race_007_fg_02",
            participant="P2",
            participant_profile="M, 55, Manufacturing supervisor, Strongsville",
            section="Senator Brennan: Has He Delivered?",
            source_file="test.md",
            line_number=100,
            preceding_moderator_q="What's changed in the past few years?"
        ),
        RetrievalResult(
            chunk_id="test2",
            score=0.82,
            content="Both parties have failed this area.",
            content_original="Both parties have failed this area. Democrats AND Republicans.",
            focus_group_id="race_007_fg_02",
            participant="P7",
            participant_profile="F, 49, Retail manager, Niles",
            section="Economic Concerns",
            source_file="test.md",
            line_number=150,
            preceding_moderator_q="Who do you blame for the economic situation?"
        )
    ]

    print("Testing light_summary...")
    summary = synthesizer.light_summary(
        mock_quotes,
        query="What frustrations did Ohio voters express?",
        focus_group_name="Cleveland Suburbs"
    )
    print(f"Summary: {summary}\n")
