"""
Retrieval evaluation metrics for focus group search.
"""

from typing import List, Set, Dict, Any
from dataclasses import dataclass


@dataclass
class RetrievalMetrics:
    """Container for retrieval evaluation metrics."""
    recall_at_k: float
    precision_at_k: float
    mrr: float
    hit: bool  # Did we find at least one expected result?


def compute_recall_at_k(
    retrieved_fg_ids: List[str],
    expected_fg_ids: List[str],
    k: int = 5
) -> float:
    """
    Compute Recall@K: What fraction of expected focus groups did we retrieve?

    Args:
        retrieved_fg_ids: List of focus group IDs from retrieved chunks
        expected_fg_ids: List of expected focus group IDs (ground truth)
        k: Number of results to consider

    Returns:
        Recall score between 0 and 1
    """
    if not expected_fg_ids:
        return 1.0  # No expected results = perfect recall (vacuously true)

    retrieved_set = set(retrieved_fg_ids[:k])
    expected_set = set(expected_fg_ids)

    found = retrieved_set.intersection(expected_set)
    return len(found) / len(expected_set)


def compute_precision_at_k(
    retrieved_fg_ids: List[str],
    expected_fg_ids: List[str],
    k: int = 5
) -> float:
    """
    Compute Precision@K: What fraction of retrieved results were relevant?

    Args:
        retrieved_fg_ids: List of focus group IDs from retrieved chunks
        expected_fg_ids: List of expected focus group IDs (ground truth)
        k: Number of results to consider

    Returns:
        Precision score between 0 and 1
    """
    if not retrieved_fg_ids:
        return 0.0  # No results = zero precision

    retrieved_list = retrieved_fg_ids[:k]
    expected_set = set(expected_fg_ids)

    relevant_count = sum(1 for fg_id in retrieved_list if fg_id in expected_set)
    return relevant_count / len(retrieved_list)


def compute_mrr(
    retrieved_fg_ids: List[str],
    expected_fg_ids: List[str]
) -> float:
    """
    Compute Mean Reciprocal Rank: How high is the first correct result?

    Args:
        retrieved_fg_ids: List of focus group IDs from retrieved chunks
        expected_fg_ids: List of expected focus group IDs (ground truth)

    Returns:
        MRR score between 0 and 1
    """
    if not expected_fg_ids:
        return 1.0  # No expected results = perfect MRR

    expected_set = set(expected_fg_ids)

    for rank, fg_id in enumerate(retrieved_fg_ids, start=1):
        if fg_id in expected_set:
            return 1.0 / rank

    return 0.0  # No correct result found


def compute_hit_at_k(
    retrieved_fg_ids: List[str],
    expected_fg_ids: List[str],
    k: int = 5
) -> bool:
    """
    Compute Hit@K: Did we find at least one expected result in top K?

    Args:
        retrieved_fg_ids: List of focus group IDs from retrieved chunks
        expected_fg_ids: List of expected focus group IDs (ground truth)
        k: Number of results to consider

    Returns:
        True if at least one expected focus group was retrieved
    """
    if not expected_fg_ids:
        return True

    retrieved_set = set(retrieved_fg_ids[:k])
    expected_set = set(expected_fg_ids)

    return len(retrieved_set.intersection(expected_set)) > 0


def evaluate_positive_query(
    retrieved_fg_ids: List[str],
    expected_fg_ids: List[str],
    k: int = 5
) -> RetrievalMetrics:
    """
    Evaluate a positive query (one with expected results).

    Args:
        retrieved_fg_ids: List of focus group IDs from retrieved chunks
        expected_fg_ids: List of expected focus group IDs (ground truth)
        k: Number of results to consider

    Returns:
        RetrievalMetrics with all computed metrics
    """
    return RetrievalMetrics(
        recall_at_k=compute_recall_at_k(retrieved_fg_ids, expected_fg_ids, k),
        precision_at_k=compute_precision_at_k(retrieved_fg_ids, expected_fg_ids, k),
        mrr=compute_mrr(retrieved_fg_ids, expected_fg_ids),
        hit=compute_hit_at_k(retrieved_fg_ids, expected_fg_ids, k)
    )


def evaluate_negative_query(
    retrieved_chunks: List[Dict[str, Any]],
    score_threshold: float = 0.5
) -> Dict[str, Any]:
    """
    Evaluate a negative query (one that should return no relevant results).

    Uses BOTH criteria:
    1. All scores must be below threshold
    2. No focus groups should be "relevant" (this is query-specific)

    Args:
        retrieved_chunks: List of retrieved chunks with scores
        score_threshold: Maximum acceptable score for negative case

    Returns:
        Dict with evaluation results
    """
    if not retrieved_chunks:
        return {
            "passed": True,
            "reason": "no_results",
            "max_score": 0.0,
            "all_scores_low": True
        }

    scores = [chunk.get("score", 0) for chunk in retrieved_chunks]
    max_score = max(scores)
    all_scores_low = all(s < score_threshold for s in scores)

    return {
        "passed": all_scores_low,
        "reason": "low_scores" if all_scores_low else "high_score_found",
        "max_score": max_score,
        "all_scores_low": all_scores_low,
        "scores": scores
    }


def evaluate_synthetic_query(
    retrieved_chunk_ids: List[str],
    source_chunk_id: str,
    k: int = 5,
    retrieved_fg_ids: List[str] = None,
    source_fg_id: str = None
) -> Dict[str, Any]:
    """
    Evaluate a synthetic query by checking if source focus group is retrieved.

    Uses focus group match instead of exact chunk match, since multiple chunks
    from the same focus group may validly answer the same query.

    Args:
        retrieved_chunk_ids: List of chunk IDs from retrieved results
        source_chunk_id: The chunk ID the query was generated from
        k: Number of results to consider
        retrieved_fg_ids: List of focus group IDs from retrieved results
        source_fg_id: The focus group ID the query was generated from

    Returns:
        Dict with evaluation results
    """
    # If focus group IDs provided, use focus group match (preferred)
    if retrieved_fg_ids is not None and source_fg_id is not None:
        retrieved_list = retrieved_fg_ids[:k]
        hit = source_fg_id in retrieved_list

        rank = None
        if hit:
            for i, fg_id in enumerate(retrieved_list, start=1):
                if fg_id == source_fg_id:
                    rank = i
                    break

        # Also check exact chunk match as secondary metric
        exact_chunk_hit = source_chunk_id in set(retrieved_chunk_ids[:k])

        return {
            "hit": hit,  # Focus group match
            "rank": rank,
            "mrr": 1.0 / rank if rank else 0.0,
            "exact_chunk_hit": exact_chunk_hit,  # Bonus: exact match
            "source_fg_id": source_fg_id,
            "retrieved_fg_ids": retrieved_list
        }

    # Fallback to exact chunk match if no FG info provided
    retrieved_set = set(retrieved_chunk_ids[:k])
    hit = source_chunk_id in retrieved_set

    rank = None
    if hit:
        for i, chunk_id in enumerate(retrieved_chunk_ids[:k], start=1):
            if chunk_id == source_chunk_id:
                rank = i
                break

    return {
        "hit": hit,
        "rank": rank,
        "mrr": 1.0 / rank if rank else 0.0
    }


def aggregate_metrics(metrics_list: List[RetrievalMetrics]) -> Dict[str, float]:
    """
    Aggregate metrics across multiple queries.

    Args:
        metrics_list: List of RetrievalMetrics from individual queries

    Returns:
        Dict with averaged metrics
    """
    if not metrics_list:
        return {
            "avg_recall": 0.0,
            "avg_precision": 0.0,
            "avg_mrr": 0.0,
            "hit_rate": 0.0,
            "count": 0
        }

    n = len(metrics_list)
    return {
        "avg_recall": sum(m.recall_at_k for m in metrics_list) / n,
        "avg_precision": sum(m.precision_at_k for m in metrics_list) / n,
        "avg_mrr": sum(m.mrr for m in metrics_list) / n,
        "hit_rate": sum(1 for m in metrics_list if m.hit) / n,
        "count": n
    }
