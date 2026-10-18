import unittest

from member3_knowledge_graph.src.platform_router import (
    classify_category_group,
    classify_query,
    load_graph_categories,
)


class TestRouterRegressions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.categories = load_graph_categories()

    def get_best_category(self, query):
        matches = classify_query(query, self.categories, top_k=5)
        self.assertTrue(matches, f"No category matches for: {query}")
        return matches[0]


    def test_bluetooth_speakers(self):
        category = self.get_best_category("bluetooth speakers")
        self.assertIn(
            "speaker",
            category["category_name"].lower(),
        )
        self.assertEqual(classify_category_group(category), "audio")
        self.assertNotIn(
            "Car & Vehicle Electronics",
            category["category_path"],
        )


    def test_usb_microphones(self):
        category = self.get_best_category("USB microphones")
        self.assertEqual(category["category_name"], "Microphones")
        self.assertEqual(classify_category_group(category), "audio")
        self.assertNotIn("Camera & Photo", category["category_path"])


    def test_wireless_routers(self):
        category = self.get_best_category("wireless routers")
        self.assertIn(
            "router",
            category["category_name"].lower(),
        )
        self.assertEqual(classify_category_group(category), "networking")


    def test_gaming_mice(self):
        category = self.get_best_category("gaming mice")
        self.assertEqual(category["category_name"], "Gaming Mice")
        self.assertEqual(classify_category_group(category), "computing")

    def test_laptop_chargers(self):
        category = self.get_best_category("laptop chargers")
        self.assertIn(
            "charger",
            category["category_name"].lower()
            + " "
            + category["category_path"].lower(),
        )
        self.assertIn(
            "laptop",
            category["category_path"].lower(),
        )
        self.assertEqual(
            classify_category_group(category),
            "power_accessories",
        )

    def test_structured_constraints_are_exposed(self):
        from member3_knowledge_graph.src.platform_router import route_query

        result = route_query(
            query="Samsung laptop with 16GB RAM and 512GB storage under $1200",
            categories=self.categories,
            crosswalk=[],
        )

        structured = result["structured_query"]
        constraints = result["routing_constraints"]

        self.assertEqual(structured["attributes"]["brand"], "Samsung")
        self.assertEqual(structured["attributes"]["ram_gb"], 16)
        self.assertEqual(structured["attributes"]["storage_gb"], 512)
        self.assertEqual(structured["attributes"]["price_max"], 1200.0)

        self.assertIn("ram_gb", constraints["hard_constraints"])
        self.assertIn("storage_gb", constraints["hard_constraints"])
        self.assertIn("price_max", constraints["hard_constraints"])
        self.assertFalse(constraints["listing_filtering_applied"])


if __name__ == "__main__":
    unittest.main()