from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.recommendations.models import YelpBusiness
from apps.recommendations.services import YelpService


def yelp_business_list(request: HttpRequest) -> HttpResponse:
    page = request.GET.get("page", "1")
    q = request.GET.get("q", "")
    city = request.GET.get("city", "")
    page_obj = YelpService.list_businesses(page=page, q=q, city=city)

    return render(
        request,
        "recommendations/yelp_business_list.html",
        {
            "page_obj": page_obj,
            "search_query": q,
            "selected_city": city,
        },
    )


def yelp_business_detail(request: HttpRequest, business_id: str) -> HttpResponse:
    business = get_object_or_404(YelpBusiness, business_id=business_id)
    return render(
        request,
        "recommendations/yelp_business_detail.html",
        {
            "business": business,
            "similar_businesses": YelpService.get_similar_businesses(business.business_id, top_k=6),
            "recent_reviews": YelpService.get_recent_reviews(business, limit=5),
        },
    )
