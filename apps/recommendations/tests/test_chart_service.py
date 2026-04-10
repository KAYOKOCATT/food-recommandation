from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.recommendations.services.chart_service import ChartService
from apps.recommendations.views.charts import ChartView


class ChartServiceTests(SimpleTestCase):
    def test_restaurant_geo_data_filters_non_us_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            _write_json(
                data_dir / "yelp_business_profiles.json",
                {
                    "profiles": [
                        _profile("us1", "Philadelphia Cafe", "PA"),
                        _profile("ca1", "Edmonton Cafe", "AB"),
                        _profile("us2", "Tampa Sushi", "FL"),
                    ],
                },
            )

            with patch.object(ChartService, "DATA_DIR", data_dir):
                result = ChartService.get_restaurant_geo_data(limit=10)

        self.assertEqual([item["state"] for item in result], ["PA", "FL"])
        self.assertEqual(result[0]["value"], [-75.0, 40.0, 4.0, 80])

    def test_restaurant_geo_data_returns_empty_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(ChartService, "DATA_DIR", Path(temp_dir)):
                result = ChartService.get_restaurant_geo_data()

        self.assertEqual(result, [])

    def test_similarity_network_uses_stable_review_count_symbol_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            _write_json(
                data_dir / "yelp_business_profiles.json",
                {
                    "profiles": [
                        _profile("b1", "Pastry One", "PA", review_count=25),
                        _profile("b2", "Pastry Two", "PA", review_count=250),
                    ],
                },
            )
            _write_json(
                data_dir / "yelp_content_itemcf.json",
                {
                    "b1": [{"business_id": "b2", "score": 0.8}],
                    "b2": [{"business_id": "b1", "score": 0.8}],
                },
            )

            with patch.object(ChartService, "DATA_DIR", data_dir):
                result = ChartService.get_similarity_network(limit=2, similarity_threshold=0.5)

        nodes = {item["id"]: item for item in result["nodes"]}
        self.assertEqual(nodes["b1"]["symbolSize"], 10)
        self.assertEqual(nodes["b2"]["symbolSize"], 15)
        self.assertEqual(result["links"], [{"source": "b1", "target": "b2", "value": 0.8}])
        self.assertEqual(result["categories"], [{"name": "Restaurants"}])


class ChartViewTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_restaurant_geo_rejects_invalid_limit(self) -> None:
        request = self.factory.get("/api/v1/charts/restaurant-geo/?limit=bad")

        response = ChartView.restaurant_geo(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)["msg"], "limit参数必须是整数")

    def test_similarity_network_rejects_invalid_params(self) -> None:
        request = self.factory.get("/api/v1/charts/similarity-network/?threshold=bad")

        response = ChartView.similarity_network(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)["msg"], "参数格式错误")


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _profile(
    business_id: str,
    name: str,
    state: str,
    review_count: int = 80,
) -> dict[str, object]:
    return {
        "business_id": business_id,
        "name": name,
        "categories": "Restaurants, Cafes",
        "stars": 4.0,
        "review_count": review_count,
        "city": "Sample City",
        "state": state,
        "latitude": 40.0,
        "longitude": -75.0,
    }
