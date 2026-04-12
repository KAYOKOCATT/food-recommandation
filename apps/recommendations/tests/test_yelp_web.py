from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import Client, TestCase

from apps.recommendations.models import YelpBusiness
from apps.recommendations.services.yelp_service import YelpService
from apps.users.models import User


class YelpServiceTests(TestCase):
    def setUp(self) -> None:
        self.business_1 = YelpBusiness.objects.create(
            business_id="b1",
            name="Alpha Sushi",
            categories="Restaurants, Sushi Bars",
            stars=4.5,
            review_count=120,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        self.business_2 = YelpBusiness.objects.create(
            business_id="b2",
            name="Beta Sushi",
            categories="Restaurants, Japanese",
            stars=4.2,
            review_count=80,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )

    def test_get_similar_businesses_hydrates_from_similarity_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text(
                json.dumps({"b1": [{"business_id": "b2", "score": 0.91}]}),
                encoding="utf-8",
            )

            result = YelpService.get_similar_businesses(
                "b1",
                top_k=6,
                similarity_file=similarity_path,
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].business.business_id, "b2")
        self.assertEqual(result[0].score, 0.91)

    def test_build_business_queryset_filters_by_keyword(self) -> None:
        queryset = YelpService.build_business_queryset(q="Alpha")

        self.assertEqual(list(queryset.values_list("business_id", flat=True)), ["b1"])


class YelpViewTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.business = YelpBusiness.objects.create(
            business_id="b1",
            name="Alpha Sushi",
            categories="Restaurants, Sushi Bars",
            stars=4.5,
            review_count=120,
            city="Philadelphia",
            state="PA",
            is_open=True,
        )
        self.user = User.objects.create(
            username="reviewer",
            password="secret123",
            email="reviewer@example.com",
            phone="13800138000",
        )
        self.business.reviews.create(
            review_id="r1",
            user=self.user,
            stars=5.0,
            text="Excellent omakase.",
        )

    def test_yelp_business_list_renders(self) -> None:
        response = self.client.get("/api/v1/yelp/restaurants/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Sushi")

    def test_yelp_business_detail_renders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            similarity_path = Path(temp_dir) / "yelp_content_itemcf.json"
            similarity_path.write_text(json.dumps({"b1": []}), encoding="utf-8")
            with patch.object(YelpService, "SIMILARITY_FILE", similarity_path):
                response = self.client.get(f"/api/v1/yelp/restaurants/{self.business.business_id}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Excellent omakase.")

    def test_yelp_business_detail_returns_404_for_unknown_business(self) -> None:
        response = self.client.get("/api/v1/yelp/restaurants/missing/")

        self.assertEqual(response.status_code, 404)
