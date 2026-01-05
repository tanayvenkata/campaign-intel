import sys
import os
from pathlib import Path
import time
import json
import hashlib
from typing import List, Dict, Optional
from contextlib import asynccontextmanager
from datetime import date
from collections import defaultdict

from cachetools import TTLCache

# Add project root to sys.path to allow imports from scripts/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Production config: disable reranker to stay under 512MB memory limit
USE_RERANKER = os.getenv("USE_RERANKER", "false").lower() == "true"

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from scripts.retrieve import (
    FocusGroupRetrieverV2, LLMRouter, RetrievalResult,
    StrategyMemoRetriever, StrategyRetrievalResult, RouterResult
)
from scripts.retrieval.hybrid import HybridFocusGroupRetriever
from scripts.synthesize import FocusGroupSynthesizer, get_friendly_error
from eval.config import STRATEGY_TOP_K_PER_RACE, DATA_DIR, PROJECT_ROOT, USE_HYBRID_RETRIEVAL
from api.schemas import (
    SearchRequest, SearchResponse, SynthesisRequest, MacroSynthesisRequest,
    GroupedResult, RetrievalChunk,
    LightMacroSynthesisRequest, DeepMacroSynthesisRequest, DeepMacroResponse,
    StrategyChunk, StrategyGroupedResult, UnifiedSearchResponse,
    StrategySynthesisRequest, StrategyMacroSynthesisRequest,
    UnifiedMacroSynthesisRequest, CorpusItem, DocumentContent
)
from api.observability import (
    QueryTracer, log_retrieval_decision, log_score_distribution,
    log_router_decision, log_result_summary
)

# Global instances
retriever: Optional[FocusGroupRetrieverV2] = None
strategy_retriever: Optional[StrategyMemoRetriever] = None
router: Optional[LLMRouter] = None
synthesizer: Optional[FocusGroupSynthesizer] = None

# === Caching & Rate Limiting ===
# Query cache: (query_hash) -> response dict (1 hour TTL, 100 entries max)
search_cache: TTLCache = TTLCache(maxsize=100, ttl=3600)

# Light summary cache: (query_hash, fg_id) -> summary string (1 hour TTL)
light_summary_cache: TTLCache = TTLCache(maxsize=500, ttl=3600)

# Macro synthesis cache: (query_hash) -> synthesis string (1 hour TTL)
macro_synthesis_cache: TTLCache = TTLCache(maxsize=100, ttl=3600)

# Rate limiting: IP -> {"count": int, "date": date}
rate_limits: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "date": date.today()})
DAILY_RATE_LIMIT = int(os.getenv("DAILY_RATE_LIMIT", "100"))


def _get_cache_key(query: str, top_k: int, score_threshold: float, use_hybrid: bool = False) -> str:
    """Generate cache key from query parameters."""
    raw = f"{query.lower().strip()}:{top_k}:{score_threshold}:{use_hybrid}"
    return hashlib.md5(raw.encode()).hexdigest()


def _check_rate_limit(client_ip: str) -> bool:
    """Check if client is within rate limit. Returns True if allowed."""
    today = date.today()
    entry = rate_limits[client_ip]

    # Reset count if new day
    if entry["date"] != today:
        entry["count"] = 0
        entry["date"] = today

    if entry["count"] >= DAILY_RATE_LIMIT:
        return False

    entry["count"] += 1
    return True

# Example queries to pre-warm (from frontend landing page)
# Selected for variety: quotes-only, lessons-only, and mixed routing
EXAMPLE_QUERIES = [
    "Ohio voters on economy",                                  # quotes (0.62)
    "What messaging mistakes did campaigns make?",             # lessons (0.64)
    "Where did Democratic messaging fail with union voters?",  # both (0.62)
    "What do swing voters want to hear about inflation?",      # both (0.62)
]

# Default search params for pre-warming
DEFAULT_TOP_K = 5
DEFAULT_SCORE_THRESHOLD = 0.50


def _prewarm_query(query: str) -> None:
    """Execute a search query and cache the result. Used for pre-warming."""
    from api.schemas import GroupedResult, StrategyGroupedResult, RetrievalChunk, StrategyChunk

    cache_key = _get_cache_key(query, DEFAULT_TOP_K, DEFAULT_SCORE_THRESHOLD, USE_HYBRID_RETRIEVAL)

    # Skip if already cached
    if cache_key in search_cache:
        return

    # Route the query
    route_result = router.route_unified(query)
    content_type = route_result.content_type

    quotes_results = []
    lessons_results = []

    # Fetch focus group quotes if needed
    if content_type in ("quotes", "both"):
        fg_ids = route_result.focus_group_ids
        results_by_fg = retriever.retrieve_per_focus_group(
            query=query,
            top_k_per_fg=DEFAULT_TOP_K,
            score_threshold=DEFAULT_SCORE_THRESHOLD,
            filter_focus_groups=fg_ids
        )

        for fg_id, chunks in results_by_fg.items():
            if not chunks:
                continue
            top_score = max(c.score for c in chunks)
            if top_score < DEFAULT_SCORE_THRESHOLD:
                continue

            fg_meta = retriever._load_focus_group_metadata(fg_id)
            api_chunks = [
                RetrievalChunk(
                    chunk_id=c.chunk_id, score=c.score, content=c.content,
                    content_original=c.content_original, focus_group_id=c.focus_group_id,
                    participant=c.participant, participant_profile=c.participant_profile,
                    section=c.section, source_file=c.source_file, line_number=c.line_number,
                    preceding_moderator_q=c.preceding_moderator_q
                ) for c in chunks
            ]
            quotes_results.append(GroupedResult(
                focus_group_id=fg_id, focus_group_metadata=fg_meta, chunks=api_chunks
            ))

    # Fetch strategy lessons if needed
    if content_type in ("lessons", "both"):
        strategy_grouped = strategy_retriever.retrieve_grouped(
            query=query, top_k=STRATEGY_TOP_K_PER_RACE * 5,
            outcome_filter=route_result.outcome_filter, score_threshold=0.0
        )

        for group in strategy_grouped:
            top_chunks = sorted(group.chunks, key=lambda c: c.score, reverse=True)[:STRATEGY_TOP_K_PER_RACE]
            if not top_chunks or top_chunks[0].score < DEFAULT_SCORE_THRESHOLD:
                continue

            race_meta = strategy_retriever._get_race_metadata(group.race_id)
            api_chunks = [
                StrategyChunk(
                    chunk_id=c.chunk_id, score=c.score, content=c.content,
                    race_id=c.race_id, section=c.section, subsection=c.subsection,
                    outcome=c.outcome, state=c.state, year=c.year, margin=c.margin,
                    source_file=c.source_file, line_number=c.line_number
                ) for c in top_chunks
            ]
            lessons_results.append(StrategyGroupedResult(
                race_id=group.race_id, race_metadata=race_meta, chunks=api_chunks
            ))

    # Store search results in cache
    cache_data = {
        "content_type": content_type,
        "quotes": [q.model_dump() for q in quotes_results],
        "lessons": [l.model_dump() for l in lessons_results],
        "stats": {
            "retrieval_time_ms": 0,  # Pre-warmed
            "total_quotes": sum(len(g.chunks) for g in quotes_results),
            "total_lessons": sum(len(g.chunks) for g in lessons_results),
            "focus_groups_count": len(quotes_results),
            "races_count": len(lessons_results),
            "routed_to": content_type,
            "outcome_filter": route_result.outcome_filter,
            "cached": True,
            "prewarmed": True
        }
    }
    search_cache[cache_key] = cache_data

    # Pre-warm light summaries and macro synthesis for focus group results
    if quotes_results and synthesizer:
        fg_summaries = {}
        fg_metadata = {}
        top_quotes_dict = {}

        for fg in quotes_results:
            fg_id = fg.focus_group_id
            fg_metadata[fg_id] = fg.focus_group_metadata

            # Convert chunks for synthesizer
            from scripts.retrieve import RetrievalResult as ScriptRetrievalResult
            script_chunks = [
                ScriptRetrievalResult(
                    chunk_id=c.chunk_id, score=c.score, content=c.content,
                    content_original=c.content_original, focus_group_id=c.focus_group_id,
                    participant=c.participant, participant_profile=c.participant_profile,
                    section=c.section, source_file=c.source_file, line_number=c.line_number,
                    preceding_moderator_q=c.preceding_moderator_q or ""
                ) for c in fg.chunks
            ]
            top_quotes_dict[fg_id] = script_chunks

            # Generate and cache light summary
            summary_cache_key = f"{cache_key}:{fg_id}"
            if summary_cache_key not in light_summary_cache:
                fg_name = fg.focus_group_metadata.get("location", fg_id)
                summary = synthesizer.light_summary(script_chunks, query, fg_name)
                light_summary_cache[summary_cache_key] = summary
                fg_summaries[fg_id] = summary
            else:
                fg_summaries[fg_id] = light_summary_cache[summary_cache_key]

        # Generate and cache macro synthesis if we have multiple FGs
        if len(fg_summaries) >= 2:
            macro_cache_key = f"macro:{cache_key}"
            if macro_cache_key not in macro_synthesis_cache:
                macro_result = synthesizer.light_macro_synthesis(
                    fg_summaries=fg_summaries,
                    top_quotes=top_quotes_dict,
                    fg_metadata=fg_metadata,
                    query=query
                )
                macro_synthesis_cache[macro_cache_key] = macro_result


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize expensive resources on startup."""
    global retriever, strategy_retriever, router, synthesizer
    print(f"Initializing resources (reranker={'enabled' if USE_RERANKER else 'disabled'}, hybrid={'enabled' if USE_HYBRID_RETRIEVAL else 'disabled'})...")
    # Initialize with same settings as app.py
    # Note: app.py uses st.cache_resource, here we use global singletons
    # USE_RERANKER=false for production (512MB limit), true for local dev
    # USE_HYBRID_RETRIEVAL=false by default, enables BM25+dense fusion
    if USE_HYBRID_RETRIEVAL:
        retriever = HybridFocusGroupRetriever(use_router=True, use_reranker=USE_RERANKER, verbose=False)
    else:
        retriever = FocusGroupRetrieverV2(use_router=True, use_reranker=USE_RERANKER, verbose=False)
    strategy_retriever = StrategyMemoRetriever(use_reranker=USE_RERANKER, verbose=False)
    router = LLMRouter()
    synthesizer = FocusGroupSynthesizer(verbose=False)
    print("Resources initialized.")

    # Pre-warm cache with example queries (async, don't block startup)
    if os.getenv("PREWARM_CACHE", "true").lower() == "true":
        print(f"Pre-warming cache with {len(EXAMPLE_QUERIES)} example queries...")
        for query in EXAMPLE_QUERIES:
            try:
                _prewarm_query(query)
                print(f"  Cached: {query}")
            except Exception as e:
                print(f"  Failed to cache '{query}': {e}")
        print("Cache pre-warming complete.")

    yield
    # Cleanup if needed
    print("Shutting down...")

app = FastAPI(title="Focus Group Search API", lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local dev
        "https://campaign-intel.vercel.app",  # Production frontend
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",  # Preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "resources_loaded": retriever is not None}

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    if not retriever or not router:
        raise HTTPException(status_code=503, detail="Service not ready")

    start_time = time.time()
    
    # 1. Route (retriever handles routing internally if filter_focus_groups is None)
    # The retriever.retrieve_per_focus_group handles routing internally if filter_focus_groups is None
    # but app.py does it explicitly to show the decision. Let's rely on retriever's internal logic 
    # OR replicate app.py if we want to return the routing decision in stats.
    
    # Let's replicate app.py logic to capture routing time stats if possible, 
    # but retrieve_per_focus_group is convenient.
    # For now, we'll let retrieve_per_focus_group handle it, or we can add a router endpoint later if needed.
    
    # Actually, app.py calls router.route() explicitly. 
    # To keep it simple and robust, let's just call retrieve_per_focus_group.
    # It returns a dict of results.

    results_by_fg = retriever.retrieve_per_focus_group(
        query=request.query,
        top_k_per_fg=request.top_k,
        score_threshold=request.score_threshold
    )
    
    retrieval_time = (time.time() - start_time) * 1000

    # Convert to response model
    grouped_results = []
    total_quotes = 0
    
    for fg_id, chunks in results_by_fg.items():
        if not chunks:
            continue
            
        fg_meta = retriever._load_focus_group_metadata(fg_id)
        
        # Convert dataclass chunks to Pydantic chunks
        api_chunks = []
        for c in chunks:
            api_chunks.append(RetrievalChunk(
                chunk_id=c.chunk_id,
                score=c.score,
                content=c.content,
                content_original=c.content_original,
                focus_group_id=c.focus_group_id,
                participant=c.participant,
                participant_profile=c.participant_profile,
                section=c.section,
                source_file=c.source_file,
                line_number=c.line_number,
                preceding_moderator_q=c.preceding_moderator_q
            ))
            
        grouped_results.append(GroupedResult(
            focus_group_id=fg_id,
            focus_group_metadata=fg_meta,
            chunks=api_chunks
        ))
        total_quotes += len(api_chunks)

    return SearchResponse(
        results=grouped_results,
        stats={
            "retrieval_time_ms": round(retrieval_time),
            "total_quotes": total_quotes,
            "focus_groups_count": len(grouped_results)
        }
    )


@app.post("/search/stream")
async def search_stream(request: SearchRequest):
    """Streaming search endpoint that yields status events during processing."""
    if not retriever or not router:
        raise HTTPException(status_code=503, detail="Service not ready")

    def build_response(results_by_fg: Dict, retrieval_time: float) -> dict:
        """Build the final response dict."""
        grouped_results = []
        total_quotes = 0

        for fg_id, chunks in results_by_fg.items():
            if not chunks:
                continue

            fg_meta = retriever._load_focus_group_metadata(fg_id)

            api_chunks = []
            for c in chunks:
                api_chunks.append({
                    "chunk_id": c.chunk_id,
                    "score": c.score,
                    "content": c.content,
                    "content_original": c.content_original,
                    "focus_group_id": c.focus_group_id,
                    "participant": c.participant,
                    "participant_profile": c.participant_profile,
                    "section": c.section,
                    "source_file": c.source_file,
                    "line_number": c.line_number,
                    "preceding_moderator_q": c.preceding_moderator_q
                })

            grouped_results.append({
                "focus_group_id": fg_id,
                "focus_group_metadata": fg_meta,
                "chunks": api_chunks
            })
            total_quotes += len(api_chunks)

        return {
            "results": grouped_results,
            "stats": {
                "retrieval_time_ms": round(retrieval_time),
                "total_quotes": total_quotes,
                "focus_groups_count": len(grouped_results)
            }
        }

    def event_generator():
        start_time = time.time()

        # Step 1: Routing
        yield json.dumps({"type": "status", "step": "routing", "message": "Analyzing query intent..."}) + "\n"

        fg_ids = router.route(request.query)
        if fg_ids is None:
            fg_ids = router._get_all_ids()
            yield json.dumps({"type": "status", "step": "filtering", "message": f"Searching all {len(fg_ids)} focus groups..."}) + "\n"
        else:
            yield json.dumps({"type": "status", "step": "filtering", "message": f"Routing to {len(fg_ids)} relevant focus groups..."}) + "\n"

        # Step 2: Searching
        yield json.dumps({"type": "status", "step": "searching", "message": "Scanning transcripts..."}) + "\n"

        results_by_fg = retriever.retrieve_per_focus_group(
            query=request.query,
            top_k_per_fg=request.top_k,
            score_threshold=request.score_threshold,
            filter_focus_groups=fg_ids  # Skip internal routing since we already routed
        )

        # Step 3: Ranking
        yield json.dumps({"type": "status", "step": "ranking", "message": "Ranking relevance..."}) + "\n"

        retrieval_time = (time.time() - start_time) * 1000

        # Step 4: Complete
        yield json.dumps({"type": "status", "step": "complete", "message": "Done"}) + "\n"

        # Final results
        response_data = build_response(results_by_fg, retrieval_time)
        yield json.dumps({"type": "results", "data": response_data}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.post("/search/unified", response_model=UnifiedSearchResponse)
async def search_unified(search_request: SearchRequest, request: Request):
    """
    Unified search that routes to quotes (focus groups) and/or lessons (strategy memos).
    Uses LLM router to determine content type based on query intent.
    """
    if not retriever or not strategy_retriever or not router:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Daily request limit reached. Please try again tomorrow."
        )

    # Check cache first
    cache_key = _get_cache_key(
        search_request.query,
        search_request.top_k,
        search_request.score_threshold,
        USE_HYBRID_RETRIEVAL
    )
    if cache_key in search_cache:
        cached = search_cache[cache_key]
        # Add cache hit indicator to stats
        cached_response = cached.copy()
        cached_response["stats"] = {**cached["stats"], "cached": True}
        return UnifiedSearchResponse(**cached_response)

    # Initialize tracer for observability
    tracer = QueryTracer(query=search_request.query)

    quotes_results = []
    lessons_results = []

    # Route to determine content type
    try:
        with tracer.step("routing"):
            route_result = router.route_unified(search_request.query)
            content_type = route_result.content_type
            log_router_decision(
                tracer, content_type, route_result.outcome_filter,
                f"FG IDs: {route_result.focus_group_ids[:3] if route_result.focus_group_ids else 'all'}"
            )
    except Exception as e:
        tracer.log("error", {"type": "routing_failure", "message": str(e)})
        # Fallback to searching both when router fails
        content_type = "both"
        route_result = RouterResult(
            content_type="both",
            focus_group_ids=None,
            outcome_filter=None,
            reasoning="Router failed, falling back to comprehensive search"
        )

    # Fetch focus group quotes if needed
    if content_type in ("quotes", "both"):
        try:
            with tracer.step("fg_retrieval"):
                fg_ids = route_result.focus_group_ids
                results_by_fg = retriever.retrieve_per_focus_group(
                    query=search_request.query,
                    top_k_per_fg=search_request.top_k,
                    score_threshold=search_request.score_threshold,
                    filter_focus_groups=fg_ids
                )

                # Log score distribution for debugging
                all_fg_scores = []
                for fg_id, chunks in results_by_fg.items():
                    all_fg_scores.extend([c.score for c in chunks])
                    if not chunks:
                        continue

                    # Filter out FGs where top chunk is below threshold
                    top_score = max(c.score for c in chunks)
                    if top_score < search_request.score_threshold:
                        continue

                    fg_meta = retriever._load_focus_group_metadata(fg_id)
                    api_chunks = [
                        RetrievalChunk(
                            chunk_id=c.chunk_id,
                            score=c.score,
                            content=c.content,
                            content_original=c.content_original,
                            focus_group_id=c.focus_group_id,
                            participant=c.participant,
                            participant_profile=c.participant_profile,
                            section=c.section,
                            source_file=c.source_file,
                            line_number=c.line_number,
                            preceding_moderator_q=c.preceding_moderator_q
                        )
                        for c in chunks
                    ]
                    quotes_results.append(GroupedResult(
                        focus_group_id=fg_id,
                        focus_group_metadata=fg_meta,
                        chunks=api_chunks
                    ))

                log_score_distribution(tracer, "fg", all_fg_scores)
                tracer.log("fg_results", {
                    "focus_groups": len(quotes_results),
                    "total_quotes": sum(len(g.chunks) for g in quotes_results)
                })
        except Exception as e:
            tracer.log("error", {"type": "fg_retrieval_failure", "message": str(e)})
            # Continue without FG results rather than failing completely

    # Fetch strategy lessons if needed
    if content_type in ("lessons", "both"):
        try:
            with tracer.step("strategy_retrieval"):
                strategy_grouped = strategy_retriever.retrieve_grouped(
                    query=search_request.query,
                    top_k=STRATEGY_TOP_K_PER_RACE * 5,
                    outcome_filter=route_result.outcome_filter,
                    score_threshold=0.0  # Rely on threshold filter below
                )

                # Track filtering for observability
                races_before_filter = len(strategy_grouped)
                filtered_races = []

                for group in strategy_grouped:
                    top_chunks = sorted(group.chunks, key=lambda c: c.score, reverse=True)[:STRATEGY_TOP_K_PER_RACE]
                    if not top_chunks:
                        continue

                    top_score = top_chunks[0].score
                    if top_score < search_request.score_threshold:
                        filtered_races.append({
                            "race_id": group.race_id,
                            "top_score": round(top_score, 3),
                            "threshold": search_request.score_threshold
                        })
                        continue

                    race_meta = strategy_retriever._get_race_metadata(group.race_id)
                    api_chunks = [
                        StrategyChunk(
                            chunk_id=c.chunk_id,
                            score=c.score,
                            content=c.content,
                            race_id=c.race_id,
                            section=c.section,
                            subsection=c.subsection,
                            outcome=c.outcome,
                            state=c.state,
                            year=c.year,
                            margin=c.margin,
                            source_file=c.source_file,
                            line_number=c.line_number
                        )
                        for c in top_chunks
                    ]
                    lessons_results.append(StrategyGroupedResult(
                        race_id=group.race_id,
                        race_metadata=race_meta,
                        chunks=api_chunks
                    ))

                # Log filtering decision
                log_retrieval_decision(
                    tracer, "strategy",
                    races_before_filter, len(lessons_results),
                    search_request.score_threshold,
                    f"Filtered out: {[r['race_id'] for r in filtered_races]}" if filtered_races else "No races filtered"
                )

                tracer.log("strategy_results", {
                    "races": len(lessons_results),
                    "total_lessons": sum(len(g.chunks) for g in lessons_results),
                    "filtered_out": filtered_races
                })
        except Exception as e:
            tracer.log("error", {"type": "strategy_retrieval_failure", "message": str(e)})
            # Continue without strategy results rather than failing completely

    # Complete trace with final summary
    log_result_summary(
        tracer,
        len(quotes_results),
        sum(len(g.chunks) for g in quotes_results),
        len(lessons_results),
        sum(len(g.chunks) for g in lessons_results)
    )
    trace = tracer.complete({
        "content_type": content_type,
        "fg_count": len(quotes_results),
        "races_count": len(lessons_results)
    })

    # Build response
    response_data = {
        "content_type": content_type,
        "quotes": quotes_results,
        "lessons": lessons_results,
        "stats": {
            "retrieval_time_ms": round(trace["total_duration_ms"]),
            "total_quotes": sum(len(g.chunks) for g in quotes_results),
            "total_lessons": sum(len(g.chunks) for g in lessons_results),
            "focus_groups_count": len(quotes_results),
            "races_count": len(lessons_results),
            "routed_to": content_type,
            "outcome_filter": route_result.outcome_filter,
            "cached": False
        }
    }

    # Store in cache (convert Pydantic models to dicts for caching)
    cache_data = {
        "content_type": content_type,
        "quotes": [q.model_dump() for q in quotes_results],
        "lessons": [l.model_dump() for l in lessons_results],
        "stats": response_data["stats"]
    }
    search_cache[cache_key] = cache_data

    return UnifiedSearchResponse(**response_data)



# ============ Corpus Explorer Endpoints ============

def _get_race_path_map() -> Dict[str, str]:
    """Helper to map race_id to directory path."""
    try:
        race_index_path = PROJECT_ROOT / "political-consulting-corpus" / "race-index.json"
        if race_index_path.exists():
            with open(race_index_path) as f:
                data = json.load(f)
                # Map race-001 -> races/race-001-michigan-gov-2022
                return {r["race_id"]: r["path"] for r in data.get("races", [])}
    except Exception as e:
        print(f"Error loading race index: {e}")
    return {}

@app.get("/corpus", response_model=List[CorpusItem])
async def list_corpus():
    """List all documents in the corpus."""
    items = []
    race_paths = _get_race_path_map()

    # 1. Focus Groups
    try:
        manifest_path = DATA_DIR / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                fg_data = json.load(f)
                for fg in fg_data.get("focus_groups", []):
                    fg_id = fg["focus_group_id"]
                    # race-XXX-fg-YYY-location
                    parts = fg_id.split("-fg-")
                    if len(parts) >= 2:
                        race_id = parts[0]
                        race_dir = race_paths.get(race_id, f"races/{race_id}")
                        
                        # Filename: fg-YYY-location.md
                        filename_suffix = fg_id.replace(f"{race_id}-", "")
                        file_path = f"{race_dir}/focus-groups/{filename_suffix}.md"
                        
                        items.append(CorpusItem(
                            id=fg_id,
                            type="focus_group",
                            title=f"{fg.get('location', 'Unknown')} ({fg.get('race_name', 'Unknown')})",
                            date=fg.get("date"),
                            location=fg.get("location"),
                            race_name=fg.get("race_name"),
                            outcome=fg.get("outcome"),
                            file_path=file_path
                        ))
    except Exception as e:
        print(f"Error loading FG manifest: {e}")

    # 2. Strategy Memos
    try:
        strategy_manifest = DATA_DIR / "strategy_chunks" / "manifest.json"
        if strategy_manifest.exists():
            with open(strategy_manifest) as f:
                strat_data = json.load(f)
                for memo in strat_data.get("memos", []):
                    race_id = memo["race_id"]
                    race_dir = race_paths.get(race_id, f"races/{race_id}")
                    
                    items.append(CorpusItem(
                        id=race_id,
                        type="strategy_memo",
                        title=f"Strategy: {memo.get('state')} {memo.get('year')} ({memo.get('outcome')})",
                        date=str(memo.get("year")),
                        location=memo.get("state"),
                        race_name=f"{memo.get('state')} {memo.get('office')}",
                        outcome=memo.get("outcome"),
                        file_path=f"{race_dir}/strategy-memo.md"
                    ))
    except Exception as e:
        print(f"Error loading strategy manifest: {e}")
        
    return items

@app.get("/corpus/{doc_type}/{doc_id}", response_model=DocumentContent)
async def get_document(doc_type: str, doc_id: str):
    """Get raw content of a document."""
    file_path = None
    race_paths = _get_race_path_map()
    
    # Resolve path based on type and ID
    if doc_type == "focus_group":
        manifest_path = DATA_DIR / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                fg_data = json.load(f)
                for fg in fg_data.get("focus_groups", []):
                    if fg["focus_group_id"] == doc_id:
                        race_id = doc_id.split("-fg-")[0]
                        race_dir = race_paths.get(race_id, f"races/{race_id}")
                        filename_suffix = doc_id.replace(f"{race_id}-", "")
                        file_path = f"{race_dir}/focus-groups/{filename_suffix}.md"
                        break
    elif doc_type == "strategy_memo":
        race_dir = race_paths.get(doc_id, f"races/{doc_id}")
        file_path = f"{race_dir}/strategy-memo.md"
        
    if not file_path:
        raise HTTPException(status_code=404, detail="Document not found")
        
    # Read file
    full_path = PROJECT_ROOT / "political-consulting-corpus" / file_path
    if not full_path.exists():
         raise HTTPException(status_code=404, detail=f"File not found on disk: {file_path}")
         
    try:
        with open(full_path, "r") as f:
            content = f.read()
            
        return DocumentContent(
            content=content,
            metadata={"source": str(file_path)}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/synthesize/light")
async def synthesize_light(request: SynthesisRequest):
    """Generate a light summary (non-streaming, as it's short)."""
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Check cache if we have a focus group ID
    if request.quotes:
        fg_id = request.quotes[0].focus_group_id
        cache_key = _get_cache_key(request.query, DEFAULT_TOP_K, DEFAULT_SCORE_THRESHOLD, USE_HYBRID_RETRIEVAL)
        summary_cache_key = f"{cache_key}:{fg_id}"

        if summary_cache_key in light_summary_cache:
            return {"summary": light_summary_cache[summary_cache_key], "cached": True}

    # Convert Pydantic chunks back to RetrievalResult dataclasses for the script
    # The script expects objects with attribute access
    script_chunks = [
        RetrievalResult(**c.model_dump()) for c in request.quotes
    ]

    summary = synthesizer.light_summary(
        quotes=script_chunks,
        query=request.query,
        focus_group_name=request.focus_group_name
    )

    # Cache the result
    if request.quotes:
        light_summary_cache[summary_cache_key] = summary

    return {"summary": summary}

@app.post("/synthesize/deep")
async def synthesize_deep(request: SynthesisRequest):
    """Generate a deep synthesis (streaming)."""
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Expand context if strictly needed on backend
    # app.py calls `retriever.fetch_expanded_context` before synthesis.
    # The frontend might not have full context, so we might need to do it here.
    
    script_chunks = [
        RetrievalResult(**c.model_dump()) for c in request.quotes
    ]
    
    # If context not provided, fetch it
    context = request.context
    if not context and retriever:
        context = retriever.fetch_expanded_context(script_chunks, max_chunks=5)
    
    # Streaming wrapper
    # The current synthesizer.deep_synthesis is NOT streaming (it returns a string).
    # We need to adapt it or rewrite it to stream.
    # Since the constraint is "Do not modify existing scripts/ code - wrap it", 
    # BUT "Streaming is required ... this is the main UX win".
    
    # The existing script uses `client.chat.completions.create` without stream=True.
    # To support streaming without modifying the script, we would need to duplicate the logic here 
    # OR modify the script to support streaming.
    # User said: "Do not modify existing scripts/ code - wrap it, don't rewrite"
    # BUT ALSO: "All LLM endpoints should support streaming via StreamingResponse"
    
    # If I cannot modify the script, I cannot make `synthesizer.deep_synthesis` stream 
    # because it calls the OpenAI client internally nicely wrapped.
    # However, I can subclass or just implement the streaming logic here using the same prompt construction.
    # Re-implementing the call logic here seems safer than modifying the shared script 
    # and risking breaking the existing Streamlit app (though I could check for regressions).
    
    # Let's inspect `scripts/synthesize.py` again. It constructs a prompt and calls client.
    # I will replicate the prompt construction here to enable streaming.
    
    # Construct prompt (copied from scripts/synthesize.py to ensure parity)
    context_str = "\n\n---\n\n".join(context) if context else ""
    if not context_str:
        quote_texts = []
        for q in script_chunks:
            mod_q = f'Moderator: "{q.preceding_moderator_q}"' if q.preceding_moderator_q else ""
            participant_info = f"{q.participant} ({q.participant_profile})"
            quote_texts.append(f'{mod_q}\n"{q.content_original or q.content}" — {participant_info}')
        context_str = "\n\n".join(quote_texts)

    prompt = f"""You are a senior political analyst synthesizing focus group insights.

User's question: "{request.query}"

Focus group: {request.focus_group_name or 'Unknown'}

Conversational context (moderator questions and participant responses):
{context_str}

Provide a synthesis that:
1. Identifies the dominant sentiment and any dissenting views
2. Notes specific language voters used (quote key phrases)
3. Highlights any emotional undertones or intensity
4. Connects findings to the user's question

Keep it to 2-3 paragraphs. Be analytical, not just descriptive."""

    async def stream_generator():
        stream = synthesizer.client.chat.completions.create(
            model=synthesizer.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.4,
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@app.post("/synthesize/macro")
async def synthesize_macro(request: MacroSynthesisRequest):
    """Generate macro synthesis (streaming)."""
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Replicate prompt logic from scripts/synthesize.py for streaming
    
    # Build summaries section
    summaries_str = ""
    for fg_id, summary in request.fg_summaries.items():
        summaries_str += f"\n**{fg_id}**: {summary}\n"

    # Build quotes section - preserve diversity across FGs while capping total
    MAX_TOTAL_QUOTES = 40
    num_fgs = len(request.top_quotes)

    # Dynamic per-FG limit: ensure every FG gets representation
    # At minimum 2 per FG, at maximum 5 per FG
    quotes_per_fg = max(2, min(5, MAX_TOTAL_QUOTES // max(num_fgs, 1)))

    quotes_str = ""
    for fg_id, quotes in request.top_quotes.items():
        quotes_str += f"\n{fg_id}:\n"
        # Take top N quotes per FG (dynamic based on total FGs)
        for q in quotes[:quotes_per_fg]:
            content = q.content_original or q.content
            quotes_str += f'- "{content}" — {q.participant}\n'

    prompt = f"""You are a senior political strategist synthesizing insights across multiple focus groups.

User's question: "{request.query}"

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

    async def stream_generator():
        stream = synthesizer.client.chat.completions.create(
            model=synthesizer.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.4,
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


# ============ V2 Macro Synthesis Endpoints ============

@app.post("/synthesize/macro/light")
async def synthesize_macro_light(request: LightMacroSynthesisRequest):
    """
    Light Macro Synthesis (streaming).

    Single LLM call with dynamic quote sampling.
    Ensures every focus group gets representation while capping total context.
    """
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Check cache
    cache_key = _get_cache_key(request.query, DEFAULT_TOP_K, DEFAULT_SCORE_THRESHOLD, USE_HYBRID_RETRIEVAL)
    macro_cache_key = f"macro:{cache_key}"

    if macro_cache_key in macro_synthesis_cache:
        # Stream cached result
        cached_content = macro_synthesis_cache[macro_cache_key]

        async def cached_stream():
            yield cached_content

        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    # Convert Pydantic chunks to dataclasses for the synthesizer
    top_quotes_dataclass = {}
    for fg_id, chunks in request.top_quotes.items():
        top_quotes_dataclass[fg_id] = [
            RetrievalResult(**c.model_dump()) for c in chunks
        ]

    # Collect full response for caching while streaming
    full_response = []

    async def stream_generator():
        for chunk in synthesizer.light_macro_synthesis_stream(
            fg_summaries=request.fg_summaries,
            top_quotes=top_quotes_dataclass,
            fg_metadata=request.fg_metadata,
            query=request.query
        ):
            full_response.append(chunk)
            yield chunk

        # Cache the full response after streaming completes
        macro_synthesis_cache[macro_cache_key] = "".join(full_response)

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


@app.post("/synthesize/macro/deep")
async def synthesize_macro_deep(request: DeepMacroSynthesisRequest):
    """
    Deep Macro Synthesis (streaming).

    Two-stage synthesis:
    - Stage 1: Theme Discovery (identifies 3-5 thematic clusters)
    - Stage 2: Per-Theme Synthesis (rich analysis for each theme)

    Streams status updates and theme content as they're generated.
    """
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Convert Pydantic chunks to dataclasses for the synthesizer
    top_quotes_dataclass = {}
    for fg_id, chunks in request.top_quotes.items():
        top_quotes_dataclass[fg_id] = [
            RetrievalResult(**c.model_dump()) for c in chunks
        ]

    def stream_generator():
        for event in synthesizer.deep_macro_synthesis_stream(
            fg_summaries=request.fg_summaries,
            top_quotes=top_quotes_dataclass,
            fg_metadata=request.fg_metadata,
            query=request.query
        ):
            yield json.dumps(event) + "\n"

    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")


# ============ Strategy Synthesis Endpoints ============

@app.post("/synthesize/strategy/light")
async def synthesize_strategy_light(request: StrategySynthesisRequest):
    """Generate a light summary of strategy lessons for a single race."""
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Build context from chunks
    chunks_text = []
    for c in request.chunks:
        chunks_text.append(f"[{c.section}] {c.content}")
    context = "\n\n".join(chunks_text)

    prompt = f"""You are a senior political strategist summarizing campaign lessons.

Query: "{request.query}"
Race: {request.race_name or 'Unknown'}

Strategy memo excerpts:
{context}

Write a 1-2 sentence summary of the key lesson(s) from this race relevant to the query.
Be specific - include what worked/failed and why. No fluff."""

    try:
        response = synthesizer.client.chat.completions.create(
            model=synthesizer.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3
        )
        return {"summary": response.choices[0].message.content.strip()}
    except Exception as e:
        return {"summary": get_friendly_error(e)}


@app.post("/synthesize/strategy/deep")
async def synthesize_strategy_deep(request: StrategySynthesisRequest):
    """Generate a deep analysis of strategy lessons (streaming)."""
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    chunks_text = []
    for c in request.chunks:
        chunks_text.append(f"[{c.section}]\n{c.content}")
    context = "\n\n---\n\n".join(chunks_text)

    prompt = f"""You are a senior political strategist providing deep analysis of campaign lessons.

Query: "{request.query}"
Race: {request.race_name or 'Unknown'}

Strategy memo excerpts:
{context}

Provide a detailed analysis that:
1. Identifies the key strategic lessons relevant to the query
2. Explains what worked or failed and WHY
3. Notes specific evidence (numbers, quotes, examples from the memo)
4. Offers actionable takeaways for future campaigns

Keep it to 2-3 paragraphs. Be analytical and specific."""

    async def stream_generator():
        try:
            stream = synthesizer.client.chat.completions.create(
                model=synthesizer.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.4,
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield get_friendly_error(e)

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


@app.post("/synthesize/strategy/macro")
async def synthesize_strategy_macro(request: StrategyMacroSynthesisRequest):
    """Generate cross-race strategy synthesis (streaming)."""
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Build summaries section
    summaries_text = ""
    for race_id, summary in request.race_summaries.items():
        meta = request.race_metadata.get(race_id, {})
        state = meta.get("state", "Unknown")
        year = meta.get("year", "?")
        outcome = meta.get("outcome", "?")
        summaries_text += f"\n**{state} {year} ({outcome}):** {summary}\n"

    # Build key excerpts section (1 quote per race)
    excerpts_text = ""
    for race_id, chunks in request.top_chunks.items():
        meta = request.race_metadata.get(race_id, {})
        state = meta.get("state", "Unknown")
        if chunks:
            excerpts_text += f"\n{state}: \"{chunks[0].content[:200]}...\"\n"

    prompt = f"""You are a senior political strategist synthesizing lessons across multiple campaigns.

Query: "{request.query}"

Race summaries:
{summaries_text}

Key excerpts:
{excerpts_text}

Provide a cross-race synthesis that:
1. Identifies 2-3 patterns or themes across these races
2. Notes which races support each pattern (wins vs losses)
3. Offers strategic recommendations based on the evidence

Be specific and actionable. Reference the races by name."""

    async def stream_generator():
        try:
            stream = synthesizer.client.chat.completions.create(
                model=synthesizer.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.4,
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield get_friendly_error(e)

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


# ============ Unified Macro Synthesis (FG + Strategy) ============

@app.post("/synthesize/unified/macro")
async def synthesize_unified_macro(request: UnifiedMacroSynthesisRequest):
    """
    Generate unified macro synthesis combining voter quotes AND strategic lessons.

    Weaves together:
    - What voters said (FG quotes + summaries)
    - What campaigns learned (strategy chunks + summaries)
    """
    if not synthesizer:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Build FG section
    fg_section = ""
    if request.fg_summaries:
        fg_section = "\n## VOTER INSIGHTS (Focus Groups)\n"
        for fg_id, summary in request.fg_summaries.items():
            meta = request.fg_metadata.get(fg_id, {})
            location = meta.get("location", "Unknown")
            fg_section += f"\n**{location}:** {summary}\n"

        # Add 1 quote per FG
        fg_section += "\nKey quotes:\n"
        for fg_id, quotes in request.fg_quotes.items():
            if quotes:
                q = quotes[0]
                fg_section += f'- "{q.content[:150]}..." — {q.participant}\n'

    # Build strategy section
    strategy_section = ""
    if request.strategy_summaries:
        strategy_section = "\n## CAMPAIGN LESSONS (Strategy Memos)\n"
        for race_id, summary in request.strategy_summaries.items():
            meta = request.strategy_metadata.get(race_id, {})
            state = meta.get("state", "Unknown")
            year = meta.get("year", "?")
            outcome = meta.get("outcome", "?")
            strategy_section += f"\n**{state} {year} ({outcome}):** {summary}\n"

        # Add 1 excerpt per race
        strategy_section += "\nKey excerpts:\n"
        for race_id, chunks in request.strategy_chunks.items():
            meta = request.strategy_metadata.get(race_id, {})
            state = meta.get("state", "Unknown")
            if chunks:
                strategy_section += f'- {state}: "{chunks[0].content[:150]}..."\n'

    prompt = f"""You are a senior political strategist synthesizing insights from BOTH voter focus groups AND campaign strategy memos.

Query: "{request.query}"

{fg_section}
{strategy_section}

Provide a unified synthesis that:
1. Connects voter sentiment to campaign outcomes (what voters said → what campaigns learned)
2. Identifies 2-3 key themes supported by BOTH voter quotes AND strategic evidence
3. Notes patterns across wins vs losses
4. Offers actionable recommendations grounded in evidence

Structure your response with clear themes. Reference specific focus groups and races."""

    async def stream_generator():
        try:
            stream = synthesizer.client.chat.completions.create(
                model=synthesizer.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1200,
                temperature=0.4,
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield get_friendly_error(e)

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
