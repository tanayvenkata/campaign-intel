"""
LLM Router for query routing to focus groups and strategy memos.
"""

import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eval.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    ROUTER_MODEL,
    DATA_DIR,
    FOCUS_GROUPS_DIR,
)
from scripts.retrieval.types import RouterResult


def _load_prompt(name: str) -> str:
    """Load a prompt from the prompts directory."""
    prompt_file = Path(__file__).parent.parent.parent / "prompts" / f"{name}.txt"
    if prompt_file.exists():
        return prompt_file.read_text()
    raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


class LLMRouter:
    """Routes queries to relevant content (focus groups and/or strategy memos)."""

    # Load prompt from file (can be overridden for testing)
    SYSTEM_PROMPT = _load_prompt("router_unified")

    def __init__(self, model: str = ROUTER_MODEL):
        import openai
        self.client = openai.OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL
        )
        self.model = model
        self.fg_manifest = self._load_fg_manifest()
        self.strategy_manifest = self._load_strategy_manifest()

    def _load_fg_manifest(self) -> str:
        """Load focus group manifest for prompt."""
        manifest_file = DATA_DIR / "manifest.json"
        with open(manifest_file) as f:
            data = json.load(f)

        lines = []
        for fg in data["focus_groups"]:
            fg_id = fg['focus_group_id']

            # Load participant_summary from individual FG file
            fg_file = FOCUS_GROUPS_DIR / f"{fg_id}.json"
            participant_summary = ""
            if fg_file.exists():
                with open(fg_file) as f:
                    fg_data = json.load(f)
                    participant_summary = fg_data.get("participant_summary", "")

            line = f"   - {fg_id}: {fg['race_name']} | {fg['location']}"
            if participant_summary:
                line += f" | {participant_summary}"
            line += f" | outcome={fg['outcome']}"
            lines.append(line)

        return "\n".join(lines)

    def _load_strategy_manifest(self) -> str:
        """Load strategy memo manifest for prompt."""
        manifest_file = DATA_DIR / "strategy_chunks" / "manifest.json"
        if not manifest_file.exists():
            return "   (No strategy memos available)"

        with open(manifest_file) as f:
            data = json.load(f)

        lines = []
        for memo in data.get("memos", []):
            outcome_str = "WIN" if memo["outcome"] == "win" else "LOSS"
            margin_str = f"+{memo['margin']}" if memo["margin"] > 0 else str(memo["margin"])

            line = f"   - {memo['race_id']}: {memo['state']} {memo['year']} {memo['office']} ({outcome_str}, {margin_str}%)"

            # Add key sections
            sections = memo.get("sections", [])
            if sections:
                key_sections = [s for s in sections if s not in ["Header", "Executive Summary"]][:4]
                line += f"\n     Sections: {', '.join(key_sections)}"

            lines.append(line)

        return "\n".join(lines)

    def route_unified(self, query: str) -> RouterResult:
        """Route query to content type(s) and specific IDs."""
        prompt = self.SYSTEM_PROMPT.format(
            fg_manifest=self.fg_manifest,
            strategy_manifest=self.strategy_manifest
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": query}
            ],
            max_tokens=500,
            temperature=0
        )

        result_text = response.choices[0].message.content.strip()

        # Parse JSON response - handle various formats
        try:
            # Handle markdown code blocks
            if "```" in result_text:
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]

            # Handle garbage text before JSON - find first { and last }
            if not result_text.startswith("{"):
                start = result_text.find("{")
                end = result_text.rfind("}") + 1
                if start != -1 and end > start:
                    result_text = result_text[start:end]

            result = json.loads(result_text)

            content_type = result.get("content_type", "both")

            # Parse focus groups
            fg_data = result.get("focus_groups", {})
            if fg_data.get("all", False):
                focus_group_ids = None
            else:
                focus_group_ids = fg_data.get("ids", [])

            # Parse strategy
            strategy_data = result.get("strategy", {})
            if strategy_data.get("all", False):
                race_ids = None
            else:
                race_ids = strategy_data.get("race_ids", [])
            outcome_filter = strategy_data.get("outcome_filter")

            return RouterResult(
                content_type=content_type,
                focus_group_ids=focus_group_ids,
                race_ids=race_ids,
                outcome_filter=outcome_filter
            )
        except json.JSONDecodeError:
            # Fallback: search both, all content
            return RouterResult(
                content_type="both",
                focus_group_ids=None,
                race_ids=None,
                outcome_filter=None
            )

    def route(self, query: str) -> Optional[List[str]]:
        """Legacy method: Route query to focus group IDs only. Returns None for 'search all'."""
        result = self.route_unified(query)
        return result.focus_group_ids

    def _get_all_fg_ids(self) -> List[str]:
        """Get all focus group IDs."""
        manifest_file = DATA_DIR / "manifest.json"
        with open(manifest_file) as f:
            data = json.load(f)
        return [fg["focus_group_id"] for fg in data["focus_groups"]]

    def _get_all_race_ids(self) -> List[str]:
        """Get all race IDs from strategy memos."""
        manifest_file = DATA_DIR / "strategy_chunks" / "manifest.json"
        if not manifest_file.exists():
            return []
        with open(manifest_file) as f:
            data = json.load(f)
        return [memo["race_id"] for memo in data.get("memos", [])]
