from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import RequestFactory, TestCase

from apps.recommendations.models import YelpBusiness
from apps.recommendations.services.chart_service import ChartService
from apps.recommendations.views.charts import ChartView


class ChartServiceTests(TestCase):
    def test_restaurant_geo_data_uses_orm_and_filters_invalid_rows(self) -> None:
        YelpBusiness.objects.create(
            business_id="us1",
            name="Philadelphia Cafe",
            categories="Restaurants, Cafes",
            stars=4.0,
            review_count=80,
            city="Philadelphia",
            state="PA",
            latitude=40.0,
            longitude=-75.0,
        )
        YelpBusiness.objects.create(
            business_id="ca1",
            name="Edmonton Cafe",
            categories="Restaurants, Cafes",
            stars=4.7,
            review_count=120,
            city="Edmonton",
            state="AB",
            latitude=53.5,
            longitude=-113.5,
        )
        YelpBusiness.objects.create(
            business_id="us2",
            name="No Coordinates",
            categories="Restaurants, Cafes",
            stars=4.5,
            review_count=90,
            city="Tampa",
            state="FL",
        )
        YelpBusiness.objects.create(
            business_id="us3",
            name="Tampa Sushi",
            categories="Restaurants, Sushi Bars",
            stars=4.2,
            review_count=70,
            city="Tampa",
            state="FL",
            latitude=27.9,
            longitude=-82.5,
        )

        result = ChartService.get_restaurant_geo_data(limit=10)

        self.assertEqual([item["state"] for item in result], ["PA", "FL"])
        self.assertEqual(result[0]["value"], [-75.0, 40.0, 4.0, 80])
        self.assertEqual(result[1]["name"], "Tampa Sushi")

    def test_restaurant_geo_data_returns_empty_when_database_has_no_rows(self) -> None:
        result = ChartService.get_restaurant_geo_data()

        self.assertEqual(result, [])

    def test_similarity_network_uses_orm_metadata_and_stable_symbol_size(self) -> None:
        YelpBusiness.objects.create(
            business_id="b1",
            name="Pastry One",
            categories="Restaurants, Cafes",
            stars=4.0,
            review_count=25,
            city="Philadelphia",
            state="PA",
            latitude=40.0,
            longitude=-75.0,
        )
        YelpBusiness.objects.create(
            business_id="b2",
            name="Pastry Two",
            categories="Restaurants, Cafes",
            stars=4.0,
            review_count=250,
            city="Philadelphia",
            state="PA",
            latitude=40.1,
            longitude=-75.1,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            _write_json(
                data_dir / "yelp_content_itemcf.json",
                {
                    "b1": [{"business_id": "b2", "score": 0.8}],
                    "b2": [{"business_id": "b1", "score": 0.8}],
                },
            )

            with patch.object(ChartService, "DATA_DIR", data_dir):
                result = ChartService.get_similarity_network(
                    limit=2,
                    similarity_threshold=0.5,
                )

        nodes = {item["id"]: item for item in result["nodes"]}
        self.assertEqual(nodes["b1"]["symbolSize"], 10)
        self.assertEqual(nodes["b2"]["symbolSize"], 15)
        self.assertEqual(result["links"], [{"source": "b1", "target": "b2", "value": 0.8}])
        self.assertEqual(result["categories"], [{"name": "Restaurants"}])

    def test_similarity_network_returns_empty_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(ChartService, "DATA_DIR", Path(temp_dir)):
                result = ChartService.get_similarity_network()

        self.assertEqual(result, {"nodes": [], "links": [], "categories": []})

    def test_similarity_network_returns_empty_when_json_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "yelp_content_itemcf.json").write_text("{invalid", encoding="utf-8")
            with patch.object(ChartService, "DATA_DIR", data_dir):
                result = ChartService.get_similarity_network()

        self.assertEqual(result, {"nodes": [], "links": [], "categories": []})

    def test_similarity_network_skips_candidates_missing_in_database(self) -> None:
        YelpBusiness.objects.create(
            business_id="b1",
            name="Pastry One",
            categories="Restaurants, Cafes",
            stars=4.0,
            review_count=25,
            city="Philadelphia",
            state="PA",
            latitude=40.0,
            longitude=-75.0,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            _write_json(
                data_dir / "yelp_content_itemcf.json",
                {"b1": [{"business_id": "missing", "score": 0.8}]},
            )
            with patch.object(ChartService, "DATA_DIR", data_dir):
                result = ChartService.get_similarity_network(
                    limit=2,
                    similarity_threshold=0.5,
                )

        self.assertEqual(
            result["nodes"],
            [
                {
                    "id": "b1",
                    "name": "Pastry One",
                    "category": "Restaurants",
                    "symbolSize": 10,
                }
            ],
        )
        self.assertEqual(result["links"], [])


class ChartViewTests(TestCase):
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
