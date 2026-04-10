from __future__ import annotations

import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from apps.recommendations.yelp_content import (
    build_business_profiles,
    build_yelp_content_recommendations,
    is_restaurant_business,
    iter_json_lines,
    preprocess_categories,
    serialize_similarity,
)


class YelpContentTests(SimpleTestCase):
    def test_iter_json_lines_skips_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.json"
            source.write_text(
                '{"business_id": "b1"}\nnot-json\n{"business_id": "b2"}\n',
                encoding="utf-8",
            )

            records = list(iter_json_lines(source))

        self.assertEqual(records, [{"business_id": "b1"}, {"business_id": "b2"}])

    def test_is_restaurant_business_filters_non_restaurants(self) -> None:
        base_record = {
            "business_id": "b1",
            "categories": "Restaurants, Sushi Bars",
            "review_count": 12,
            "is_open": 1,
            "latitude": 1.0,
            "longitude": 2.0,
        }

        self.assertTrue(is_restaurant_business(base_record))
        self.assertFalse(
            is_restaurant_business({**base_record, "categories": "Pet Food, Retail"})
        )
        self.assertFalse(is_restaurant_business({**base_record, "is_open": 0}))
        self.assertTrue(
            is_restaurant_business({**base_record, "is_open": 0}, include_closed=True)
        )
        self.assertFalse(is_restaurant_business({**base_record, "review_count": 3}))
        self.assertFalse(is_restaurant_business({**base_record, "latitude": None}))

    def test_preprocess_categories_keeps_multiword_category_tokens(self) -> None:
        result = preprocess_categories("Ice Cream & Frozen Yogurt, Bubble Tea")

        self.assertEqual(result, "ice_cream_frozen_yogurt bubble_tea")

    def test_build_business_profiles_aggregates_reviews_with_cap(self) -> None:
        business_records = [
            {
                "business_id": "b1",
                "name": "Ramen One",
                "categories": "Restaurants, Ramen",
                "stars": 4.5,
                "review_count": 20,
                "is_open": 1,
                "latitude": 1.0,
                "longitude": 2.0,
            },
            {
                "business_id": "b2",
                "name": "Pharmacy Cafe",
                "categories": "Pharmacy, Cafe",
                "stars": 4.0,
                "review_count": 20,
                "is_open": 1,
                "latitude": 1.0,
                "longitude": 2.0,
            },
        ]
        review_records = [
            {"business_id": "b1", "text": "rich broth ramen"},
            {"business_id": "b1", "text": "spicy noodles"},
            {"business_id": "b1", "text": "extra review ignored"},
            {"business_id": "b2", "text": "not included"},
        ]

        profiles = build_business_profiles(
            business_records,
            review_records,
            max_reviews_per_business=2,
        )

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].business_id, "b1")
        self.assertEqual(profiles[0].review_texts, ["rich broth ramen", "spicy noodles"])

    def test_build_yelp_content_recommendations_outputs_business_id_json(self) -> None:
        profiles = build_business_profiles(
            [
                _business("b1", "Sushi Ramen", "Restaurants, Sushi Bars", 30),
                _business("b2", "Taco Corner", "Restaurants, Mexican", 30),
                _business("b3", "Omakase Sushi", "Restaurants, Sushi Bars", 30),
            ],
            [
                {"business_id": "b1", "text": "sushi ramen noodle"},
                {"business_id": "b2", "text": "taco burrito salsa"},
                {"business_id": "b3", "text": "sushi omakase sashimi"},
            ],
            max_reviews_per_business=5,
        )

        result = build_yelp_content_recommendations(
            profiles,
            top_k=1,
            max_features=100,
            min_df=1,
            max_df=1.0,
        )
        serialized = serialize_similarity(result.similarities)

        self.assertEqual(set(serialized), {"b1", "b2", "b3"})
        self.assertEqual(serialized["b1"][0]["business_id"], "b3")
        score = serialized["b1"][0]["score"]
        self.assertIsInstance(score, float)
        self.assertGreater(float(score), 0.0)
        self.assertGreater(result.feature_count, 0)


def _business(
    business_id: str,
    name: str,
    categories: str,
    review_count: int,
) -> dict[str, object]:
    return {
        "business_id": business_id,
        "name": name,
        "categories": categories,
        "stars": 4.0,
        "review_count": review_count,
        "is_open": 1,
        "latitude": 1.0,
        "longitude": 2.0,
    }
