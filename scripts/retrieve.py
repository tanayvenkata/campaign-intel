#!/usr/bin/env python3
"""
Focus Group Retrieval: LLM Router → Hierarchical Search (Parents → Children)

Uses:
- LLM Router (Gemini Flash) to select relevant focus groups
- bge-m3 local embeddings (1024 dims)
- Hierarchical index: query parents first, return children

Run: python scripts/retrieve.py "What did Ohio voters say about the economy?"
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Union
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.config import (
    OPENAI_API_KEY,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    ROUTER_MODEL,
    PINECONE_API_KEY,
    DATA_DIR,
    FOCUS_GROUPS_DIR,
    EMBEDDING_MODEL_LOCAL,
    RERANKER_MODEL,
)

# V3 index constants (bge-m3 with 1024 dims)
INDEX_NAME = "focus-group-v3"
MODEL_DIMENSIONS = {
    "BAAI/bge-m3": 1024,
    "intfloat/e5-base-v2": 768,
    "BAAI/bge-base-en-v1.5": 768,
}
DIMENSION = MODEL_DIMENSIONS.get(EMBEDDING_MODEL_LOCAL, 1024)


@dataclass
class RetrievalResult:
    """Single retrieval result."""
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


@dataclass
class GroupedResults:
    """Results grouped by focus group with metadata."""
    focus_group_id: str
    focus_group_metadata: Dict
    chunks: List[RetrievalResult]


@dataclass
class StrategyRetrievalResult:
    """Single strategy memo retrieval result."""
    chunk_id: str
    score: float
    content: str
    race_id: str
    section: str
    subsection: str
    outcome: str
    state: str
    year: int
    margin: float
    source_file: str
    line_number: int


@dataclass
class StrategyGroupedResults:
    """Results grouped by race with metadata."""
    race_id: str
    race_metadata: Dict
    chunks: List[StrategyRetrievalResult]


@dataclass
class RouterResult:
    """Result from unified content router."""
    content_type: str  # "quotes", "lessons", or "both"
    focus_group_ids: Optional[List[str]]  # None means search all FGs
    race_ids: Optional[List[str]]  # None means search all races
    outcome_filter: Optional[str]  # "win", "loss", or None


class LLMRouter:
    """Routes queries to relevant content (focus groups and/or strategy memos)."""

    SYSTEM_PROMPT = """You are a political research assistant that routes queries to the right content.

We have TWO types of content:

1. FOCUS GROUP TRANSCRIPTS (voter quotes)
   Direct quotes from voters in focus groups. Use when the query wants to know what voters said, felt, or thought.
{fg_manifest}

2. STRATEGY MEMOS (campaign lessons)
   Internal campaign analysis of what worked, what failed, and lessons learned. Use when the query asks about strategy, messaging effectiveness, recommendations, or why campaigns won/lost.
{strategy_manifest}

YOUR TASK:
1. Decide what content type(s) would best answer this query
2. Filter to relevant focus groups and/or races based on state, demographics, outcome, etc.

GUIDELINES:
- If query asks what VOTERS said/think/feel → "quotes"
- If query asks what WORKED/FAILED or WHY we won/lost → "lessons"
- If query could benefit from both voter quotes AND strategic analysis → "both"
- Be INCLUSIVE - if in doubt, include more content (retrieval will handle relevance)
- For broad topic queries with no specific filters, search all within the content type

OUTPUT FORMAT:
Return ONLY valid JSON:
{{
  "content_type": "quotes" | "lessons" | "both",
  "focus_groups": {{"ids": ["fg-id-1", "fg-id-2"]}} or {{"all": true}},
  "strategy": {{"race_ids": ["race-001"], "outcome_filter": "win"|"loss"|null}} or {{"all": true}}
}}

Examples:
- "What did Ohio voters say about the economy?" → {{"content_type": "quotes", "focus_groups": {{"ids": ["race-007-fg-001-cleveland-suburbs", "race-007-fg-002-columbus-educated", "race-007-fg-003-youngstown-working-class"]}}, "strategy": {{"race_ids": [], "outcome_filter": null}}}}
- "What went wrong in Ohio 2024?" → {{"content_type": "lessons", "focus_groups": {{"ids": []}}, "strategy": {{"race_ids": ["race-007"], "outcome_filter": "loss"}}}}
- "What messaging worked with working-class voters?" → {{"content_type": "both", "focus_groups": {{"all": true}}, "strategy": {{"all": true, "outcome_filter": "win"}}}}
- "Why did we lose Wisconsin 2022?" → {{"content_type": "lessons", "focus_groups": {{"ids": []}}, "strategy": {{"race_ids": ["race-003"], "outcome_filter": "loss"}}}}"""

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


class FocusGroupRetrieverV2:
    """V2 Retriever with LLM routing, hierarchical search, and optional reranking."""

    def __init__(
        self,
        use_router: bool = True,
        use_reranker: bool = False,
        reranker_model: str = RERANKER_MODEL,
        verbose: bool = False
    ):
        from scripts.retrieval.base import SharedResources

        self.verbose = verbose
        self.use_router = use_router
        self.use_reranker = use_reranker

        # Initialize router
        if use_router:
            if verbose:
                print("Initializing LLM router...")
            self.router = LLMRouter()
        else:
            self.router = None

        # Initialize reranker (uses shared model if available)
        if use_reranker:
            if verbose:
                print(f"Loading reranker: {reranker_model}...")
            self.reranker = SharedResources.get_reranker_model()
        else:
            self.reranker = None

        # Use shared embedding model and Pinecone index (singleton pattern)
        if verbose:
            print(f"Using shared embedding model: {EMBEDDING_MODEL_LOCAL}...")
        self.model = SharedResources.get_embedding_model()
        self.index = SharedResources.get_pinecone_index()

        # Cache for focus group metadata
        self._fg_metadata_cache: Dict[str, Dict] = {}

    def _embed_query(self, query: str) -> List[float]:
        """Embed query with sentence-transformer model (bge-m3 by default)."""
        return self.model.encode(query).tolist()

    def _load_focus_group_metadata(self, fg_id: str) -> Dict:
        """Load focus group metadata from file."""
        if fg_id in self._fg_metadata_cache:
            return self._fg_metadata_cache[fg_id]

        fg_file = FOCUS_GROUPS_DIR / f"{fg_id}.json"
        if fg_file.exists():
            with open(fg_file) as f:
                metadata = json.load(f)
                self._fg_metadata_cache[fg_id] = metadata
                return metadata
        return {}

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_focus_groups: Optional[List[str]] = None,
        parent_top_k: int = 3,
    ) -> List[RetrievalResult]:
        """
        Two-stage hierarchical retrieval.

        1. Route query to relevant focus groups (if router enabled)
        2. Query parent summaries
        3. Return children from matched parents
        """
        # Step 1: Route
        if filter_focus_groups:
            fg_ids = filter_focus_groups
        elif self.use_router and self.router:
            fg_ids = self.router.route(query)  # Returns None for "search all"
            if self.verbose:
                if fg_ids is None:
                    print("Router: searching all focus groups")
                else:
                    print(f"Router selected {len(fg_ids)} focus groups")
        else:
            fg_ids = None

        # Step 2: Query
        query_embedding = self._embed_query(query)

        # If searching ALL focus groups (no filter), skip parents and search children directly
        # This is faster and hierarchical grouping provides less value without pre-filtering
        if fg_ids is None:
            if self.verbose:
                print("Skipping parents (ALL mode) - direct child search")
            results = self._direct_child_search(query_embedding, None, top_k * 4 if self.use_reranker else top_k)
            return self._maybe_rerank(query, results, top_k)

        # Filtered search: use hierarchical approach (parents → children)
        filter_dict = {"type": "parent"}
        filter_dict["focus_group_id"] = {"$in": fg_ids}

        parent_results = self.index.query(
            vector=query_embedding,
            top_k=parent_top_k,
            filter=filter_dict,
            include_metadata=True
        )

        if self.verbose:
            print(f"Found {len(parent_results.matches)} matching parents")

        # Collect child IDs from matched parents
        child_ids = []
        for match in parent_results.matches:
            meta = match.metadata
            try:
                ids = json.loads(meta.get("child_ids", "[]"))
                child_ids.extend(ids)
            except json.JSONDecodeError:
                pass

        if not child_ids:
            # Fallback: direct child search
            if self.verbose:
                print("No children from parents, falling back to direct search")
            results = self._direct_child_search(query_embedding, fg_ids, top_k * 4 if self.use_reranker else top_k)
            return self._maybe_rerank(query, results, top_k)

        # Step 3: Fetch children by IDs and re-rank
        # Query children directly with the same embedding
        child_filter = {"type": "child"}
        if fg_ids:
            child_filter["focus_group_id"] = {"$in": fg_ids}

        # Get more candidates when reranking is enabled
        candidate_k = top_k * 4 if self.use_reranker else top_k * 2
        child_results = self.index.query(
            vector=query_embedding,
            top_k=candidate_k,
            filter=child_filter,
            include_metadata=True
        )

        # Filter to only children from matched parents and limit
        results = []
        seen_ids = set()
        for match in child_results.matches:
            if match.id in child_ids and match.id not in seen_ids:
                seen_ids.add(match.id)
                meta = match.metadata
                results.append(RetrievalResult(
                    chunk_id=match.id,
                    score=match.score,
                    content=meta.get("content", ""),
                    content_original=meta.get("content_original", ""),
                    focus_group_id=meta.get("focus_group_id", ""),
                    participant=meta.get("participant", ""),
                    participant_profile=meta.get("participant_profile", ""),
                    section=meta.get("section", ""),
                    source_file=meta.get("source_file", ""),
                    line_number=meta.get("line_number", 0),
                    preceding_moderator_q=meta.get("preceding_moderator_q", ""),
                ))
                # When reranking, collect more candidates; otherwise limit early
                if not self.use_reranker and len(results) >= top_k:
                    break

        # If we didn't get enough from parent-filtered, add more from direct search
        max_results = top_k * 4 if self.use_reranker else top_k
        if len(results) < max_results:
            for match in child_results.matches:
                if match.id not in seen_ids:
                    seen_ids.add(match.id)
                    meta = match.metadata
                    results.append(RetrievalResult(
                        chunk_id=match.id,
                        score=match.score,
                        content=meta.get("content", ""),
                        content_original=meta.get("content_original", ""),
                        focus_group_id=meta.get("focus_group_id", ""),
                        participant=meta.get("participant", ""),
                        participant_profile=meta.get("participant_profile", ""),
                        section=meta.get("section", ""),
                        source_file=meta.get("source_file", ""),
                        line_number=meta.get("line_number", 0),
                        preceding_moderator_q=meta.get("preceding_moderator_q", ""),
                    ))
                    if not self.use_reranker and len(results) >= top_k:
                        break

        return self._maybe_rerank(query, results, top_k)

    def _maybe_rerank(self, query: str, results: List[RetrievalResult], top_k: int) -> List[RetrievalResult]:
        """Apply reranking if enabled."""
        if not self.use_reranker or not self.reranker or not results:
            return results[:top_k]

        if self.verbose:
            print(f"Reranking {len(results)} candidates...")

        reranked = self.reranker.rerank(query, results, top_k=top_k)
        return reranked

    def _direct_child_search(
        self,
        query_embedding: List[float],
        fg_ids: Optional[List[str]],
        top_k: int
    ) -> List[RetrievalResult]:
        """Direct search on children (fallback)."""
        filter_dict = {"type": "child"}
        if fg_ids:
            filter_dict["focus_group_id"] = {"$in": fg_ids}

        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            filter=filter_dict,
            include_metadata=True
        )

        return [
            RetrievalResult(
                chunk_id=match.id,
                score=match.score,
                content=match.metadata.get("content", ""),
                content_original=match.metadata.get("content_original", ""),
                focus_group_id=match.metadata.get("focus_group_id", ""),
                participant=match.metadata.get("participant", ""),
                participant_profile=match.metadata.get("participant_profile", ""),
                section=match.metadata.get("section", ""),
                source_file=match.metadata.get("source_file", ""),
                line_number=match.metadata.get("line_number", 0),
                preceding_moderator_q=match.metadata.get("preceding_moderator_q", ""),
            )
            for match in results.matches
        ]

    def fetch_qa_block(self, chunk: RetrievalResult) -> str:
        """
        Fetch full Q&A exchange from source transcript for richer context.

        Two-stage context expansion:
        1. Load source markdown file (chunk.source_file)
        2. Find the moderator question (chunk.preceding_moderator_q)
        3. Extract all participant responses until next moderator Q

        Args:
            chunk: A RetrievalResult with source_file and line_number

        Returns:
            Formatted string with full Q&A context
        """
        # Construct path to source file
        corpus_dir = Path(__file__).parent.parent / "political-consulting-corpus"
        source_path = corpus_dir / chunk.source_file

        if not source_path.exists():
            if self.verbose:
                print(f"Source file not found: {source_path}")
            return ""

        # Read the source file
        with open(source_path, "r") as f:
            lines = f.readlines()

        # Find the chunk's line (1-indexed in metadata)
        target_line = chunk.line_number - 1  # Convert to 0-indexed
        if target_line < 0 or target_line >= len(lines):
            return ""

        # Search backwards to find the moderator question
        mod_q_line = -1
        for i in range(target_line, -1, -1):
            line = lines[i].strip()
            if line.startswith("**MODERATOR**:") or line.startswith("**Moderator**:"):
                mod_q_line = i
                break

        if mod_q_line == -1:
            # No moderator question found, return just the chunk context
            return ""

        # Search forward to find the next moderator question (or end of section)
        end_line = len(lines)
        for i in range(mod_q_line + 1, len(lines)):
            line = lines[i].strip()
            # Check for next moderator question or section header
            if line.startswith("**MODERATOR**:") or line.startswith("**Moderator**:"):
                end_line = i
                break
            # Check for section headers (## or ### in markdown)
            if line.startswith("##"):
                end_line = i
                break

        # Extract the full Q&A block
        qa_lines = lines[mod_q_line:end_line]

        # Format the block
        formatted = []
        current_speaker = None

        for line in qa_lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check for speaker pattern: **SPEAKER**:
            if stripped.startswith("**") and "**:" in stripped:
                # Extract speaker name
                speaker_end = stripped.index("**:", 2)
                current_speaker = stripped[2:speaker_end]
                content = stripped[speaker_end + 3:].strip()

                if current_speaker.upper() == "MODERATOR":
                    formatted.append(f"\n**Moderator:** {content}")
                else:
                    formatted.append(f"\n**{current_speaker}:** {content}")
            elif current_speaker:
                # Continuation of previous speaker
                formatted.append(stripped)

        return "\n".join(formatted)

    def fetch_expanded_context(
        self,
        chunks: List[RetrievalResult],
        max_chunks: int = 5
    ) -> List[str]:
        """
        Fetch expanded Q&A context for multiple chunks.

        Args:
            chunks: List of RetrievalResults to expand
            max_chunks: Maximum number of chunks to expand (to control context size)

        Returns:
            List of formatted Q&A blocks (deduplicated by moderator question)
        """
        seen_mod_qs = set()
        contexts = []

        for chunk in chunks[:max_chunks]:
            # Skip if we already have this moderator question's context
            mod_q = chunk.preceding_moderator_q
            if mod_q and mod_q in seen_mod_qs:
                continue

            qa_block = self.fetch_qa_block(chunk)
            if qa_block:
                seen_mod_qs.add(mod_q)
                contexts.append(qa_block)

        return contexts

    def retrieve_per_focus_group(
        self,
        query: str,
        top_k_per_fg: int = 5,
        score_threshold: float = 0.75,
        filter_focus_groups: Optional[List[str]] = None,
    ) -> Dict[str, List[RetrievalResult]]:
        """
        Per-focus-group retrieval: query each FG independently.

        This ensures diversity across focus groups - prevents one FG from
        dominating results when content is similarly relevant across groups.

        Args:
            query: Search query
            top_k_per_fg: Max results per focus group (capped at 5)
            score_threshold: Minimum similarity score to include (default 0.75)
            filter_focus_groups: Optional list of FG IDs to search

        Returns:
            Dict mapping focus_group_id -> list of results for that FG
        """
        # Step 1: Get focus groups to search
        if filter_focus_groups:
            fg_ids = filter_focus_groups
        elif self.use_router and self.router:
            fg_ids = self.router.route(query)
            if fg_ids is None:
                # "Search all" - get all FG IDs
                fg_ids = self.router._get_all_fg_ids()
            if self.verbose:
                print(f"Router selected {len(fg_ids)} focus groups: {fg_ids}")
        else:
            # No router - need to get all IDs
            manifest_file = DATA_DIR / "manifest.json"
            with open(manifest_file) as f:
                data = json.load(f)
            fg_ids = [fg["focus_group_id"] for fg in data["focus_groups"]]

        # Step 2: Embed query once
        query_embedding = self._embed_query(query)

        # Step 3: Query each focus group independently
        results_by_fg: Dict[str, List[RetrievalResult]] = {}

        # Get more candidates if reranking
        search_k = top_k_per_fg * 4 if self.use_reranker else top_k_per_fg * 2

        for fg_id in fg_ids:
            filter_dict = {
                "type": "child",
                "focus_group_id": fg_id
            }

            fg_results = self.index.query(
                vector=query_embedding,
                top_k=search_k,
                filter=filter_dict,
                include_metadata=True
            )

            # Convert to RetrievalResult and apply score threshold
            fg_chunks = []
            for match in fg_results.matches:
                if match.score < score_threshold:
                    continue  # Skip low-scoring results

                meta = match.metadata
                fg_chunks.append(RetrievalResult(
                    chunk_id=match.id,
                    score=match.score,
                    content=meta.get("content", ""),
                    content_original=meta.get("content_original", ""),
                    focus_group_id=meta.get("focus_group_id", ""),
                    participant=meta.get("participant", ""),
                    participant_profile=meta.get("participant_profile", ""),
                    section=meta.get("section", ""),
                    source_file=meta.get("source_file", ""),
                    line_number=meta.get("line_number", 0),
                    preceding_moderator_q=meta.get("preceding_moderator_q", ""),
                ))

            # Rerank within this focus group if enabled
            if self.use_reranker and self.reranker and fg_chunks:
                fg_chunks = self.reranker.rerank(query, fg_chunks, top_k=top_k_per_fg)
            else:
                fg_chunks = fg_chunks[:top_k_per_fg]

            # Only include FGs with results above threshold
            if fg_chunks:
                results_by_fg[fg_id] = fg_chunks
                if self.verbose:
                    print(f"  {fg_id}: {len(fg_chunks)} results (top score: {fg_chunks[0].score:.3f})")

        return results_by_fg

    def retrieve_grouped(
        self,
        query: str,
        top_k: int = 5,
        filter_focus_groups: Optional[List[str]] = None,
        per_focus_group: bool = False,
        score_threshold: float = 0.75,
    ) -> List[GroupedResults]:
        """Retrieve and group results by focus group.

        Args:
            query: Search query
            top_k: Number of results (global top-k or per-FG depending on mode)
            filter_focus_groups: Optional list of FG IDs to filter
            per_focus_group: If True, use per-FG retrieval for diversity
            score_threshold: Minimum score for per-FG mode (default 0.75)
        """
        if per_focus_group:
            # Per-FG retrieval mode
            results_by_fg = self.retrieve_per_focus_group(
                query,
                top_k_per_fg=min(top_k, 5),  # Cap at 5 per FG
                score_threshold=score_threshold,
                filter_focus_groups=filter_focus_groups
            )

            grouped = []
            for fg_id, chunks in results_by_fg.items():
                metadata = self._load_focus_group_metadata(fg_id)
                grouped.append(GroupedResults(
                    focus_group_id=fg_id,
                    focus_group_metadata=metadata,
                    chunks=chunks
                ))

            # Sort by highest scoring chunk in each group
            grouped.sort(key=lambda g: max(c.score for c in g.chunks), reverse=True)
            return grouped

        # Original global top-k mode
        results = self.retrieve(query, top_k, filter_focus_groups)

        # Group by focus group
        groups: Dict[str, List[RetrievalResult]] = {}
        for result in results:
            fg_id = result.focus_group_id
            if fg_id not in groups:
                groups[fg_id] = []
            groups[fg_id].append(result)

        # Create GroupedResults with metadata
        grouped = []
        for fg_id, chunks in groups.items():
            metadata = self._load_focus_group_metadata(fg_id)
            grouped.append(GroupedResults(
                focus_group_id=fg_id,
                focus_group_metadata=metadata,
                chunks=chunks
            ))

        # Sort by highest scoring chunk in each group
        grouped.sort(key=lambda g: max(c.score for c in g.chunks), reverse=True)

        return grouped


class StrategyMemoRetriever:
    """Retriever for strategy memo content (lessons learned from campaigns)."""

    def __init__(
        self,
        use_reranker: bool = False,
        reranker_model: str = RERANKER_MODEL,
        verbose: bool = False
    ):
        from scripts.retrieval.base import SharedResources

        self.verbose = verbose
        self.use_reranker = use_reranker

        # Initialize reranker (uses shared model if available)
        if use_reranker:
            if verbose:
                print(f"Loading reranker: {reranker_model}...")
            self.reranker = SharedResources.get_reranker_model()
        else:
            self.reranker = None

        # Use shared embedding model and Pinecone index (singleton pattern)
        if verbose:
            print(f"Using shared embedding model: {EMBEDDING_MODEL_LOCAL}...")
        self.model = SharedResources.get_embedding_model()
        self.index = SharedResources.get_pinecone_index()

        # Load strategy manifest for metadata
        self._manifest_cache: Optional[Dict] = None

    def _load_manifest(self) -> Dict:
        """Load strategy manifest."""
        if self._manifest_cache:
            return self._manifest_cache

        manifest_file = DATA_DIR / "strategy_chunks" / "manifest.json"
        if manifest_file.exists():
            with open(manifest_file) as f:
                self._manifest_cache = json.load(f)
                return self._manifest_cache
        return {"memos": []}

    def _get_race_metadata(self, race_id: str) -> Dict:
        """Get metadata for a specific race from manifest."""
        manifest = self._load_manifest()
        for memo in manifest.get("memos", []):
            if memo["race_id"] == race_id:
                return memo
        return {}

    def _embed_query(self, query: str) -> List[float]:
        """Embed query with sentence-transformer model."""
        return self.model.encode(query).tolist()

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        outcome_filter: Optional[str] = None,  # "win", "loss", or None for all
        state_filter: Optional[str] = None,
        year_filter: Optional[int] = None,
        parent_top_k: int = 5,
    ) -> List[StrategyRetrievalResult]:
        """
        Retrieve strategy memo chunks.

        Uses hierarchical approach:
        1. Query strategy_parent vectors
        2. Return children from matched parents

        Args:
            query: Search query
            top_k: Number of results to return
            outcome_filter: Filter by "win" or "loss"
            state_filter: Filter by state name
            year_filter: Filter by year
            parent_top_k: Number of parent vectors to query
        """
        query_embedding = self._embed_query(query)

        # Build filter for parents
        parent_filter: Dict = {"type": "strategy_parent"}
        if outcome_filter:
            parent_filter["outcome"] = outcome_filter
        if state_filter:
            parent_filter["state"] = state_filter
        if year_filter:
            parent_filter["year"] = year_filter

        if self.verbose:
            print(f"Querying strategy parents with filter: {parent_filter}")

        # Step 1: Query parents
        parent_results = self.index.query(
            vector=query_embedding,
            top_k=parent_top_k,
            filter=parent_filter,
            include_metadata=True
        )

        if self.verbose:
            print(f"Found {len(parent_results.matches)} matching parents")

        # Collect child IDs from matched parents
        child_ids = []
        for match in parent_results.matches:
            meta = match.metadata
            try:
                ids = json.loads(meta.get("child_ids", "[]"))
                child_ids.extend(ids)
            except json.JSONDecodeError:
                pass

        if not child_ids:
            # Fallback: direct child search
            if self.verbose:
                print("No children from parents, falling back to direct search")
            return self._direct_search(query_embedding, outcome_filter, state_filter, year_filter, top_k)

        # Step 2: Query children
        child_filter: Dict = {"type": "strategy_memo"}
        if outcome_filter:
            child_filter["outcome"] = outcome_filter
        if state_filter:
            child_filter["state"] = state_filter
        if year_filter:
            child_filter["year"] = year_filter

        candidate_k = top_k * 4 if self.use_reranker else top_k * 2
        child_results = self.index.query(
            vector=query_embedding,
            top_k=candidate_k,
            filter=child_filter,
            include_metadata=True
        )

        # Filter to children from matched parents
        results = []
        seen_ids = set()
        for match in child_results.matches:
            if match.id in child_ids and match.id not in seen_ids:
                seen_ids.add(match.id)
                meta = match.metadata
                results.append(StrategyRetrievalResult(
                    chunk_id=match.id,
                    score=match.score,
                    content=meta.get("content", ""),
                    race_id=meta.get("race_id", ""),
                    section=meta.get("section", ""),
                    subsection=meta.get("subsection", ""),
                    outcome=meta.get("outcome", ""),
                    state=meta.get("state", ""),
                    year=meta.get("year", 0),
                    margin=meta.get("margin", 0.0),
                    source_file=meta.get("source_file", ""),
                    line_number=meta.get("line_number", 0),
                ))
                if not self.use_reranker and len(results) >= top_k:
                    break

        # If we need more, add from direct results
        if len(results) < top_k:
            for match in child_results.matches:
                if match.id not in seen_ids:
                    seen_ids.add(match.id)
                    meta = match.metadata
                    results.append(StrategyRetrievalResult(
                        chunk_id=match.id,
                        score=match.score,
                        content=meta.get("content", ""),
                        race_id=meta.get("race_id", ""),
                        section=meta.get("section", ""),
                        subsection=meta.get("subsection", ""),
                        outcome=meta.get("outcome", ""),
                        state=meta.get("state", ""),
                        year=meta.get("year", 0),
                        margin=meta.get("margin", 0.0),
                        source_file=meta.get("source_file", ""),
                        line_number=meta.get("line_number", 0),
                    ))
                    if not self.use_reranker and len(results) >= top_k:
                        break

        return self._maybe_rerank(query, results, top_k)

    def _direct_search(
        self,
        query_embedding: List[float],
        outcome_filter: Optional[str],
        state_filter: Optional[str],
        year_filter: Optional[int],
        top_k: int
    ) -> List[StrategyRetrievalResult]:
        """Direct search on strategy_memo children."""
        filter_dict: Dict = {"type": "strategy_memo"}
        if outcome_filter:
            filter_dict["outcome"] = outcome_filter
        if state_filter:
            filter_dict["state"] = state_filter
        if year_filter:
            filter_dict["year"] = year_filter

        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            filter=filter_dict,
            include_metadata=True
        )

        return [
            StrategyRetrievalResult(
                chunk_id=match.id,
                score=match.score,
                content=match.metadata.get("content", ""),
                race_id=match.metadata.get("race_id", ""),
                section=match.metadata.get("section", ""),
                subsection=match.metadata.get("subsection", ""),
                outcome=match.metadata.get("outcome", ""),
                state=match.metadata.get("state", ""),
                year=match.metadata.get("year", 0),
                margin=match.metadata.get("margin", 0.0),
                source_file=match.metadata.get("source_file", ""),
                line_number=match.metadata.get("line_number", 0),
            )
            for match in results.matches
        ]

    def _maybe_rerank(
        self,
        query: str,
        results: List[StrategyRetrievalResult],
        top_k: int
    ) -> List[StrategyRetrievalResult]:
        """Apply reranking if enabled."""
        if not self.use_reranker or not self.reranker or not results:
            return results[:top_k]

        if self.verbose:
            print(f"Reranking {len(results)} candidates...")

        # Reranker expects objects with .content attribute
        reranked = self.reranker.rerank(query, results, top_k=top_k)
        return reranked

    def retrieve_grouped(
        self,
        query: str,
        top_k: int = 10,
        outcome_filter: Optional[str] = None,
        state_filter: Optional[str] = None,
        year_filter: Optional[int] = None,
        score_threshold: float = 0.55,
    ) -> List[StrategyGroupedResults]:
        """
        Retrieve and group results by race.

        Args:
            query: Search query
            top_k: Total results to retrieve
            outcome_filter: Filter by "win" or "loss"
            state_filter: Filter by state
            year_filter: Filter by year
            score_threshold: Minimum score threshold
        """
        results = self.retrieve(
            query,
            top_k=top_k,
            outcome_filter=outcome_filter,
            state_filter=state_filter,
            year_filter=year_filter,
        )

        # Filter by score threshold
        results = [r for r in results if r.score >= score_threshold]

        # Group by race
        groups: Dict[str, List[StrategyRetrievalResult]] = {}
        for result in results:
            race_id = result.race_id
            if race_id not in groups:
                groups[race_id] = []
            groups[race_id].append(result)

        # Create grouped results with metadata
        grouped = []
        for race_id, chunks in groups.items():
            metadata = self._get_race_metadata(race_id)
            grouped.append(StrategyGroupedResults(
                race_id=race_id,
                race_metadata=metadata,
                chunks=chunks
            ))

        # Sort by highest scoring chunk in each group
        grouped.sort(key=lambda g: max(c.score for c in g.chunks), reverse=True)

        return grouped


def format_strategy_results(grouped_results: List[StrategyGroupedResults]) -> str:
    """Format strategy retrieval results for display."""
    output = []

    for group in grouped_results:
        meta = group.race_metadata

        # Header with race info
        header = f"\n{'='*60}\n"
        header += f"## {meta.get('state', group.race_id)} {meta.get('year', '')} - {meta.get('office', '')}\n"
        outcome = meta.get('outcome', 'unknown')
        margin = meta.get('margin', 0)
        outcome_str = f"{'Won' if outcome == 'win' else 'Lost'} by {abs(margin):.1f}%"
        header += f"**{outcome_str}**\n"
        header += f"{'='*60}\n"
        output.append(header)

        # Lessons/chunks
        for chunk in group.chunks:
            section_info = f"[{chunk.section}"
            if chunk.subsection:
                section_info += f" > {chunk.subsection}"
            section_info += "]"

            lesson = f"\n**{section_info}**\n"
            lesson += f"{chunk.content}\n"
            lesson += f"_[score: {chunk.score:.3f}]_\n"
            output.append(lesson)

    return "".join(output)


def format_results_for_display(grouped_results: List[GroupedResults]) -> str:
    """Format grouped results for display."""
    output = []

    for group in grouped_results:
        meta = group.focus_group_metadata

        # Header with focus group info
        header = f"\n{'='*60}\n"
        header += f"## {meta.get('location', group.focus_group_id)}\n"
        header += f"**{meta.get('race_name', '')}** | {meta.get('date', '')}\n"
        header += f"Participants: {meta.get('participant_summary', '')}\n"

        # Moderator notes summary if available
        mod_notes = meta.get("moderator_notes", {})
        if mod_notes.get("key_themes"):
            header += f"\n**Key Themes:** {', '.join(mod_notes['key_themes'])}\n"

        header += f"{'='*60}\n"
        output.append(header)

        # Quotes
        for chunk in group.chunks:
            quote = f"\n**{chunk.participant}** ({chunk.participant_profile}):\n"
            # Use original content (without the enrichment header)
            content = chunk.content_original if chunk.content_original else chunk.content
            quote += f"> \"{content}\"\n"
            quote += f"_[{chunk.source_file}:{chunk.line_number}] (score: {chunk.score:.3f})_\n"
            output.append(quote)

    return "".join(output)


def main():
    """Interactive retrieval demo."""
    import argparse

    parser = argparse.ArgumentParser(description="V2 Focus Group Retrieval")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results")
    parser.add_argument("--focus-groups", nargs="+", help="Filter to specific focus groups (bypasses router)")
    parser.add_argument("--no-router", action="store_true", help="Disable LLM router")
    parser.add_argument("--rerank", action="store_true", help="Enable cross-encoder reranking")
    parser.add_argument("--rerank-model", default=RERANKER_MODEL,
                        help="Reranker model to use")
    parser.add_argument("--per-fg", action="store_true",
                        help="Use per-focus-group retrieval for diversity")
    parser.add_argument("--threshold", type=float, default=0.75,
                        help="Score threshold for per-FG mode (default: 0.75)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--raw", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    retriever = FocusGroupRetrieverV2(
        use_router=not args.no_router,
        use_reranker=args.rerank,
        reranker_model=args.rerank_model,
        verbose=args.verbose
    )

    if args.query:
        # Single query mode
        grouped = retriever.retrieve_grouped(
            args.query,
            top_k=args.top_k,
            filter_focus_groups=args.focus_groups,
            per_focus_group=args.per_fg,
            score_threshold=args.threshold
        )

        if args.raw:
            # Output as JSON
            output = []
            for group in grouped:
                output.append({
                    "focus_group_id": group.focus_group_id,
                    "metadata": group.focus_group_metadata,
                    "chunks": [
                        {
                            "chunk_id": c.chunk_id,
                            "score": c.score,
                            "content": c.content,
                            "content_original": c.content_original,
                            "participant": c.participant,
                            "participant_profile": c.participant_profile,
                            "section": c.section,
                            "line_number": c.line_number,
                        }
                        for c in group.chunks
                    ]
                })
            print(json.dumps(output, indent=2))
        else:
            # Formatted display
            print(format_results_for_display(grouped))

    else:
        # Interactive mode
        print("V2 Focus Group Retrieval (type 'quit' to exit)")
        print("-" * 40)

        while True:
            query = input("\nQuery: ").strip()
            if query.lower() in ("quit", "exit", "q"):
                break
            if not query:
                continue

            grouped = retriever.retrieve_grouped(query, top_k=args.top_k)
            print(format_results_for_display(grouped))


if __name__ == "__main__":
    main()
