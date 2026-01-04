"""
End-to-End Backend Test Suite

Validates the entire retrieval pipeline works as documented.
Run with: python eval/test_backend_e2e.py

Tests cover:
1. Router behavior (quotes/lessons/both routing)
2. FG retrieval (score thresholds, correct results)
3. Strategy retrieval (score thresholds, no cross-contamination)
4. Edge cases and negative tests
"""

import os
import sys
import time
import requests
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from eval.config import FG_SCORE_THRESHOLD

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_THRESHOLD = FG_SCORE_THRESHOLD  # From config, should be 0.50


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    duration_ms: float


class BackendE2ETests:
    """End-to-end tests for the backend API."""

    def __init__(self, base_url: str = API_BASE_URL, threshold: float = DEFAULT_THRESHOLD):
        self.base_url = base_url
        self.threshold = threshold
        self.results: list[TestResult] = []

    def _search(self, query: str, top_k: int = 5) -> dict:
        """Execute unified search."""
        response = requests.post(
            f"{self.base_url}/search/unified",
            json={"query": query, "top_k": top_k, "score_threshold": self.threshold}
        )
        response.raise_for_status()
        return response.json()

    def _add_result(self, name: str, passed: bool, message: str, duration_ms: float):
        self.results.append(TestResult(name, passed, message, duration_ms))

    # =========================================================================
    # ROUTER TESTS - Verify correct content type routing
    # =========================================================================

    def test_router_pure_quotes(self):
        """Pure FG query should route to 'quotes' or 'both'."""
        start = time.time()
        query = "What did Ohio voters say about the economy?"

        try:
            result = self._search(query)
            content_type = result["content_type"]
            has_quotes = result["stats"]["total_quotes"] > 0

            # Should route to quotes and return FG quotes
            passed = content_type in ("quotes", "both") and has_quotes
            message = f"Routed to '{content_type}', {result['stats']['total_quotes']} quotes"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("router_pure_quotes", passed, message, (time.time() - start) * 1000)

    def test_router_pure_lessons(self):
        """Strategy query should route to 'lessons' or 'both'."""
        start = time.time()
        query = "What strategic mistakes did we make in Ohio 2024?"

        try:
            result = self._search(query)
            content_type = result["content_type"]
            has_lessons = result["stats"]["total_lessons"] > 0

            passed = content_type in ("lessons", "both") and has_lessons
            message = f"Routed to '{content_type}', {result['stats']['total_lessons']} lessons"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("router_pure_lessons", passed, message, (time.time() - start) * 1000)

    def test_router_both(self):
        """Query needing both should route to 'both'."""
        start = time.time()
        query = "What did focus groups warn us about that we ignored?"

        try:
            result = self._search(query)
            content_type = result["content_type"]

            # This query should ideally return both
            passed = content_type == "both"
            message = f"Routed to '{content_type}'"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("router_both", passed, message, (time.time() - start) * 1000)

    # =========================================================================
    # FG RETRIEVAL TESTS - Verify focus group results
    # =========================================================================

    def test_fg_returns_ohio_for_ohio_query(self):
        """Ohio query should return Ohio focus groups."""
        start = time.time()
        query = "What did Ohio voters say about the economy?"

        try:
            result = self._search(query)
            quotes = result["quotes"]

            # Check that we got Ohio focus groups
            ohio_fgs = [q for q in quotes if "ohio" in q["focus_group_id"].lower() or
                       "ohio" in str(q.get("focus_group_metadata", {})).lower()]

            passed = len(ohio_fgs) > 0
            message = f"Found {len(ohio_fgs)} Ohio FGs out of {len(quotes)} total"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("fg_ohio_query_returns_ohio", passed, message, (time.time() - start) * 1000)

    def test_fg_score_threshold_applied(self):
        """All returned FG quotes should be above threshold."""
        start = time.time()
        query = "What did voters say about healthcare?"

        try:
            result = self._search(query)

            # Check all chunk scores
            low_score_chunks = []
            for fg in result["quotes"]:
                for chunk in fg["chunks"]:
                    if chunk["score"] < self.threshold:
                        low_score_chunks.append((fg["focus_group_id"], chunk["score"]))

            passed = len(low_score_chunks) == 0
            if passed:
                message = f"All {result['stats']['total_quotes']} quotes above threshold {self.threshold}"
            else:
                message = f"Found {len(low_score_chunks)} chunks below threshold: {low_score_chunks[:3]}"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("fg_score_threshold_applied", passed, message, (time.time() - start) * 1000)

    # =========================================================================
    # STRATEGY RETRIEVAL TESTS - Verify campaign lessons results
    # =========================================================================

    def test_strategy_montana_returns_montana(self):
        """Montana query should return Montana race, not others."""
        start = time.time()
        query = "What went wrong in Montana?"

        try:
            result = self._search(query)
            lessons = result["lessons"]

            # Get states returned
            states = [r["race_metadata"].get("state", "?") for r in lessons]

            has_montana = "Montana" in states
            has_non_montana = any(s != "Montana" for s in states)

            passed = has_montana and not has_non_montana
            message = f"Returned states: {states}"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("strategy_montana_only", passed, message, (time.time() - start) * 1000)

    def test_strategy_score_threshold_applied(self):
        """Strategy races should only include those above threshold."""
        start = time.time()
        query = "What went wrong in our Senate races?"

        try:
            result = self._search(query)

            # Check that top chunk in each race is above threshold
            low_score_races = []
            for race in result["lessons"]:
                if race["chunks"]:
                    top_score = max(c["score"] for c in race["chunks"])
                    if top_score < self.threshold:
                        low_score_races.append((race["race_id"], top_score))

            passed = len(low_score_races) == 0
            if passed:
                message = f"All {len(result['lessons'])} races have chunks above threshold"
            else:
                message = f"Found {len(low_score_races)} races below threshold: {low_score_races}"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("strategy_score_threshold_applied", passed, message, (time.time() - start) * 1000)

    def test_strategy_no_cross_state_contamination(self):
        """Very specific state query should prioritize that state."""
        start = time.time()
        # Very specific query - should strongly prioritize Montana
        query = "What did the Montana 2024 post-mortem say about Jack Sullivan?"

        try:
            result = self._search(query)
            lessons = result["lessons"]

            # Get states returned
            states = [r["race_metadata"].get("state", "?") for r in lessons]

            # Montana should be first/primary if present
            has_montana = "Montana" in states
            montana_first = len(states) > 0 and states[0] == "Montana"

            passed = has_montana and montana_first
            message = f"Returned states: {states}"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("strategy_state_priority", passed, message, (time.time() - start) * 1000)

    # =========================================================================
    # EDGE CASE TESTS
    # =========================================================================

    def test_empty_query_handled(self):
        """Empty or very short query should not crash."""
        start = time.time()
        query = "?"

        try:
            result = self._search(query)
            # Should return something without crashing
            passed = "content_type" in result
            message = f"Returned content_type: {result.get('content_type')}"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("edge_empty_query", passed, message, (time.time() - start) * 1000)

    def test_irrelevant_query_returns_empty_or_low_results(self):
        """Completely irrelevant query should return few/no results."""
        start = time.time()
        query = "What is the recipe for chocolate cake?"

        try:
            result = self._search(query)
            total = result["stats"]["total_quotes"] + result["stats"]["total_lessons"]

            # Should return very few results (ideally 0)
            passed = total <= 3  # Allow some noise
            message = f"Returned {total} total results for irrelevant query"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("edge_irrelevant_query", passed, message, (time.time() - start) * 1000)

    def test_latency_acceptable(self):
        """Search should complete within acceptable time."""
        start = time.time()
        query = "What did voters say about the economy?"

        try:
            result = self._search(query)
            latency = result["stats"]["retrieval_time_ms"]

            passed = latency < 10000  # 10 seconds max (cold start can be slow)
            message = f"Latency: {latency:.0f}ms"

        except Exception as e:
            passed = False
            message = f"Error: {e}"

        self._add_result("latency_acceptable", passed, message, (time.time() - start) * 1000)

    # =========================================================================
    # RUN ALL TESTS
    # =========================================================================

    def run_all(self) -> bool:
        """Run all tests and return True if all passed."""
        print("=" * 70)
        print("BACKEND END-TO-END TEST SUITE")
        print(f"API: {self.base_url}")
        print(f"Threshold: {self.threshold}")
        print("=" * 70)
        print()

        # Check API is running
        try:
            requests.get(f"{self.base_url}/health", timeout=5)
        except Exception as e:
            print(f"ERROR: API not reachable at {self.base_url}")
            print(f"  Start with: uvicorn api.main:app --reload")
            return False

        # Router tests
        print("ROUTER TESTS")
        print("-" * 40)
        self.test_router_pure_quotes()
        self.test_router_pure_lessons()
        self.test_router_both()
        print()

        # FG retrieval tests
        print("FOCUS GROUP RETRIEVAL TESTS")
        print("-" * 40)
        self.test_fg_returns_ohio_for_ohio_query()
        self.test_fg_score_threshold_applied()
        print()

        # Strategy retrieval tests
        print("STRATEGY RETRIEVAL TESTS")
        print("-" * 40)
        self.test_strategy_montana_returns_montana()
        self.test_strategy_score_threshold_applied()
        self.test_strategy_no_cross_state_contamination()
        print()

        # Edge case tests
        print("EDGE CASE TESTS")
        print("-" * 40)
        self.test_empty_query_handled()
        self.test_irrelevant_query_returns_empty_or_low_results()
        self.test_latency_acceptable()
        print()

        # Print results
        print("=" * 70)
        print("RESULTS")
        print("=" * 70)

        passed = 0
        failed = 0

        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            icon = "✓" if r.passed else "✗"
            print(f"{icon} [{status}] {r.name}")
            print(f"    {r.message} ({r.duration_ms:.0f}ms)")

            if r.passed:
                passed += 1
            else:
                failed += 1

        print()
        print("=" * 70)
        print(f"TOTAL: {passed}/{passed + failed} passed")

        if failed > 0:
            print(f"FAILED: {failed} tests")
            print()
            print("Failed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")

        print("=" * 70)

        return failed == 0


def main():
    """Run the test suite."""
    import argparse

    parser = argparse.ArgumentParser(description="Run backend E2E tests")
    parser.add_argument("--url", default=API_BASE_URL, help="API base URL")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Score threshold")
    args = parser.parse_args()

    tests = BackendE2ETests(base_url=args.url, threshold=args.threshold)
    success = tests.run_all()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
