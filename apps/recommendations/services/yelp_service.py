from __future__ import annotations

from uuid import uuid4
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.recommendations.models import YelpBusiness, YelpReview
from apps.recommendations.services.similarity import (
    RecommendationCandidate,
    similarity_cache,
)


@dataclass(frozen=True)
class YelpBusinessRecommendation:
    business: YelpBusiness
    score: float


class YelpService:
    SIMILARITY_FILE = settings.BASE_DIR / "data" / "recommendations" / "yelp_content_itemcf.json"
    USERCF_FILE = settings.BASE_DIR / "data" / "recommendations" / "yelp_usercf.json"

    @classmethod
    def build_business_queryset(
        cls,
        *,
        q: str = "",
        city: str = "",
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
        return queryset.order_by("-review_count", "-stars", "name")

    @classmethod
    def list_businesses(
        cls,
        *,
        page: int = 1,
        per_page: int = 18,
        q: str = "",
        city: str = "",
    ):
        paginator = Paginator(cls.build_business_queryset(q=q, city=city), max(per_page, 1))
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
