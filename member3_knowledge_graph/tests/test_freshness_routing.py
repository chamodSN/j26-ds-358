import sys
import unittest
from pathlib import Path

# Make the M3 source directory importable
PROJECT_DIR = Path(__file__).resolve().parents[2]
M3_SRC_DIR = PROJECT_DIR / "member3_knowledge_graph" / "src"
sys.path.insert(0, str(M3_SRC_DIR))

from platform_router import (
    rank_by_freshness,
    route_query,
    select_platforms,
    calculate_routing_score,
)

class TestFreshnessRouting(unittest.TestCase):

    def test_higher_freshness_ranks_first(self):
        result = rank_by_freshness(
            ["ebay", "amazon"],
            {"ebay": 0.5, "amazon": 0.9},
        )
        self.assertEqual(result, ["amazon", "ebay"])

    def test_unknown_freshness_ranks_after_known(self):
        result = rank_by_freshness(
            ["ebay", "amazon"],
            {"ebay": 0.8},
        )
        self.assertEqual(result, ["ebay", "amazon"])

    def test_equal_scores_preserve_original_order(self):
        result = rank_by_freshness(
            ["ebay", "amazon"],
            {"ebay": 0.7, "amazon": 0.7},
        )
        self.assertEqual(result, ["ebay", "amazon"])

    def test_all_unknown_preserves_original_order(self):
        result = rank_by_freshness(
            ["ebay", "amazon"],
            {},
        )
        self.assertEqual(result, ["ebay", "amazon"])

    def test_multiple_platforms_sort_correctly(self):
        result = rank_by_freshness(
            ["ebay", "amazon", "aliexpress"],
            {
                "ebay": 0.5,
                "amazon": 0.9,
                "aliexpress": 0.7,
            },
        )
        self.assertEqual(
            result,
            ["amazon", "aliexpress", "ebay"],
        )
    def test_unknown_scores_do_not_change_order(self):
        platforms = ["ebay", "amazon", "aliexpress"]

        result = rank_by_freshness(platforms, {})

        self.assertEqual(result, platforms)

    def test_known_scores_rank_before_unknown(self):
        result = rank_by_freshness(
            ["ebay", "amazon", "aliexpress"],
            {
                "ebay": 0.4,
                "amazon": 0.9,
            },
        )

        self.assertEqual(
            result,
            ["amazon", "ebay", "aliexpress"],
        )

    def test_required_platform_is_selected(self):
        result = select_platforms(
            {"name": "Headphones", "path": "Electronics > Audio > Headphones"},
            {"required_platforms": ["ebay"]},
        )

        self.assertEqual(result["routing_candidates"], ["ebay"])
        self.assertIn("ebay", result["retrieval_ready"])

    def test_excluded_platform_is_not_selected(self):
        result = select_platforms(
            {"name": "Headphones", "path": "Electronics > Audio > Headphones"},
            {"excluded_platforms": ["ebay"]},
        )

        self.assertNotIn("ebay", result["routing_candidates"])

    def test_unavailable_required_platform_fails_safely(self):
        result = select_platforms(
            {"name": "Headphones", "path": "Electronics > Audio > Headphones"},
            {"required_platforms": ["aliexpress"]},
        )

        self.assertEqual(result["routing_candidates"], [])
        self.assertEqual(result["retrieval_ready"], [])

    def test_amazon_candidate_is_not_live_ready(self):
        result = select_platforms(
            {"name": "Headphones", "path": "Electronics > Audio > Headphones"},
            {"required_platforms": ["amazon"]},
        )

        self.assertIn("amazon", result["routing_candidates"])
        self.assertNotIn("amazon", result["retrieval_ready"])

    def test_missing_category_returns_no_candidates(self):
        result = select_platforms(None)

        self.assertEqual(result["routing_candidates"], [])
        self.assertEqual(result["retrieval_ready"], [])

    def test_routing_score_combines_relevance_and_freshness(self):
        score = calculate_routing_score(0.8, 0.6)
        self.assertAlmostEqual(score, 0.74)

    def test_unknown_freshness_uses_category_relevance(self):
        score = calculate_routing_score(0.8, None)
        self.assertAlmostEqual(score, 0.8)

    def test_invalid_relevance_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_routing_score(1.2, 0.5)

    def test_routing_weights_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            calculate_routing_score(
                0.8, 0.6,
                relevance_weight=0.8,
                freshness_weight=0.3,
            )

    def test_threshold_filters_low_scoring_platform(self):
        result = select_platforms(
            {
                "name": "Headphones",
                "path": "Electronics > Audio > Headphones",
            },
            freshness_scores={
                "ebay": 1.0,
                "amazon": 0.0,
            },
            platform_relevance_scores={
                "ebay": 1.0,
                "amazon": 0.5,
            },
            min_routing_score=0.75,
        )

        self.assertIn("ebay", result["routing_candidates"])
        self.assertNotIn("amazon", result["routing_candidates"])

    def test_fallback_keeps_best_candidate_when_threshold_excludes_all(self):
        result = select_platforms(
        {
            "name": "Headphones",
            "path": "Electronics > Audio > Headphones",
        },
        freshness_scores={
            "ebay": 0.0,
            "amazon": 0.0,
        },
        platform_relevance_scores={
            "ebay": 0.8,
            "amazon": 0.6,
        },
        min_routing_score=0.95,
    )

        self.assertTrue(result["routing_candidates"])
        self.assertEqual(result["routing_candidates"][0], "ebay")

    def test_required_platform_survives_threshold(self):
        result = select_platforms(
            {
                "name": "Headphones",
                "path": "Electronics > Audio > Headphones",
            },
            constraints={"required_platforms": ["amazon"]},
            freshness_scores={"amazon": 0.0},
            platform_relevance_scores={"amazon": 0.2},
            min_routing_score=0.75,
        )

        self.assertEqual(result["routing_candidates"], ["amazon"])

    def test_unknown_relevance_fallback_does_not_filter_by_default(self):
        result = select_platforms(
            {
                "name": "Headphones",
                "path": "Electronics > Audio > Headphones",
            },
            freshness_scores={},
        )

        self.assertIn("ebay", result["routing_candidates"])
        self.assertIn("amazon", result["routing_candidates"])


    def test_route_query_applies_threshold(self):
        from unittest.mock import patch

        categories = [{
            "category_id": "test_headphones",
            "category_name": "Headphones",
            "category_path": "Electronics > Audio > Headphones",
            "source": "Google Product Taxonomy",
            "score": 1.5,
        }]

        crosswalk = []

        with patch(
            "platform_router.classify_query",
            return_value=categories,
        ):
            result = route_query(
                query="wireless headphones",
                categories=categories,
                crosswalk=crosswalk,
                min_routing_score=0.75,
                platform_relevance_scores={
                    "ebay": 1.0,
                    "amazon": 0.5,
                },
            )

        self.assertIn("ebay", result["selected_platforms"])
        self.assertNotIn("amazon", result["selected_platforms"])
        self.assertEqual(
            result["selected_platforms"],
            result["retrieval_ready_platforms"],
        )

if __name__ == "__main__":
    unittest.main(verbosity=2)