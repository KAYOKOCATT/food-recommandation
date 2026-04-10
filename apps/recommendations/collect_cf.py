from __future__ import annotations

from collections import defaultdict
from math import sqrt

from .services import RecommendationCandidate

Interaction = tuple[int, int]


def build_user_items(interactions: list[Interaction]) -> dict[int, set[int]]:
    user_items: dict[int, set[int]] = defaultdict(set)
    for user_id, item_id in interactions:
        user_items[user_id].add(item_id)
    return dict(user_items)


def build_item_users(interactions: list[Interaction]) -> dict[int, set[int]]:
    item_users: dict[int, set[int]] = defaultdict(set)
    for user_id, item_id in interactions:
        item_users[item_id].add(user_id)
    return dict(item_users)


def item_cf_similarities(
    interactions: list[Interaction],
    *,
    top_k: int = 20,
) -> dict[str, list[RecommendationCandidate]]:
    item_users = build_item_users(interactions)
    co_counts: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    user_items = build_user_items(interactions)
    for items in user_items.values():
        item_list = sorted(items)
        for left_index, left_item in enumerate(item_list):
            for right_item in item_list[left_index + 1:]:
                co_counts[left_item][right_item] += 1
                co_counts[right_item][left_item] += 1

    similarities: dict[str, list[RecommendationCandidate]] = {}
    for item_id, neighbors in co_counts.items():
        candidates = [
            RecommendationCandidate(
                item_id=str(other_item_id),
                score=count / sqrt(len(item_users[item_id]) * len(item_users[other_item_id])),
            )
            for other_item_id, count in neighbors.items()
        ]
        similarities[str(item_id)] = sorted(
            candidates,
            key=lambda candidate: candidate.score,
            reverse=True,
        )[:top_k]
    return similarities


def user_cf_recommendations(
    interactions: list[Interaction],
    *,
    top_k: int = 20,
    similar_user_k: int = 20,
) -> dict[str, list[RecommendationCandidate]]:
    user_items = build_user_items(interactions)
    recommendations: dict[str, list[RecommendationCandidate]] = {}

    for user_id, items in user_items.items():
        user_sims: list[tuple[int, float]] = []
        for other_user_id, other_items in user_items.items():
            if other_user_id == user_id:
                continue
            common_count = len(items & other_items)
            if common_count == 0:
                continue
            similarity = common_count / sqrt(len(items) * len(other_items))
            user_sims.append((other_user_id, similarity))

        scores: dict[int, float] = defaultdict(float)
        for other_user_id, similarity in sorted(
            user_sims,
            key=lambda item: item[1],
            reverse=True,
        )[:similar_user_k]:
            for item_id in user_items[other_user_id] - items:
                scores[item_id] += similarity

        candidates = [
            RecommendationCandidate(item_id=str(item_id), score=score)
            for item_id, score in scores.items()
        ]
        recommendations[str(user_id)] = sorted(
            candidates,
            key=lambda candidate: candidate.score,
            reverse=True,
        )[:top_k]

    return recommendations


def serialize_recommendations(
    recommendations: dict[str, list[RecommendationCandidate]],
) -> dict[str, list[dict[str, float | str]]]:
    return {
        key: [
            {"item_id": candidate.item_id, "score": round(candidate.score, 6)}
            for candidate in candidates
        ]
        for key, candidates in recommendations.items()
    }
