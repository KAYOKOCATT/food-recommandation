from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.recommendations.services import HomeWordCloudService


class Command(BaseCommand):
    help = "Build offline PNG word clouds for the user home page."

    def handle(self, *args: Any, **options: Any) -> None:
        outputs = HomeWordCloudService.build_all()
        self.stdout.write(
            self.style.SUCCESS(
                "Wrote "
                f"{outputs['food']} and {outputs['yelp']}."
            )
        )
