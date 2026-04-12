from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.users.demo_candidates import save_yelp_demo_candidates


class Command(BaseCommand):
    help = "Refresh the offline Yelp demo-user candidate JSON used by the login page."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--candidate-count", type=int, default=100)
        parser.add_argument(
            "--output",
            default=None,
            help="Optional JSON output path. Defaults to data/recommendations/yelp_demo_users.json.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        candidates = save_yelp_demo_candidates(
            candidate_count=max(int(options["candidate_count"]), 0),
            output_path=options["output"],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Refreshed {len(candidates)} Yelp demo candidates.")
        )
