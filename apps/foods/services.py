from dataclasses import dataclass
from pathlib import Path

from django.db.models import QuerySet

from apps.recommendations.services import (
    RecommendationCandidate,
    rerank_from_recent_items,
    similarity_cache,
)

from .models import Collect, Foods


@dataclass(frozen=True)
class FoodRecommendation:
    food: Foods
    score: float
    source: str


def popular_foods(limit: int = 20) -> QuerySet[Foods]:
    """Statistical fallback for Chinese dish data."""
    safe_limit = max(limit, 1)
    return (
        Foods.objects.order_by("-collect_count", "-comment_count", "foodtype", "foodname")[
            :safe_limit
        ]
    )


def recommend_foods_by_itemcf(
    user_id: int,
    similarity_file: str | Path,
    *,
    top_k: int = 20,
) -> list[FoodRecommendation]:
    recent_food_ids = [
        str(food_id)
        for food_id in Collect.objects.filter(user_id=user_id)
        .order_by("-added_time")
        .values_list("food_id", flat=True)
    ]
    candidates = rerank_from_recent_items(
        recent_food_ids,
        similarity_file,
        top_k=top_k,
    )
    return _hydrate_food_candidates(candidates, source="itemcf")


def recommend_foods_by_usercf(
    user_id: int,
    recommendation_file: str | Path,
    *,
    top_k: int = 20,
) -> list[FoodRecommendation]:
    seen_food_ids = set(
        Collect.objects.filter(user_id=user_id).values_list("food_id", flat=True)
    )
    candidates = [
        candidate
        for candidate in similarity_cache.get(recommendation_file).get(str(user_id), [])
        if int(candidate.item_id) not in seen_food_ids
    ][:top_k]
    return _hydrate_food_candidates(candidates, source="usercf")


def _hydrate_food_candidates(
    candidates: list[RecommendationCandidate],
    *,
    source: str,
) -> list[FoodRecommendation]:
    food_ids = [int(candidate.item_id) for candidate in candidates]
    foods_by_id = Foods.objects.in_bulk(food_ids)
    return [
        FoodRecommendation(
            food=foods_by_id[food_id],
            score=candidate.score,
            source=source,
        )
        for candidate in candidates
        if (food_id := int(candidate.item_id)) in foods_by_id
    ]
