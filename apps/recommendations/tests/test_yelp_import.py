from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.recommendations.models import YelpBusiness, YelpReview
from apps.users.models import User


class YelpImportCommandTests(TestCase):
    def test_import_yelp_data_loads_businesses_users_and_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            _write_jsonl(
                data_dir / "yelp_academic_dataset_business.json",
                [
                    {
                        "business_id": "b1",
                        "name": "Alpha Sushi",
                        "categories": "Restaurants, Sushi Bars",
                        "stars": 4.5,
                        "review_count": 12,
                        "is_open": 1,
                        "city": "Philadelphia",
                        "state": "PA",
                        "latitude": 1.0,
                        "longitude": 2.0,
                    }
                ],
            )
            _write_jsonl(
                data_dir / "yelp_academic_dataset_user.json",
                [{"user_id": "u1", "name": "Yelp Alice"}],
            )
            _write_jsonl(
                data_dir / "yelp_academic_dataset_review.json",
                [
                    {
                        "review_id": "r1",
                        "business_id": "b1",
                        "user_id": "u1",
                        "stars": 5,
                        "text": "Excellent omakase.",
                        "date": "2024-01-02 03:04:05",
                    }
                ],
            )

            call_command("import_yelp_data", "--mode", "all", "--data-dir", str(data_dir))

        self.assertEqual(YelpBusiness.objects.count(), 1)
        self.assertEqual(User.objects.filter(source="yelp").count(), 1)
        self.assertEqual(YelpReview.objects.count(), 1)
        self.assertEqual(YelpBusiness.objects.get().aggregated_review_count, 1)
        self.assertEqual(User.objects.get(source="yelp").username, "yelp_u1")

    def test_import_yelp_data_skips_non_restaurants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            _write_jsonl(
                data_dir / "yelp_academic_dataset_business.json",
                [
                    {
                        "business_id": "b1",
                        "name": "Pet Shop",
                        "categories": "Pet Food, Retail",
                        "stars": 4.5,
                        "review_count": 20,
                        "is_open": 1,
                        "city": "Philadelphia",
                        "state": "PA",
                        "latitude": 1.0,
                        "longitude": 2.0,
                    }
                ],
            )

            call_command("import_yelp_data", "--mode", "businesses", "--data-dir", str(data_dir))

        self.assertEqual(YelpBusiness.objects.count(), 0)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
