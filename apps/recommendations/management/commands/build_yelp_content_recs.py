from __future__ import annotations

# pylint: disable=too-many-locals

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.recommendations.yelp_content import (
    build_business_profiles,
    build_yelp_content_recommendations,
    iter_json_lines,
    serialize_similarity,
)


class Command(BaseCommand):
    """Django entrypoint for the offline Yelp TF-IDF content build."""

    help = "Build offline Yelp restaurant content-based similarity JSON from TF-IDF."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register command-line controls for dev sampling and full offline builds."""
        parser.add_argument(
            "--data-dir",
            default="data/archive_4",
            help="Directory containing Yelp Academic Dataset JSONL files.",
        )
        parser.add_argument(
            "--output",
            default="data/recommendations/yelp_content_itemcf.json",
            help="Output JSON path for business-to-business content similarities.",
        )
        parser.add_argument(
            "--metadata-output",
            default="data/recommendations/yelp_business_profiles.json",
            help="Output JSON path for filtered business metadata.",
        )
        parser.add_argument("--top-k", type=int, default=20)
        parser.add_argument("--max-features", type=int, default=5000)
        parser.add_argument("--min-business-review-count", type=int, default=10)
        parser.add_argument(
            "--review-line-limit",
            type=int,
            default=0,
            help="Limit review JSONL lines for development runs. 0 means unlimited.",
        )
        parser.add_argument(
            "--business-limit",
            type=int,
            default=0,
            help="Limit filtered businesses for development runs. 0 means unlimited.",
        )
        parser.add_argument(
            "--include-closed",
            action="store_true",
            help="Include Yelp businesses with is_open=0.",
        )
        parser.add_argument(
            "--max-reviews-per-business",
            type=int,
            default=50,
            help="Maximum review texts aggregated per business. 0 means unlimited.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Load Yelp JSONL data, build TF-IDF neighbors, and write JSON artifacts."""
        data_dir = Path(options["data_dir"])
        business_path = data_dir / "yelp_academic_dataset_business.json"
        review_path = data_dir / "yelp_academic_dataset_review.json"
        if not business_path.exists():
            raise CommandError(f"Business file not found: {business_path}")
        if not review_path.exists():
            raise CommandError(f"Review file not found: {review_path}")

        top_k = max(int(options["top_k"]), 1)
        max_features = max(int(options["max_features"]), 1)
        min_business_review_count = max(int(options["min_business_review_count"]), 0)
        review_line_limit = _zero_as_none(int(options["review_line_limit"]))
        business_limit = _zero_as_none(int(options["business_limit"]))
        max_reviews_per_business = _zero_as_none(int(options["max_reviews_per_business"]))

        # Stream raw Yelp JSONL files; the review file is large, so avoid eager loading.
        self.stdout.write("Loading Yelp business/review records...")
        profiles = build_business_profiles(
            iter_json_lines(business_path),
            iter_json_lines(review_path, limit=review_line_limit),
            min_business_review_count=min_business_review_count,
            business_limit=business_limit,
            include_closed=bool(options["include_closed"]),
            max_reviews_per_business=max_reviews_per_business,
        )
        if len(profiles) < 2:
            raise CommandError(
                f"Need at least 2 restaurant profiles, got {len(profiles)}."
            )

        # Convert the filtered restaurant corpus into TF-IDF vectors and top-k neighbors.
        self.stdout.write(
            f"Building TF-IDF similarities for {len(profiles)} Yelp restaurants..."
        )
        result = build_yelp_content_recommendations(
            profiles,
            top_k=top_k,
            max_features=max_features,
        )

        output_path = Path(options["output"])
        metadata_path = Path(options["metadata_output"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        # Keep recommendation candidates and inspectable metadata as separate artifacts.
        output_path.write_text(
            json.dumps(
                serialize_similarity(result.similarities),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        metadata_path.write_text(
            json.dumps(
                {
                    "feature_count": result.feature_count,
                    "business_count": len(result.profiles),
                    "profiles": [
                        profile.to_metadata()
                        for profile in result.profiles
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {output_path} and {metadata_path} "
                f"({result.feature_count} TF-IDF features)."
            )
        )


def _zero_as_none(value: int) -> int | None:
    """Treat CLI value 0 as an unlimited option."""
    return None if value == 0 else max(value, 1)
