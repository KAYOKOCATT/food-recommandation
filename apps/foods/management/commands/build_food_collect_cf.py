from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.foods.models import Collect
from apps.recommendations.collect_cf import (
    item_cf_similarities,
    serialize_recommendations,
    user_cf_recommendations,
)


class Command(BaseCommand):
    help = "Build offline ItemCF/UserCF JSON files from Collect implicit feedback."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--output-dir",
            default="data/recommendations",
            help="Directory for generated JSON files.",
        )
        parser.add_argument(
            "--algorithm",
            choices=["itemcf", "usercf", "both"],
            default="both",
        )
        parser.add_argument("--top-k", type=int, default=20)
        parser.add_argument("--similar-user-k", type=int, default=20)

    def handle(self, *args: Any, **options: Any) -> None:
        interactions = list(
            Collect.objects.order_by("user_id", "food_id")
            .values_list("user_id", "food_id")
        )
        if not interactions:
            self.stdout.write(self.style.WARNING("No Collect rows found; nothing built."))
            return

        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        top_k = max(int(options["top_k"]), 1)
        algorithm = options["algorithm"]

        if algorithm in {"itemcf", "both"}:
            item_path = output_dir / "food_itemcf.json"
            item_data = serialize_recommendations(
                item_cf_similarities(interactions, top_k=top_k)
            )
            _write_json(item_path, item_data)
            self.stdout.write(self.style.SUCCESS(f"Wrote {item_path}"))

        if algorithm in {"usercf", "both"}:
            user_path = output_dir / "food_usercf.json"
            user_data = serialize_recommendations(
                user_cf_recommendations(
                    interactions,
                    top_k=top_k,
                    similar_user_k=max(int(options["similar_user_k"]), 1),
                )
            )
            _write_json(user_path, user_data)
            self.stdout.write(self.style.SUCCESS(f"Wrote {user_path}"))


def _write_json(path: Path, data: dict[str, list[dict[str, float | str]]]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
