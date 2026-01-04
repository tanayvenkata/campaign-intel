#!/usr/bin/env python3
"""
V3 Retrieval: LLM Router → Hierarchical Search (Parents → Children)

Uses:
- LLM Router (Gemini Flash) to select relevant focus groups
- bge-m3 local embeddings (1024 dims)
- Hierarchical index: query parents first, return children
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


class LLMRouter:
    """Routes queries to relevant focus groups using LLM."""

    SYSTEM_PROMPT = """You are a focus group search filter. Given a user query, determine which focus groups are relevant.

AVAILABLE FOCUS GROUPS:
{manifest}

YOUR TASK:
1. Analyze the query for geographic, demographic, or other specific filters
2. Match against the focus group metadata (state, location, demographics, outcome)
3. Return relevant focus group IDs

FILTERING RULES:
- If query mentions a STATE (Ohio, Michigan, etc.) → return only FGs from that state
- If query mentions a CITY (Cleveland, Detroit, etc.) → return FGs from that city/area
- If query mentions DEMOGRAPHICS (working-class, Latino, suburban, etc.) → return FGs matching that demographic
- If query mentions OUTCOME (lost, won, races we lost) → filter by outcome
- If query is BROAD with no specific filters (just topics like "economy", "jobs", "healthcare") → return {{"all": true}}

IMPORTANT:
- Be INCLUSIVE - if in doubt, include the focus group (retrieval will handle relevance)
- A query can have MULTIPLE filters (e.g., "Ohio working-class" = Ohio AND working-class)
- If query mentions a state/location we don't have data for, return empty with reason

OUTPUT FORMAT:
Return ONLY valid JSON, no explanations, no text before or after.

Examples:
{{"focus_group_ids": ["race-007-fg-001-cleveland-suburbs", "race-007-fg-002-columbus-educated"]}}
{{"all": true}}
{{"focus_group_ids": [], "reason": "No focus groups match California. Available: Michigan, Pennsylvania, Wisconsin, Georgia, Arizona, Nevada, Ohio, Montana, North Carolina"}}"""

    def __init__(self, model: str = ROUTER_MODEL):
        import openai
        # Use OpenRouter (centralized for cost tracking)
        self.client = openai.OpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL
        )
        self.model = model
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> str:
        """Load manifest as formatted string for prompt, enriched with participant demographics."""
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

            # Format: ID: Race | Location | Participants | outcome
            line = f"- {fg_id}: {fg['race_name']} | {fg['location']}"
            if participant_summary:
                line += f" | {participant_summary}"
            line += f" | outcome={fg['outcome']}"
            lines.append(line)

        return "\n".join(lines)

    def route(self, query: str) -> Optional[List[str]]:
        """Route query to relevant focus group IDs. Returns None for 'search all'."""
        prompt = self.SYSTEM_PROMPT.format(manifest=self.manifest)

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

        # Parse JSON response
        try:
            # Handle potential markdown code blocks
            if "```" in result_text:
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]

            result = json.loads(result_text)

            # Check for "all" flag
            if result.get("all", False):
                return None  # None means search all

            return result.get("focus_group_ids", [])
        except json.JSONDecodeError:
            # Fallback: search all
            return None

    def _get_all_ids(self) -> List[str]:
        """Get all focus group IDs."""
        manifest_file = DATA_DIR / "manifest.json"
        with open(manifest_file) as f:
            data = json.load(f)
        return [fg["focus_group_id"] for fg in data["focus_groups"]]


class FocusGroupRetrieverV2:
    """V2 Retriever with LLM routing, hierarchical search, and optional reranking."""

    def __init__(
        self,
        use_router: bool = True,
        use_reranker: bool = False,
        reranker_model: str = RERANKER_MODEL,
        verbose: bool = False
    ):
        from sentence_transformers import SentenceTransformer
        from pinecone import Pinecone

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

        # Initialize reranker
        if use_reranker:
            if verbose:
                print(f"Loading reranker: {reranker_model}...")
            from scripts.rerank import Reranker
            self.reranker = Reranker(model_name=reranker_model)
        else:
            self.reranker = None

        # Load embedding model (bge-m3 by default)
        if verbose:
            print(f"Loading embedding model: {EMBEDDING_MODEL_LOCAL}...")
        self.model = SentenceTransformer(EMBEDDING_MODEL_LOCAL)

        # Initialize Pinecone
        self.pc = Pinecone(api_key=PINECONE_API_KEY)
        self.index = self.pc.Index(INDEX_NAME)

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
                fg_ids = self.router._get_all_ids()
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
