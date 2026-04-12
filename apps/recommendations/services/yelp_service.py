from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet

from apps.recommendations.models import YelpBusiness, YelpReview
from apps.recommendations.services.similarity import similarity_cache


@dataclass(frozen=True)
class YelpBusinessRecommendation:
    business: YelpBusiness
    score: float


class YelpService:
    SIMILARITY_FILE = settings.BASE_DIR / "data" / "recommendations" / "yelp_content_itemcf.json"

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
        return business.reviews.select_related("user").order_by("-review_date", "-id")[: max(limit, 1)]

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
        try:
            candidates = similarity_cache.get(source).get(str(business_id), [])
        except (OSError, ValueError):
            return []

        candidate_ids = [candidate.item_id for candidate in candidates if candidate.item_id != business_id]
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
