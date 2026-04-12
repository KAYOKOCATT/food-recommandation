from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import sqrt

from apps.recommendations.services.similarity import RecommendationCandidate

RatingInteraction = tuple[int, str, float]
RawRatingInteraction = tuple[int, str, float, datetime | None, int]


def build_user_ratings(
    interactions: list[RatingInteraction],
) -> dict[int, dict[str, float]]:
    user_ratings: dict[int, dict[str, float]] = defaultdict(dict)
    for user_id, business_id, stars in interactions:
        user_ratings[user_id][business_id] = stars
    return dict(user_ratings)


def filter_rating_interactions(
    interactions: list[RatingInteraction],
    *,
    min_user_reviews: int,
    min_business_reviews: int,
) -> list[RatingInteraction]:
    filtered = list(interactions)
    while True:
        user_counts: dict[int, int] = defaultdict(int)
        business_counts: dict[str, int] = defaultdict(int)
        for user_id, business_id, _stars in filtered:
            user_counts[user_id] += 1
            business_counts[business_id] += 1

        next_filtered = [
            interaction
            for interaction in filtered
            if user_counts[interaction[0]] >= min_user_reviews
            and business_counts[interaction[1]] >= min_business_reviews
        ]
        if len(next_filtered) == len(filtered):
            return next_filtered
        filtered = next_filtered


def latest_rating_interactions(
    interactions: list[RawRatingInteraction],
) -> list[RatingInteraction]:
    latest_by_pair: dict[tuple[int, str], RawRatingInteraction] = {}
    for interaction in interactions:
        key = (interaction[0], interaction[1])
        current = latest_by_pair.get(key)
        if current is None or _is_newer_interaction(interaction, current):
            latest_by_pair[key] = interaction
    return [
        (user_id, business_id, stars)
        for user_id, business_id, stars, _review_date, _row_id in latest_by_pair.values()
    ]


def user_cf_recommendations_from_ratings(
    interactions: list[RatingInteraction],
    *,
    top_k: int = 20,
    similar_user_k: int = 20,
    min_common_items: int = 2,
) -> dict[str, list[RecommendationCandidate]]:
    user_ratings = build_user_ratings(interactions)
    user_means = {
        user_id: sum(ratings.values()) / len(ratings)
        for user_id, ratings in user_ratings.items()
        if ratings
    }
    recommendations: dict[str, list[RecommendationCandidate]] = {}

    for user_id, ratings in user_ratings.items():
        user_sims: list[tuple[int, float]] = []
        for other_user_id, other_ratings in user_ratings.items():
            if other_user_id == user_id:
                continue
            similarity = _centered_cosine_similarity(
                ratings,
                other_ratings,
                user_mean=user_means[user_id],
                other_mean=user_means[other_user_id],
                min_common_items=min_common_items,
            )
            if similarity > 0:
                user_sims.append((other_user_id, similarity))

        scores: dict[str, float] = defaultdict(float)
        weights: dict[str, float] = defaultdict(float)
        for other_user_id, similarity in sorted(
            user_sims,
            key=lambda item: item[1],
            reverse=True,
        )[:similar_user_k]:
            other_mean = user_means[other_user_id]
            for business_id, stars in user_ratings[other_user_id].items():
                if business_id in ratings:
                    continue
                scores[business_id] += similarity * (stars - other_mean)
                weights[business_id] += similarity

        candidates = []
        for business_id, weighted_score in scores.items():
            weight = weights[business_id]
            if weight <= 0:
                continue
            predicted = user_means[user_id] + (weighted_score / weight)
            candidates.append(
                RecommendationCandidate(
                    item_id=business_id,
                    score=predicted,
                )
            )

        recommendations[str(user_id)] = sorted(
            candidates,
            key=lambda candidate: candidate.score,
            reverse=True,
        )[:top_k]

    return recommendations


def serialize_business_recommendations(
    recommendations: dict[str, list[RecommendationCandidate]],
) -> dict[str, list[dict[str, float | str]]]:
    return {
        key: [
            {
                "business_id": candidate.item_id,
                "score": round(candidate.score, 6),
            }
            for candidate in candidates
        ]
        for key, candidates in recommendations.items()
    }


def _is_newer_interaction(
    candidate: RawRatingInteraction,
    current: RawRatingInteraction,
) -> bool:
    candidate_date = candidate[3]
    current_date = current[3]
    if candidate_date is None and current_date is None:
        return candidate[4] > current[4]
    if candidate_date is None:
        return False
    if current_date is None:
        return True
    if candidate_date == current_date:
        return candidate[4] > current[4]
    return candidate_date > current_date


def _centered_cosine_similarity(
    ratings: dict[str, float],
    other_ratings: dict[str, float],
    *,
    user_mean: float,
    other_mean: float,
    min_common_items: int,
) -> float:
    common_items = set(ratings) & set(other_ratings)
    if len(common_items) < min_common_items:
        return 0.0

    numerator = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for business_id in common_items:
        left = ratings[business_id] - user_mean
        right = other_ratings[business_id] - other_mean
        numerator += left * right
        left_norm += left * left
        right_norm += right * right

    if numerator <= 0 or left_norm <= 0 or right_norm <= 0:
        return 0.0
    return numerator / sqrt(left_norm * right_norm)
