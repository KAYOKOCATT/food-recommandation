from __future__ import annotations

from uuid import uuid4
from dataclasses import dataclass
from pathlib import Path
from math import log1p

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.recommendations.models import YelpBusiness, YelpReview
from apps.recommendations.services.similarity import (
    RecommendationCandidate,
    rerank_from_recent_items,
    similarity_cache,
)


@dataclass(frozen=True)
class YelpBusinessRecommendation:
    business: YelpBusiness
    score: float


class YelpService:
    SIMILARITY_FILE = settings.BASE_DIR / "data" / "recommendations" / "yelp_content_itemcf.json"
    USERCF_FILE = settings.BASE_DIR / "data" / "recommendations" / "yelp_usercf.json"
    ALS_FILE = settings.BASE_DIR / "data" / "recommendations" / "yelp_als_userrec.json"

    @classmethod
    def build_business_queryset(
        cls,
        *,
        q: str = "",
        city: str = "",
        is_open_only: bool = False,
    ) -> QuerySet[YelpBusiness]:
        queryset = YelpBusiness.objects.all()
        keyword = q.strip()
        city_name = city.strip()

        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(categories__icontains=keyword)
                | Q(city__icontains=keyword)
                | Q(state__icontains=keyword)
            )
        if city_name:
            queryset = queryset.filter(city__iexact=city_name)
        if is_open_only:
            queryset = queryset.filter(is_open=True)
        return queryset.order_by("-review_count", "-stars", "name")

    @classmethod
    def list_businesses(
        cls,
        *,
        page: int = 1,
        per_page: int = 18,
        q: str = "",
        city: str = "",
        is_open_only: bool = False,
    ):
        paginator = Paginator(
            cls.build_business_queryset(q=q, city=city, is_open_only=is_open_only),
            max(per_page, 1),
        )
        return paginator.get_page(page)

    @classmethod
    def get_business(cls, business_id: str) -> YelpBusiness | None:
        return YelpBusiness.objects.filter(business_id=business_id).first()

    @classmethod
    def get_recent_reviews(
        cls,
        business: YelpBusiness,
        *,
        limit: int = 5,
    ) -> QuerySet[YelpReview]:
        return business.reviews.select_related("user").order_by(
            "-review_date", "-id"
        )[: max(limit, 1)]

    @classmethod
    def create_local_review(
        cls,
        *,
        business: YelpBusiness,
        user_id: int,
        stars: float,
        text: str,
    ) -> YelpReview:
        review = YelpReview.objects.create(
            review_id=cls._build_local_review_id(user_id),
            business=business,
            user_id=user_id,
            source="local",
            stars=stars,
            text=text,
            review_date=timezone.now(),
        )
        cls.refresh_aggregated_review_counts([business.id])
        return review

    @classmethod
    def refresh_aggregated_review_counts(
        cls,
        business_ids: list[int] | None = None,
    ) -> None:
        queryset = YelpBusiness.objects.all()
        if business_ids is not None:
            if not business_ids:
                return
            queryset = queryset.filter(id__in=business_ids)

        businesses = list(queryset.only("id", "aggregated_review_count"))
        if not businesses:
            return

        counts = (
            YelpReview.objects.filter(business_id__in=[business.id for business in businesses])
            .values("business_id")
            .annotate(total=Count("id"))
        )
        count_map = {row["business_id"]: row["total"] for row in counts}
        for business in businesses:
            business.aggregated_review_count = count_map.get(business.id, 0)
        YelpBusiness.objects.bulk_update(businesses, ["aggregated_review_count"])

    @classmethod
    def get_similar_businesses(
        cls,
        business_id: str,
        *,
        top_k: int = 6,
        similarity_file: str | Path | None = None,
    ) -> list[YelpBusinessRecommendation]:
        if top_k <= 0:
            return []

        source = Path(similarity_file) if similarity_file else cls.SIMILARITY_FILE
        candidates = cls._safe_similarity_candidates(source, business_id)
        if not candidates:
            return []

        candidate_ids = [
            candidate.item_id
            for candidate in candidates
            if candidate.item_id != business_id
        ]
        businesses = YelpBusiness.objects.in_bulk(candidate_ids, field_name="business_id")
        recommendations: list[YelpBusinessRecommendation] = []

        for candidate in candidates:
            if candidate.item_id == business_id:
                continue
            business = businesses.get(candidate.item_id)
            if business is None:
                continue
            recommendations.append(
                YelpBusinessRecommendation(business=business, score=candidate.score)
            )
            if len(recommendations) >= top_k:
                break
        return recommendations

    @classmethod
    def get_usercf_recommendations(
        cls,
        user_id: int,
        *,
        top_k: int = 20,
        recommendation_file: str | Path | None = None,
    ) -> list[YelpBusinessRecommendation]:
        if top_k <= 0:
            return []

        source = Path(recommendation_file) if recommendation_file else cls.USERCF_FILE
        try:
            candidates = similarity_cache.get(source).get(str(user_id), [])
        except (OSError, ValueError):
            return []

        seen_business_ids = set(
            YelpReview.objects.filter(user_id=user_id).values_list(
                "business__business_id",
                flat=True,
            )
        )
        businesses = YelpBusiness.objects.in_bulk(
            [
                candidate.item_id
                for candidate in candidates
                if candidate.item_id not in seen_business_ids
            ],
            field_name="business_id",
        )

        recommendations: list[YelpBusinessRecommendation] = []
        for candidate in candidates:
            if candidate.item_id in seen_business_ids:
                continue
            business = businesses.get(candidate.item_id)
            if business is None:
                continue
            recommendations.append(
                YelpBusinessRecommendation(business=business, score=candidate.score)
            )
            if len(recommendations) >= top_k:
                break
        return recommendations

    @classmethod
    def get_als_recommendations(
        cls,
        user_id: int,
        *,
        top_k: int = 20,
        recommendation_file: str | Path | None = None,
    ) -> list[YelpBusinessRecommendation]:
        if top_k <= 0:
            return []

        source = Path(recommendation_file) if recommendation_file else cls.ALS_FILE
        try:
            candidates = similarity_cache.get(source).get(str(user_id), [])
        except (OSError, ValueError):
            return []

        seen_business_ids = set(
            YelpReview.objects.filter(user_id=user_id).values_list(
                "business__business_id",
                flat=True,
            )
        )
        businesses = YelpBusiness.objects.in_bulk(
            [
                candidate.item_id
                for candidate in candidates
                if candidate.item_id not in seen_business_ids
            ],
            field_name="business_id",
        )

        recommendations: list[YelpBusinessRecommendation] = []
        for candidate in candidates:
            if candidate.item_id in seen_business_ids:
                continue
            business = businesses.get(candidate.item_id)
            if business is None:
                continue
            recommendations.append(
                YelpBusinessRecommendation(business=business, score=candidate.score)
            )
            if len(recommendations) >= top_k:
                break
        return recommendations

    @classmethod
    def get_recent_recommendations(
        cls,
        user_id: int,
        *,
        top_k: int = 12,
        recent_limit: int = 8,
        similarity_file: str | Path | None = None,
    ) -> tuple[list[YelpBusinessRecommendation], bool]:
        recent_business_ids = cls._recent_review_business_ids(
            user_id,
            limit=max(recent_limit, 1),
        )
        if not recent_business_ids:
            return cls.get_popular_recommendations(top_k=top_k), False

        source = Path(similarity_file) if similarity_file else cls.SIMILARITY_FILE
        try:
            candidates = rerank_from_recent_items(
                recent_business_ids,
                source,
                top_k=max(top_k * 3, top_k),
            )
        except (OSError, ValueError):
            candidates = []

        seen_business_ids = set(recent_business_ids)
        candidate_ids = [
            candidate.item_id
            for candidate in candidates
            if candidate.item_id not in seen_business_ids
        ]
        businesses = YelpBusiness.objects.in_bulk(candidate_ids, field_name="business_id")

        recommendations: list[YelpBusinessRecommendation] = []
        for candidate in candidates:
            if candidate.item_id in seen_business_ids:
                continue
            business = businesses.get(candidate.item_id)
            if business is None:
                continue
            blended_score = cls._blend_recent_and_popularity(
                recent_score=candidate.score,
                business=business,
            )
            recommendations.append(
                YelpBusinessRecommendation(
                    business=business,
                    score=blended_score,
                )
            )
            if len(recommendations) >= top_k:
                break

        if recommendations:
            return recommendations, True
        return cls.get_popular_recommendations(top_k=top_k), False

    @classmethod
    def get_popular_recommendations(
        cls,
        *,
        top_k: int = 12,
    ) -> list[YelpBusinessRecommendation]:
        if top_k <= 0:
            return []

        businesses = list(
            YelpBusiness.objects.order_by("-review_count", "-stars", "name")[:top_k]
        )
        return [
            YelpBusinessRecommendation(
                business=business,
                score=cls._popularity_score(business),
            )
            for business in businesses
        ]

    @staticmethod
    def _safe_similarity_candidates(
        similarity_file: Path,
        business_id: str,
    ) -> list[RecommendationCandidate]:
        try:
            return similarity_cache.get(similarity_file).get(str(business_id), [])
        except (OSError, ValueError):
            return []

    @staticmethod
    def _build_local_review_id(user_id: int) -> str:
        return f"local_{user_id}_{uuid4().hex[:20]}"

    @classmethod
    def _recent_review_business_ids(
        cls,
        user_id: int,
        *,
        limit: int,
    ) -> list[str]:
        interactions = YelpReview.objects.filter(user_id=user_id).order_by(
            "-review_date", "-id"
        ).values_list("business__business_id", flat=True)
        seen: set[str] = set()
        result: list[str] = []
        for business_id in interactions:
            if business_id in seen:
                continue
            seen.add(business_id)
            result.append(business_id)
            if len(result) >= limit:
                break
        return result

    @classmethod
    def _blend_recent_and_popularity(
        cls,
        *,
        recent_score: float,
        business: YelpBusiness,
    ) -> float:
        return round((recent_score * 0.75) + (cls._popularity_score(business) * 0.25), 6)

    @staticmethod
    def _popularity_score(business: YelpBusiness) -> float:
        return round(log1p(max(business.review_count, 0)) + (business.stars * 0.1), 6)
