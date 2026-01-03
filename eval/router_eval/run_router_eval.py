#!/usr/bin/env python3
"""
Router Prompt A/B Evaluation

Compare v1 (hardcoded keywords) vs v2 (flexible manifest reasoning) prompts.
"""

import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from eval.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, ROUTER_MODEL

import openai

# Test cases: (query, expected_behavior)
# expected_behavior can be:
#   - {"states": ["Ohio"]} - should return FGs from these states
#   - {"all": True} - should return all FGs
#   - {"demographics": ["working-class"]} - should return FGs matching demographics
#   - {"empty": True} - should return empty (no matching data)

TEST_CASES = [
    # STATE FILTERS
    ("What did Ohio voters say about jobs?", {"states": ["Ohio"]}),
    ("How do Michigan voters feel about the economy?", {"states": ["Michigan"]}),
    ("Pennsylvania voters on healthcare", {"states": ["Pennsylvania"]}),
    ("What did Wisconsin voters think about education?", {"states": ["Wisconsin"]}),
    ("Georgia voters on voting rights", {"states": ["Georgia"]}),
    ("Arizona immigration concerns", {"states": ["Arizona"]}),
    ("North Carolina suburban voters", {"states": ["North Carolina"]}),
    ("Montana rural voters", {"states": ["Montana"]}),

    # DEMOGRAPHIC FILTERS
    ("What do working-class voters think about trade?", {"demographics": ["working-class"]}),
    ("Latino voters on immigration", {"demographics": ["Latino"]}),
    ("Black voters in Georgia", {"states": ["Georgia"], "demographics": ["Black"]}),
    ("College-educated suburban voters", {"demographics": ["college", "suburban"]}),

    # BROAD QUERIES - SHOULD RETURN ALL
    ("What do voters think about the economy?", {"all": True}),
    ("How do people feel about inflation?", {"all": True}),
    ("Voter concerns about healthcare costs", {"all": True}),
    ("What messaging resonates with swing voters?", {"all": True}),

    # COMPOUND FILTERS
    ("Working-class Ohio voters on manufacturing", {"states": ["Ohio"], "demographics": ["working-class"]}),
    ("Pennsylvania suburban voters 2024", {"states": ["Pennsylvania"]}),

    # EDGE CASES
    ("California voters on housing", {"empty": True}),  # No CA data
    ("Cleveland suburbs on local issues", {"cities": ["Cleveland"]}),
]

# Load manifest
MANIFEST_FILE = Path(__file__).parent / "manifest.txt"


@dataclass
class EvalResult:
    query: str
    expected: Dict[str, Any]
    prompt_version: str
    raw_output: str
    parsed_output: Optional[Dict]
    passed: bool
    reason: str


def load_manifest() -> str:
    with open(MANIFEST_FILE) as f:
        return f.read()


def load_prompt(version: str) -> str:
    prompt_file = Path(__file__).parent / "prompts" / f"router_{version}.txt"
    with open(prompt_file) as f:
        return f.read()


def run_router(prompt_template: str, manifest: str, query: str) -> str:
    """Run a single router query."""
    client = openai.OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL
    )

    prompt = prompt_template.replace("{{manifest}}", manifest).replace("{{query}}", query)

    response = client.chat.completions.create(
        model=ROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=500
    )

    return response.choices[0].message.content.strip()


def parse_output(raw: str) -> Optional[Dict]:
    """Parse JSON from router output."""
    try:
        # Handle markdown code blocks
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except:
        return None


def check_result(parsed: Optional[Dict], expected: Dict[str, Any], manifest: str) -> tuple[bool, str]:
    """Check if result matches expected behavior."""
    if parsed is None:
        return False, "Failed to parse JSON output"

    # Check for "all" expected
    if expected.get("all"):
        if parsed.get("all") == True:
            return True, "Correctly returned all"
        return False, f"Expected all=true, got {parsed}"

    # Check for empty expected
    if expected.get("empty"):
        ids = parsed.get("focus_group_ids", [])
        if len(ids) == 0 or parsed.get("all") == True:
            return True, "Correctly handled missing data"
        return False, f"Expected empty/all, got {len(ids)} FGs"

    # Check state filters
    if "states" in expected:
        ids = parsed.get("focus_group_ids", [])
        if parsed.get("all"):
            return False, "Got all=true when state filter expected"
        if not ids:
            return False, "Got empty when state filter expected results"

        # Check that returned FGs match expected states
        expected_states = [s.lower() for s in expected["states"]]
        for fg_id in ids:
            # Extract state from manifest
            fg_line = [l for l in manifest.split("\n") if fg_id in l]
            if fg_line:
                line_lower = fg_line[0].lower()
                if not any(state in line_lower for state in expected_states):
                    return False, f"FG {fg_id} doesn't match expected states {expected_states}"

        return True, f"Correctly filtered to {len(ids)} FGs for {expected_states}"

    # Check city filters
    if "cities" in expected:
        ids = parsed.get("focus_group_ids", [])
        if not ids and not parsed.get("all"):
            return False, "Got empty when city filter expected results"
        return True, f"Returned {len(ids)} FGs for city filter"

    # Check demographics
    if "demographics" in expected:
        ids = parsed.get("focus_group_ids", [])
        if parsed.get("all"):
            return False, "Got all=true when demographic filter expected"
        if len(ids) > 0:
            return True, f"Returned {len(ids)} FGs for demographic filter"
        return False, "Got empty when demographic filter expected results"

    return False, "Unknown expected format"


def run_eval(version: str) -> List[EvalResult]:
    """Run evaluation for a prompt version."""
    manifest = load_manifest()
    prompt = load_prompt(version)
    results = []

    print(f"\n{'='*60}")
    print(f"Evaluating prompt version: {version}")
    print(f"{'='*60}\n")

    for i, (query, expected) in enumerate(TEST_CASES):
        print(f"[{i+1}/{len(TEST_CASES)}] {query[:50]}...", end=" ", flush=True)

        raw_output = run_router(prompt, manifest, query)
        parsed = parse_output(raw_output)
        passed, reason = check_result(parsed, expected, manifest)

        result = EvalResult(
            query=query,
            expected=expected,
            prompt_version=version,
            raw_output=raw_output,
            parsed_output=parsed,
            passed=passed,
            reason=reason
        )
        results.append(result)

        status = "✓" if passed else "✗"
        print(f"{status} {reason[:40]}")

    return results


def print_summary(v1_results: List[EvalResult], v2_results: List[EvalResult]):
    """Print comparison summary."""
    v1_passed = sum(1 for r in v1_results if r.passed)
    v2_passed = sum(1 for r in v2_results if r.passed)
    total = len(TEST_CASES)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"v1 (hardcoded keywords): {v1_passed}/{total} ({100*v1_passed/total:.0f}%)")
    print(f"v2 (flexible reasoning):  {v2_passed}/{total} ({100*v2_passed/total:.0f}%)")
    print()

    # Show differences
    print("Differences:")
    for v1, v2 in zip(v1_results, v2_results):
        if v1.passed != v2.passed:
            winner = "v2" if v2.passed else "v1"
            print(f"  [{winner} wins] {v1.query[:50]}...")
            print(f"    v1: {v1.reason[:50]}")
            print(f"    v2: {v2.reason[:50]}")


def main():
    print("Router Prompt A/B Evaluation")
    print("="*60)

    # Run both versions
    v1_results = run_eval("v1")
    v2_results = run_eval("v2")

    # Print summary
    print_summary(v1_results, v2_results)

    # Save detailed results
    output = {
        "v1": [{"query": r.query, "passed": r.passed, "reason": r.reason, "output": r.raw_output} for r in v1_results],
        "v2": [{"query": r.query, "passed": r.passed, "reason": r.reason, "output": r.raw_output} for r in v2_results],
    }
    output_file = Path(__file__).parent / "eval_results.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nDetailed results saved to: {output_file}")


if __name__ == "__main__":
    main()
