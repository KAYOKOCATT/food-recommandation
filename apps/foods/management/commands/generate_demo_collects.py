from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import F

from apps.foods.models import Collect, Foods
from apps.users.models import User


@dataclass(frozen=True)
class DemoCollectOptions:
    seed: int
    per_user: int
    explore_rate: float
    dry_run: bool


class Command(BaseCommand):
    help = "Generate clearly marked demo Collect rows for Chinese dish CF demos."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--seed", type=int, default=20260410)
        parser.add_argument("--per-user", type=int, default=8)
        parser.add_argument("--explore-rate", type=float, default=0.25)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        demo_options = DemoCollectOptions(
            seed=int(options["seed"]),
            per_user=max(int(options["per_user"]), 1),
            explore_rate=min(max(float(options["explore_rate"]), 0.0), 1.0),
            dry_run=bool(options["dry_run"]),
        )
        rng = random.Random(demo_options.seed)

        users = list(User.objects.order_by("id"))
        foods = list(Foods.objects.order_by("id"))
        if not users or not foods:
            self.stdout.write(self.style.WARNING("No users or foods found; nothing generated."))
            return

        foods_by_type: dict[str, list[Foods]] = defaultdict(list)
        for food in foods:
            foods_by_type[food.foodtype].append(food)

        created_count = 0
        skipped_count = 0
        for user in users:
            created, skipped = _generate_collects_for_user(
                rng,
                user=user,
                foods=foods,
                foods_by_type=foods_by_type,
                options=demo_options,
            )
            created_count += created
            skipped_count += skipped

        action = "Would create" if demo_options.dry_run else "Created"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} {created_count} demo collects; skipped {skipped_count} existing rows."
            )
        )
        self.stdout.write(
            "These rows are synthetic implicit feedback for demos, not real behavior data."
        )


def _pick_preferred_types(rng: random.Random, foodtypes: list[str]) -> list[str]:
    if len(foodtypes) <= 2:
        return foodtypes
    return rng.sample(foodtypes, k=min(2, len(foodtypes)))


def _generate_collects_for_user(
    rng: random.Random,
    *,
    user: User,
    foods: list[Foods],
    foods_by_type: dict[str, list[Foods]],
    options: DemoCollectOptions,
) -> tuple[int, int]:
    preferred_types = _pick_preferred_types(rng, list(foods_by_type.keys()))
    candidates = _pick_foods_for_user(
        rng,
        foods=foods,
        foods_by_type=foods_by_type,
        preferred_types=preferred_types,
        options=options,
    )

    created_count = 0
    skipped_count = 0
    for food in candidates:
        if options.dry_run:
            if Collect.objects.filter(user=user, food=food).exists():
                skipped_count += 1
            else:
                created_count += 1
            continue

        _, created = Collect.objects.get_or_create(user=user, food=food)
        if created:
            Foods.objects.filter(id=food.id).update(collect_count=F("collect_count") + 1)
            created_count += 1
        else:
            skipped_count += 1
    return created_count, skipped_count


def _pick_foods_for_user(
    rng: random.Random,
    *,
    preferred_types: list[str],
    foods: list[Foods],
    foods_by_type: dict[str, list[Foods]],
    options: DemoCollectOptions,
) -> list[Foods]:
    preferred_pool = [
        food
        for foodtype in preferred_types
        for food in foods_by_type.get(foodtype, [])
    ]
    result: list[Foods] = []
    attempts = 0

    while (
        len(result) < min(options.per_user, len(foods))
        and attempts < options.per_user * 10
    ):
        attempts += 1
        use_global_pool = rng.random() < options.explore_rate or not preferred_pool
        pool = foods if use_global_pool else preferred_pool
        food = rng.choice(pool)
        if food not in result:
            result.append(food)
    return result
