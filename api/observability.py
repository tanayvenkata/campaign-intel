"""
Observability module for the Focus Group Search API.

Provides structured logging and tracing for debugging retrieval issues.
Logs are structured JSON for easy parsing and analysis.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from functools import wraps

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" or "text"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(message)s' if LOG_FORMAT == "json" else '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("focus-group-api")


@dataclass
class QueryTrace:
    """Trace data for a single query."""
    query_id: str
    query: str
    timestamp: str
    steps: list
    total_duration_ms: float = 0
    final_result: Optional[dict] = None
    error: Optional[str] = None


class QueryTracer:
    """
    Traces a query through the retrieval pipeline.

    Usage:
        tracer = QueryTracer(query="What did Ohio voters say?")
        with tracer.step("routing"):
            result = router.route(query)
            tracer.log("route_decision", {"content_type": result.content_type})
        tracer.complete({"total_results": 10})
    """

    def __init__(self, query: str, query_id: Optional[str] = None):
        self.query = query
        self.query_id = query_id or f"q-{int(time.time() * 1000)}"
        self.start_time = time.time()
        self.steps = []
        self.current_step = None
        self.current_step_start = None

    @contextmanager
    def step(self, step_name: str):
        """Context manager for timing a step."""
        self.current_step = step_name
        self.current_step_start = time.time()
        step_data = {
            "step": step_name,
            "started_at": datetime.now().isoformat(),
            "events": []
        }

        try:
            yield
            step_data["status"] = "success"
        except Exception as e:
            step_data["status"] = "error"
            step_data["error"] = str(e)
            raise
        finally:
            step_data["duration_ms"] = (time.time() - self.current_step_start) * 1000
            self.steps.append(step_data)
            self.current_step = None

    def log(self, event: str, data: dict):
        """Log an event within the current step."""
        event_data = {
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

        if self.steps and self.current_step:
            self.steps[-1]["events"].append(event_data)
        else:
            # Log outside of step
            self.steps.append({"event": event, **event_data})

        # Also emit to logger for real-time visibility
        if LOG_FORMAT == "json":
            logger.info(json.dumps({
                "query_id": self.query_id,
                "event": event,
                **data
            }))
        else:
            logger.info(f"[{self.query_id}] {event}: {data}")

    def complete(self, result_summary: dict):
        """Complete the trace with final results."""
        total_duration = (time.time() - self.start_time) * 1000

        trace = {
            "type": "query_trace",
            "query_id": self.query_id,
            "query": self.query[:100],  # Truncate for logs
            "timestamp": datetime.now().isoformat(),
            "total_duration_ms": round(total_duration),
            "steps": self.steps,
            "result_summary": result_summary
        }

        if LOG_FORMAT == "json":
            logger.info(json.dumps(trace))
        else:
            logger.info(f"[{self.query_id}] COMPLETE: {total_duration:.0f}ms - {result_summary}")

        return trace


def log_retrieval_decision(
    tracer: QueryTracer,
    source_type: str,  # "fg" or "strategy"
    items_before_filter: int,
    items_after_filter: int,
    threshold: float,
    filter_reason: str
):
    """Log a retrieval filtering decision."""
    tracer.log("retrieval_filter", {
        "source": source_type,
        "before": items_before_filter,
        "after": items_after_filter,
        "threshold": threshold,
        "reason": filter_reason,
        "filtered_out": items_before_filter - items_after_filter
    })


def log_score_distribution(
    tracer: QueryTracer,
    source_type: str,
    scores: list[float]
):
    """Log score distribution for debugging."""
    if not scores:
        return

    tracer.log("score_distribution", {
        "source": source_type,
        "count": len(scores),
        "min": round(min(scores), 3),
        "max": round(max(scores), 3),
        "mean": round(sum(scores) / len(scores), 3),
        "above_50": len([s for s in scores if s >= 0.50]),
        "above_60": len([s for s in scores if s >= 0.60]),
        "above_70": len([s for s in scores if s >= 0.70]),
    })


def log_router_decision(
    tracer: QueryTracer,
    content_type: str,
    outcome_filter: Optional[str],
    reasoning: Optional[str] = None
):
    """Log router decision."""
    tracer.log("router_decision", {
        "content_type": content_type,
        "outcome_filter": outcome_filter,
        "reasoning": reasoning[:200] if reasoning else None
    })


def log_result_summary(
    tracer: QueryTracer,
    fg_count: int,
    fg_quotes: int,
    strategy_races: int,
    strategy_lessons: int
):
    """Log final result summary."""
    tracer.log("result_summary", {
        "focus_groups": fg_count,
        "quotes": fg_quotes,
        "strategy_races": strategy_races,
        "strategy_lessons": strategy_lessons,
        "total_items": fg_quotes + strategy_lessons
    })
