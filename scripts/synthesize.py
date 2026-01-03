#!/usr/bin/env python3
"""
LLM synthesis layer for focus group retrieval.
Generates summaries and thematic analysis from retrieved quotes.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from eval.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, SYNTHESIS_MODEL


@dataclass
class RetrievalResult:
    """Mirror of the dataclass from retrieve_v2.py"""
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
                max_tokens=150,
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
                max_tokens=500,
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
                max_tokens=800,
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if self.verbose:
                print(f"Error generating macro synthesis: {e}")
            return "Unable to generate synthesis."


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
