from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.recommendations.models import YelpReview
from apps.recommendations.review_cf import (
    filter_rating_interactions,
    latest_rating_interactions,
    serialize_business_recommendations,
    user_cf_recommendations_from_ratings,
)


class Command(BaseCommand):
    help = "Build offline Yelp UserCF JSON from rating interactions stored in YelpReview."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--output",
            default="data/recommendations/yelp_usercf.json",
            help="Output JSON path for Yelp user-based CF recommendations.",
        )
        parser.add_argument("--top-k", type=int, default=20)
        parser.add_argument("--similar-user-k", type=int, default=20)
        parser.add_argument("--min-user-reviews", type=int, default=5)
        parser.add_argument("--min-business-reviews", type=int, default=10)
        parser.add_argument("--min-common-items", type=int, default=2)

    def handle(self, *args: Any, **options: Any) -> None:
        raw_interactions = list(
            YelpReview.objects.order_by("user_id", "business__business_id").values_list(
                "user_id",
                "business__business_id",
                "stars",
                "review_date",
                "id",
            )
        )
        if not raw_interactions:
            self.stdout.write(self.style.WARNING("No YelpReview rows found; nothing built."))
            return
        interactions = latest_rating_interactions(raw_interactions)

        filtered_interactions = filter_rating_interactions(
            interactions,
            min_user_reviews=max(int(options["min_user_reviews"]), 1),
            min_business_reviews=max(int(options["min_business_reviews"]), 1),
        )
        if not filtered_interactions:
            self.stdout.write(
                self.style.WARNING("No rating interactions remain after filtering; nothing built.")
            )
            return

        recommendations = user_cf_recommendations_from_ratings(
            filtered_interactions,
            top_k=max(int(options["top_k"]), 1),
            similar_user_k=max(int(options["similar_user_k"]), 1),
            min_common_items=max(int(options["min_common_items"]), 1),
        )
        if not any(recommendations.values()):
            self.stdout.write(
                self.style.WARNING("No Yelp UserCF candidates generated; nothing built.")
            )
            return

        output_path = Path(options["output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                serialize_business_recommendations(recommendations),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(f"Wrote {output_path}"))
