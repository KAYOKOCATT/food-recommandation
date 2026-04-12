from __future__ import annotations

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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

            with patch(
                "apps.recommendations.management.commands.import_yelp_data.save_yelp_demo_candidates"
            ):
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

            with patch(
                "apps.recommendations.management.commands.import_yelp_data.save_yelp_demo_candidates"
            ):
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
            with patch(
                "apps.recommendations.management.commands.import_yelp_data.save_yelp_demo_candidates"
            ):
                call_command(
                    "import_yelp_data",
                    "--mode",
                    "all",
                    "--data-dir",
                    str(data_dir),
                    stdout=output,
                )

        output_text = output.getvalue()
        self.assertEqual(YelpReview.objects.count(), 1)
        self.assertEqual(YelpBusiness.objects.get().aggregated_review_count, 1)
        self.assertIn("Imported/updated 1 Yelp reviews.", output_text)
        self.assertIn("Scanned 4 rows; matched business filter 1;", output_text)
        self.assertIn("business_not_target=1", output_text)
        self.assertIn("user_not_target=1", output_text)
        self.assertIn("missing review_id=1", output_text)
        self.assertIn("missing business=0", output_text)
        self.assertIn("missing user=0", output_text)

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

            with patch(
                "apps.recommendations.management.commands.import_yelp_data.save_yelp_demo_candidates"
            ):
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

            with patch(
                "apps.recommendations.management.commands.import_yelp_data.save_yelp_demo_candidates"
            ):
                call_command("import_yelp_data", "--mode", "all", "--data-dir", str(data_dir))

        self.assertEqual(YelpReview.objects.count(), 2)
        self.assertEqual(
            YelpReview.objects.filter(business__business_id="b1", user__external_user_id="u1").count(),
            2,
        )
        self.assertEqual(YelpBusiness.objects.get().aggregated_review_count, 2)

    def test_import_yelp_data_keeps_only_reviews_for_selected_businesses_and_users(self) -> None:
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
                        "review_count": 120,
                        "is_open": 1,
                        "city": "Philadelphia",
                        "state": "PA",
                        "latitude": 1.0,
                        "longitude": 2.0,
                    },
                    {
                        "business_id": "b2",
                        "name": "Beta Sushi",
                        "categories": "Restaurants, Sushi Bars",
                        "stars": 4.1,
                        "review_count": 80,
                        "is_open": 1,
                        "city": "Boston",
                        "state": "MA",
                        "latitude": 3.0,
                        "longitude": 4.0,
                    },
                ],
            )
            _write_jsonl(
                data_dir / "yelp_academic_dataset_user.json",
                [
                    {"user_id": "u1", "name": "Yelp Alice"},
                    {"user_id": "u2", "name": "Yelp Bob"},
                    {"user_id": "u3", "name": "Yelp Carol"},
                ],
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
                    },
                    {
                        "review_id": "r2",
                        "business_id": "b1",
                        "user_id": "u2",
                        "stars": 4,
                        "text": "Pretty good.",
                    },
                    {
                        "review_id": "r3",
                        "business_id": "b2",
                        "user_id": "u3",
                        "stars": 3,
                        "text": "Not in selected business set.",
                    },
                ],
            )

            with patch(
                "apps.recommendations.management.commands.import_yelp_data.save_yelp_demo_candidates"
            ):
                call_command(
                    "import_yelp_data",
                    "--mode",
                    "all",
                    "--data-dir",
                    str(data_dir),
                    "--target-business-count",
                    "1",
                    "--target-user-count",
                    "1",
                    "--target-review-count",
                    "1",
                    "--min-business-review-count",
                    "1",
                )

        self.assertEqual(list(YelpBusiness.objects.values_list("business_id", flat=True)), ["b1"])
        self.assertEqual(list(User.objects.filter(source="yelp").values_list("external_user_id", flat=True)), ["u1"])
        self.assertEqual(list(YelpReview.objects.values_list("review_id", flat=True)), ["r1"])

    def test_import_yelp_data_refreshes_only_affected_businesses(self) -> None:
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
                    },
                    {
                        "business_id": "b2",
                        "name": "Beta Sushi",
                        "categories": "Restaurants, Sushi Bars",
                        "stars": 4.2,
                        "review_count": 11,
                        "is_open": 1,
                        "city": "Philadelphia",
                        "state": "PA",
                        "latitude": 3.0,
                        "longitude": 4.0,
                    },
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
                    }
                ],
            )

            with patch(
                "apps.recommendations.management.commands.import_yelp_data.save_yelp_demo_candidates"
            ), patch(
                "apps.recommendations.management.commands.import_yelp_data.YelpService.refresh_aggregated_review_counts"
            ) as refresh_counts:
                call_command(
                    "import_yelp_data",
                    "--mode",
                    "all",
                    "--data-dir",
                    str(data_dir),
                    "--target-business-count",
                    "2",
                    "--target-user-count",
                    "1",
                    "--target-review-count",
                    "1",
                    "--min-business-review-count",
                    "1",
                )

        affected_ids = sorted(YelpBusiness.objects.filter(business_id="b1").values_list("id", flat=True))
        refresh_counts.assert_called_once_with(affected_ids)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
