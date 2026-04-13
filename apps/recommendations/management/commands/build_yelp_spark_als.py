from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.recommendations.spark_jobs import build_yelp_als_recommendations


class Command(BaseCommand):
    help = "Build Yelp ALS user recommendations with Spark from raw Yelp archive JSONL files."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--data-dir",
            default="data/archive_4",
            help="Directory containing Yelp Academic Dataset JSONL files.",
        )
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
        try:
            build_yelp_als_recommendations(
                data_dir=options["data_dir"],
                output_path=options["output"],
                rank=max(int(options["rank"]), 1),
                max_iter=max(int(options["max_iter"]), 1),
                reg_param=float(options["reg_param"]),
                top_k=max(int(options["top_k"]), 1),
            )
        except (FileNotFoundError, RuntimeError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"Wrote {options['output']}"))
