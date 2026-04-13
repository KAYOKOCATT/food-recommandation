from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.recommendations.spark_jobs import build_yelp_spark_stats


class Command(BaseCommand):
    help = "Build Yelp aggregate statistics with Spark SQL from raw Yelp JSONL files."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--data-dir",
            default="data/archive_4",
            help="Directory containing Yelp Academic Dataset JSONL files.",
        )
        parser.add_argument(
            "--output-dir",
            default="data/recommendations",
            help="Directory for generated Spark statistics JSON files.",
        )
        parser.add_argument("--top-k", type=int, default=10)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            outputs = build_yelp_spark_stats(
                data_dir=options["data_dir"],
                output_dir=options["output_dir"],
                top_k=max(int(options["top_k"]), 1),
            )
        except (FileNotFoundError, RuntimeError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Wrote Spark statistics: "
                + ", ".join(str(path) for path in outputs.values())
            )
        )
