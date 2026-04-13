from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.recommendations.models import YelpReview
from apps.recommendations.spark_jobs import build_yelp_als_recommendations


class Command(BaseCommand):
    help = "Build Yelp ALS user recommendations with Spark from ORM review interactions."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--output",
            default="data/recommendations/yelp_als_userrec.json",
            help="Output JSON path for Spark ALS user recommendations.",
        )
        parser.add_argument("--rank", type=int, default=20)
        parser.add_argument("--max-iter", type=int, default=10)
        parser.add_argument("--reg-param", type=float, default=0.1)
        parser.add_argument("--top-k", type=int, default=20)

    def handle(self, *args: Any, **options: Any) -> None:
        interactions = list(
            YelpReview.objects.order_by("user_id", "business__business_id", "-review_date", "-id")
            .values("user_id", "business__business_id", "stars")
        )
        if not interactions:
            self.stdout.write(self.style.WARNING("No YelpReview rows found; nothing built."))
            return

        latest_pairs: dict[tuple[int, str], dict[str, Any]] = {}
        for row in interactions:
            user_id = int(row["user_id"])
            business_id = str(row["business__business_id"])
            key = (user_id, business_id)
            if key not in latest_pairs:
                latest_pairs[key] = {
                    "user_id": str(user_id),
                    "business_id": business_id,
                    "stars": float(row["stars"]),
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "yelp_als_interactions.jsonl"
            temp_path.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in latest_pairs.values()),
                encoding="utf-8",
            )
            try:
                build_yelp_als_recommendations(
                    interactions_path=temp_path,
                    output_path=options["output"],
                    rank=max(int(options["rank"]), 1),
                    max_iter=max(int(options["max_iter"]), 1),
                    reg_param=float(options["reg_param"]),
                    top_k=max(int(options["top_k"]), 1),
                )
            except (FileNotFoundError, RuntimeError) as exc:
                raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Wrote {options['output']}"))
