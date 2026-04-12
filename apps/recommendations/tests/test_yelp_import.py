from __future__ import annotations

import json
import tempfile
from io import StringIO
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

    def test_import_yelp_data_reports_review_skip_reasons(self) -> None:
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
                    },
                    {
                        "review_id": "r2",
                        "business_id": "missing_business",
                        "user_id": "u1",
                        "stars": 4,
                        "text": "Missing business.",
                    },
                    {
                        "review_id": "r3",
                        "business_id": "b1",
                        "user_id": "missing_user",
                        "stars": 4,
                        "text": "Missing user.",
                    },
                    {
                        "business_id": "b1",
                        "user_id": "u1",
                        "stars": 3,
                        "text": "Missing review id.",
                    },
                ],
            )

            output = StringIO()
            call_command("import_yelp_data", "--mode", "all", "--data-dir", str(data_dir), stdout=output)

        output_text = output.getvalue()
        self.assertEqual(YelpReview.objects.count(), 1)
        self.assertEqual(YelpBusiness.objects.get().aggregated_review_count, 1)
        self.assertIn("Imported/updated 1 Yelp reviews. Skipped 3 rows", output_text)
        self.assertIn("missing review_id=1", output_text)
        self.assertIn("missing business=1", output_text)
        self.assertIn("missing user=1", output_text)

    def test_import_yelp_data_is_idempotent_for_reviews(self) -> None:
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
            call_command("import_yelp_data", "--mode", "reviews", "--data-dir", str(data_dir))

        self.assertEqual(YelpReview.objects.count(), 1)
        self.assertEqual(YelpBusiness.objects.get().aggregated_review_count, 1)

    def test_import_yelp_data_keeps_multiple_reviews_for_same_user_and_business(self) -> None:
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
                        "stars": 3,
                        "text": "First visit.",
                        "date": "2024-01-01 10:00:00",
                    },
                    {
                        "review_id": "r2",
                        "business_id": "b1",
                        "user_id": "u1",
                        "stars": 5,
                        "text": "Second visit.",
                        "date": "2024-02-01 10:00:00",
                    },
                ],
            )

            call_command("import_yelp_data", "--mode", "all", "--data-dir", str(data_dir))

        self.assertEqual(YelpReview.objects.count(), 2)
        self.assertEqual(
            YelpReview.objects.filter(business__business_id="b1", user__external_user_id="u1").count(),
            2,
        )
        self.assertEqual(YelpBusiness.objects.get().aggregated_review_count, 2)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
